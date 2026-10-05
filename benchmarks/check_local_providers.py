#!/usr/bin/env python3
"""Functional checks against running Laya/Kev servers using only synthetic notes.

Run from a source checkout with Python 3.11+. This is not a quality benchmark.
Server/model setup and pinned revisions are documented in docs/local-models.md.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def unavailable_server():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def hashes(vault):
    return {str(p.relative_to(vault)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(vault.rglob("*.md"))}


def check(laya_url, kev_url, providers=("laya", "kev")):
    report = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "scope": "Synthetic functional smoke, not a quality or cost comparison",
              "providers": {}}
    with tempfile.TemporaryDirectory(prefix="brain-openkit-provider-smoke-") as directory:
        temp = Path(directory)
        vault = temp / "vault"
        shutil.copytree(ROOT / "examples/vault", vault)
        # Also exercise exact CRLF and Unicode preservation on both providers.
        note = vault / "local-search.md"
        note.write_bytes(note.read_bytes().replace(b"\n", b"\r\n"))
        before = hashes(vault)
        config = temp / "providers.json"
        config.write_text(json.dumps({"vault": str(vault), "cache_dir": str(temp / "cache"),
                                     "laya_base_url": laya_url, "kev_base_url": kev_url,
                                     "timeout": 120, "limit": 3, "candidates": 6}), encoding="utf-8")

        def cli(*args, expected=0):
            result = subprocess.run([sys.executable, str(ROOT / "scripts/brain-openkit.py"),
                                     *args, "--config", str(config), "--json"],
                                    capture_output=True, encoding="utf-8", timeout=300)
            if result.returncode != expected:
                raise AssertionError(f"CLI {args}: exit {result.returncode}: {result.stdout} {result.stderr}")
            return json.loads(result.stdout)

        cli("index")
        baseline = cli("search", "검색", "--provider", "none")
        assert baseline["results"], "Fixture must produce BM25 candidates"
        for provider in providers:
            checked = {}
            health = cli("doctor", "--provider", provider)
            assert health["provider"] == provider and health["inference_verified"] is False
            checked["health"] = health
            probe = cli("doctor", "--provider", provider, "--probe")
            assert probe["inference_verified"] is True
            checked["probe"] = probe
            checked["probe_matches_expected_A"] = probe["probe"]["choice"] == "A"
            retrieved = cli("search", "검색", "--provider", provider)
            assert retrieved["rerank_status"] == "complete" and retrieved["provider"] == provider
            assert retrieved["candidate_count"] > 0 and retrieved["results"]
            for hit in retrieved["results"]:
                assert hit["model_score"] is not None
                lines = (vault / hit["path"]).read_text(encoding="utf-8").splitlines()
                assert hit["text"].splitlines() == lines[hit["start_line"] - 1:hit["end_line"]]
            checked["search"] = retrieved
            checked["classify"] = {}
            for path in ("local-search.md", "reading.md"):
                classified = cli("classify", path, "--provider", provider,
                                 "--taxonomy", str(ROOT / "examples/taxonomy.json"))
                assert classified["provider"] == provider and classified["status"] == "complete"
                assert classified["note_modified"] is False
                assert classified["passages"] and all(len(p["tags"]) == 3 for p in classified["passages"])
                checked["classify"][path] = classified
            evaluation = cli("evaluate", str(ROOT / "examples/evaluation.jsonl"), "--provider", provider)
            assert evaluation["requested"]["model_query_count"] == 4
            assert evaluation["requested"]["fallback_query_count"] == 0
            checked["evaluate"] = evaluation
            # Inject an HTTP outage, not a model response, and check actual CLI behavior.
            with unavailable_server() as failed_url:
                fallback = cli("search", "검색", "--provider", provider, "--base-url", failed_url)
                assert fallback["rerank_status"] == "unavailable" and fallback["fallback_reason"] == "http_503"
                assert [h["path"] for h in fallback["results"]] == [h["path"] for h in baseline["results"]]
                assert all(h["model_score"] is None and h["decision"] is None for h in fallback["results"])
                failed = cli("classify", "local-search.md", "--provider", provider, "--base-url", failed_url,
                             "--taxonomy", str(ROOT / "examples/taxonomy.json"), expected=2)
                assert failed["error"]["message"] == "http_503"
                checked["injected_outage"] = {"search": fallback, "classify": failed}
            assert hashes(vault) == before, "Source notes changed"
            checked["source_hashes_unchanged"] = True
            report["providers"][provider] = checked
            print(f"{provider}: functional checks passed", flush=True)
        report["source_sha256"] = before
        report["functional_checks_passed"] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--laya-url", default="http://127.0.0.1:8000")
    parser.add_argument("--kev-url", default="http://127.0.0.1:8009")
    parser.add_argument("--provider", choices=("both", "laya", "kev"), default="both",
                        help="Check both servers, or only the selected provider")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    providers = ("laya", "kev") if args.provider == "both" else (args.provider,)
    report = check(args.laya_url, args.kev_url, providers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
