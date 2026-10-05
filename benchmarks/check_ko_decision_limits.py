#!/usr/bin/env python3
"""Verify Korean model limits and reviewed Obsidian writes using synthetic notes.

Requires a running ko-decision server. This is a functional check, not a model
quality benchmark. It makes real CLI requests, writes only a temporary vault,
and undoes its reviewed metadata change before deleting the temporary files.
No inference packages are imported by this verifier.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "mmetamong/ko-decision-roberta-large"
MODEL_REVISION = "dfd606fff30d52963c0073659ff9a8f6bf1fce6d"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def check(base_url="http://127.0.0.1:8010", timeout=120, python=sys.executable, installed=False):
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Synthetic functional verification; one labeled example is not a quality estimate",
        "provider": "ko-decision", "prompt_language": "ko", "model": MODEL_ID,
        "expected_model_revision": MODEL_REVISION, "cli_mode": "installed" if installed else "source",
        "commands": [],
    }
    with tempfile.TemporaryDirectory(prefix="brain-openkit-ko-limits-") as directory:
        temp = Path(directory)
        vault = temp / "vault"
        vault.mkdir()
        cache = temp / "cache"
        short = vault / "backup.md"
        original = ("# 옵시디언 노트 백업\r\n\r\n"
                    "옵시디언의 마크다운 노트를 매일 외장 디스크에 백업한다.\r\n"
                    "복원 시험을 통해 파일이 손상되지 않았는지 확인한다.\r\n").encode("utf-8")
        short.write_bytes(original)
        long = vault / "oversized.md"
        long.write_text("백업 " * 900 + "\n", encoding="utf-8")
        before = {path.name: sha256(path.read_bytes()) for path in (short, long)}
        taxonomy = temp / "taxonomy.json"
        taxonomy.write_text(json.dumps({
            "categories": {"기술": "소프트웨어와 데이터 관리에 관한 기록", "요리": "음식의 재료와 조리법에 관한 기록"},
            "tags": {"백업": "데이터를 복사하고 복원하여 보존하는 방법", "요리": "음식과 조리 방법"},
        }, ensure_ascii=False), encoding="utf-8")

        def normalize(value):
            if isinstance(value, str):
                for path in sorted({str(temp), str(temp.resolve())}, key=len, reverse=True):
                    value = value.replace(path, "<temporary>")
                return value.replace(str(ROOT), "<checkout>").replace(str(python), "<python>")
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items()}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            return value

        launcher = [python, "-I", "-m", "brain_openkit"] if installed else [python, str(ROOT / "scripts/brain-openkit.py")]

        def cli(*args, expected=0):
            command = [*launcher, *args, "--vault", str(vault), "--cache-dir", str(cache), "--json"]
            result = subprocess.run(command, capture_output=True, encoding="utf-8", timeout=timeout * 3 + 30)
            try:
                payload = json.loads(result.stdout)
            except (ValueError, UnicodeError):
                raise AssertionError(f"CLI did not return JSON: {normalize(list(args))}") from None
            report["commands"].append({"argv": normalize(command), "exit_code": result.returncode,
                                       "response": normalize(payload)})
            require(result.returncode == expected,
                    f"Unexpected CLI exit {result.returncode}: {normalize(list(args))}: {normalize(payload)}")
            require(not result.stderr.strip(), "CLI emitted unexpected stderr")
            return payload

        selected = ["--provider", "ko-decision", "--prompt-language", "ko",
                    "--base-url", base_url, "--timeout", str(timeout)]
        health = cli("doctor", *selected)
        require(health["provider"] == "ko-decision" and health["inference_verified"] is False,
                "Health check unexpectedly performed inference")
        loaded = [card for card in health["health"]["models"] if card["name"] == MODEL_ID]
        require(len(loaded) == 1 and loaded[0]["revision"] == MODEL_REVISION,
                "Loaded model revision does not match this verification")
        report["model_revision"] = loaded[0]["revision"]

        baseline = cli("search", "백업", "--provider", "none", "--prompt-language", "ko",
                       "--limit", "2", "--candidates", "2")
        require({row["path"] for row in baseline["results"]} == {"backup.md", "oversized.md"},
                "Synthetic search must include both short and oversized notes")
        retrieved = cli("search", "백업", "--limit", "2", "--candidates", "2", *selected)
        require(retrieved["rerank_status"] == "unavailable" and retrieved["fallback_reason"] == "http_413",
                "Oversized pair did not produce an explicit HTTP 413 fallback")
        columns = ("path", "start_line", "end_line", "text", "bm25_score")
        require([[row[key] for key in columns] for row in retrieved["results"]]
                == [[row[key] for key in columns] for row in baseline["results"]],
                "Failed model reranking changed the BM25 ordering or citations")
        require(all(row["model_score"] is None and row["decision"] is None for row in retrieved["results"]),
                "Failed reranking retained a partial or fabricated model result")
        failed = cli("classify", "oversized.md", "--taxonomy", str(taxonomy), *selected, expected=2)
        require(set(failed) == {"error"} and failed["error"]["message"] == "http_413",
                "Oversized classification returned an invented classification")
        require({path.name: sha256(path.read_bytes()) for path in (short, long)} == before,
                "Read-only error checks modified source notes")
        report["oversized_input"] = {
            "single_line_repetitions": 900,
            "search_restores_complete_bm25": True, "search_fallback_reason": "http_413",
            "classification_exit_code": 2, "classification_error": "http_413",
            "source_hashes_unchanged": True,
            "boundary_scope": "Exact 512/513-token boundary is covered separately by runtime unit tests",
        }

        classified = cli("classify", "backup.md", "--taxonomy", str(taxonomy), *selected)
        require(classified["status"] == "complete" and classified["provider"] == "ko-decision"
                and classified["model"] == MODEL_ID and classified["note_modified"] is False,
                "Classification contract is incomplete")
        require(classified["category"] in {"기술", "요리"} and classified["review_required"] is False,
                "Single short note did not yield an existing category")
        require(isinstance(classified["tags"], list) and set(classified["tags"]) <= {"백업", "요리"},
                "Classification invented a tag outside the taxonomy")
        require(len(classified["passages"]) == 1, "The short fixture must remain a single passage")
        passage = classified["passages"][0]
        require(set(passage["tags"]) == {"백업", "요리"}, "Missing tag decisions")
        for decision in [passage["category_decision"], *passage["tags"].values()]:
            require(decision["usage"]["model_revision"] == MODEL_REVISION
                    and decision["usage"]["truncated"] is False
                    and decision["usage"]["state_tokens_dropped"] == 0,
                    "Prediction lost model provenance or silently truncated the note")
        predicted_tags = set(classified["tags"])
        report["single_labeled_example"] = {
            "expected_category": "기술", "predicted_category": classified["category"],
            "category_matches": classified["category"] == "기술",
            "expected_tags": ["백업"], "predicted_tags": classified["tags"],
            "exact_tags_match": predicted_tags == {"백업"},
            "false_positive_tags": sorted(predicted_tags - {"백업"}),
            "false_negative_tags": sorted({"백업"} - predicted_tags),
            "quality_conclusion": "Not estimated from this single synthetic note",
        }
        plan_file = temp / "organize-plan.json"
        arguments = ["organize", "backup.md", "--category", classified["category"], "--plan", str(plan_file)]
        for tag in classified["tags"]:
            arguments.extend(["--tag", tag])
        plan = cli(*arguments)
        require(short.read_bytes() == original, "Organize preview changed the note before approval")
        require(plan_file.is_file() and not plan_file.resolve().is_relative_to(vault.resolve()),
                "Review plan was not stored outside the vault")
        require(len(plan["changes"]) == 1 and plan["changes"][0]["path"] == "backup.md",
                "Organize preview targeted unexpected notes")
        applied = cli("apply", str(plan_file), "--approve", plan["id"])
        require(applied["status"] == "applied" and applied["transaction_id"], "Reviewed plan was not applied")
        updated = short.read_bytes()
        require(updated.endswith(original), "Organizing changed original Markdown body bytes")
        prefix = updated[:-len(original)].decode("utf-8")
        lines = prefix.splitlines()
        require(lines[0] == "---" and lines[-1] == "---", "Missing Obsidian frontmatter delimiters")
        metadata = {key: json.loads(value) for key, value in (line.split(": ", 1) for line in lines[1:-1])}
        require(metadata["category"] == classified["category"]
                and set(metadata.get("tags", [])) == predicted_tags,
                "Applied metadata differs from the reviewed model suggestions")
        require(sha256(long.read_bytes()) == before["oversized.md"], "Organize changed an unrelated note")
        applied_sha = sha256(updated)
        undone = cli("undo", applied["transaction_id"])
        require(undone["status"] == "undone", "Undo did not complete")
        require(short.read_bytes() == original
                and {path.name: sha256(path.read_bytes()) for path in (short, long)} == before,
                "Undo did not restore byte-identical original notes")
        report["reviewed_write"] = {
            "preview_did_not_modify_note": True, "plan_stored_outside_vault": True,
            "approved_exact_plan_id": plan["id"], "applied_metadata": metadata,
            "original_body_bytes_preserved": True, "source_sha256": before["backup.md"],
            "applied_sha256": applied_sha, "undo_restores_original_bytes": True,
        }
        report["source_sha256"] = before
        report["functional_checks_passed"] = True
    return report


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--timeout", type=int, default=120, help="Per-request timeout in seconds (1–300)")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter for CLI subprocesses")
    parser.add_argument("--installed", action="store_true", help="Use that interpreter's installed brain_openkit module")
    parser.add_argument("--output", type=Path, help="Save JSON report; otherwise print JSON to stdout")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be between 1 and 300 seconds")
    report = check(args.base_url, args.timeout, args.python, args.installed)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(args.output)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
