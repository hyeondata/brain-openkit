"""Verify metric semantics, including failures, without running a model."""

import importlib.util
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from brain_openkit.providers import Decision

_path = Path(__file__).resolve().parents[1] / "benchmarks" / "run_bilingual.py"
_spec = importlib.util.spec_from_file_location("benchmark_runner", _path)
benchmark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(benchmark)


@contextmanager
def decision_server(provider="kev"):
    """Exercise the complete runner without loading an external model."""
    requests = []
    model = "mmetamong/ko-decision-roberta-large" if provider == "ko-decision" else "fixture-kev"
    revision = "dfd606fff30d52963c0073659ff9a8f6bf1fce6d"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, body):
            encoded = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            card = {"name": model, "description": "Fixture only", "release_date": "2026-01-01",
                    "run": "fixture/weights@abc"}
            if provider == "ko-decision":
                card.update(revision=revision, max_length=512, truncate_states=False)
            self.reply({"models": [card]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            choices = body["questions"]["decision"]["criteria"]
            selected = next(iter(choices))
            response = {"model": model, "answers": {"decision": {
                "type": "choice", "choice": selected, "confidence": 1.0,
                "probabilities": {key: float(key == selected) for key in choices},
            }}, "usage": {"input_tokens": 10, "output_tokens": 0}}
            if provider == "ko-decision":
                response["model_revision"] = revision
                response["usage"].update(model_revision=revision, max_pair_tokens=10,
                                         state_tokens=5, state_tokens_dropped=0,
                                         truncated=False, truncated_questions=[])
            self.reply(response)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", requests
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


class BenchmarkTests(unittest.TestCase):
    def test_wrong_category_false_tags_and_missed_tags_are_counted(self):
        taxonomy = {"categories": {"x": "X", "y": "Y"}, "tags": {"a": "A", "b": "B"}}
        rows = [
            {"category": "x", "tags": ["a"], "elapsed_ms": 1,
             "result": {"category": "x", "tags": ["a", "b"]}},
            {"category": "y", "tags": ["a", "b"], "elapsed_ms": 2,
             "result": {"category": "x", "tags": ["b"]}},
        ]
        result = benchmark.classification_metrics(rows, taxonomy)
        self.assertEqual(result["category_accuracy"], 0.5)
        self.assertAlmostEqual(result["category_macro_f1"], 1 / 3)
        self.assertAlmostEqual(result["tag_micro_f1"], 2 / 3)
        self.assertAlmostEqual(result["tag_macro_f1"], 2 / 3)
        self.assertEqual(result["tag_exact_match"], 0)
        self.assertEqual(result["elapsed_ms"], 3)

    def test_language_metrics_expose_false_positive_and_missed_tags(self):
        taxonomy = {"categories": {"x": "X", "y": "Y"}, "tags": {"a": "A", "b": "B"}}
        rows = [
            {"language": "ko", "category": "x", "tags": ["a"], "elapsed_ms": 1,
             "result": {"category": "x", "tags": ["a", "b"]}},
            {"language": "ko", "category": "y", "tags": ["b"], "elapsed_ms": 2,
             "result": {"category": "x", "tags": []}},
            {"language": "en", "category": "y", "tags": ["a"], "elapsed_ms": 3,
             "result": {"category": "y", "tags": ["a"]}},
        ]
        result = benchmark.classification_metrics(rows, taxonomy)
        self.assertEqual(result.get("tag_false_positives"), 1)
        self.assertEqual(result.get("tag_false_negatives"), 1)
        self.assertAlmostEqual(result["tag_micro_precision"], 2 / 3)
        self.assertAlmostEqual(result["tag_micro_recall"], 2 / 3)
        korean = result["by_language"]["ko"]
        self.assertEqual(korean["category_accuracy"], 0.5)
        self.assertEqual(korean["tag_micro_precision"], 0.5)
        self.assertEqual(korean["tag_micro_recall"], 0.5)
        self.assertEqual(korean["tag_false_positives"], 1)
        self.assertEqual(result["by_language"]["en"]["category_accuracy"], 1)
        self.assertEqual(result["by_language"]["en"]["tag_false_positives"], 0)

    def test_recording_preserves_provider_name_and_excludes_every_warmup(self):
        class FixedProvider:
            name = "kev"

            def choose(self, state, question, choices):
                return Decision("A", {"A": 1.0}, 1.0, "fixture-kev", {}, 0)

        output = io.StringIO()
        provider = benchmark.RecordingProvider(FixedProvider(), output)
        self.assertEqual(provider.name, "kev")
        with patch.object(benchmark, "perf_counter", side_effect=[0, 1, 2, 4, 5, 5.125]):
            provider.choose("State", "Question", {"A": "Answer"})
            provider.choose("State", "Question", {"A": "Answer"})
            provider.phase = "retrieval-holdout"
            provider.choose("State", "Question", {"A": "Answer"})
        self.assertEqual(provider.timings, [1000, 2000, 125])
        self.assertEqual(provider.measured_timings, [125])
        self.assertEqual(provider.warmup_timings, [1000, 2000])
        self.assertEqual(provider.models, {"fixture-kev"})
        self.assertEqual([json.loads(line)["phase"] for line in output.getvalue().splitlines()],
                         ["warmup", "warmup", "retrieval-holdout"])

    def test_kev_cli_records_actual_provider_model_and_runtime_metadata(self):
        with tempfile.TemporaryDirectory() as directory, decision_server() as (url, requests):
            root = Path(directory)
            runtime = root / "runtime.json"
            runtime.write_text(json.dumps({"package": "fixture-kev", "version": "fixture-1"}))
            output = root / "report"
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                try:
                    code = benchmark.main(["--provider", "kev", "--base-url", url,
                                           "--model", "fixture-alias", "--timeout", "2",
                                           "--runtime-metadata", str(runtime), "--output", str(output)])
                except SystemExit as exc:
                    self.fail(f"Benchmark CLI rejected a supported provider: {exc.code}")
            self.assertEqual(code, 0)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["provider"], "kev")
            self.assertEqual(report["requested_model"], "fixture-alias")
            self.assertEqual(report["observed_models"], ["fixture-kev"])
            self.assertEqual(report["prompt_language"], "en")
            self.assertEqual(report["server_runtime"]["version"], "fixture-1")
            self.assertEqual(report["health_after"]["models"][0]["run"], "fixture/weights@abc")
            self.assertTrue(report["source_preservation"]["unchanged"])
            self.assertEqual(report["classification"]["holdout"]["note_count"], 18)
            self.assertEqual(report["classification"]["holdout"]["by_language"]["ko"]["note_count"], 8)
            self.assertEqual(report["requests"]["count_excluding_warmup"], len(requests) - 1)
            self.assertEqual(report["requests"]["warmup_count"], 1)
            self.assertEqual({row["model"] for row in requests}, {"fixture-alias"})
            rows = report["retrieval"]["holdout"]["queries"]
            self.assertTrue(all(row["requested"]["provider"] == "kev" for row in rows))
            self.assertEqual(report["requests"]["error_count"], 0)

    def test_ko_cli_uses_selected_provider_and_preserves_pinned_health_metadata(self):
        with tempfile.TemporaryDirectory() as directory, decision_server("ko-decision") as (url, requests):
            output = Path(directory) / "report"
            with redirect_stdout(io.StringIO()):
                code = benchmark.main(["--provider", "ko-decision", "--base-url", url,
                                       "--prompt-language", "ko", "--output", str(output)])
            self.assertEqual(code, 0)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["provider"], "ko-decision")
            self.assertEqual(report["requested_model"], "mmetamong/ko-decision-roberta-large")
            self.assertEqual(report["observed_models"], ["mmetamong/ko-decision-roberta-large"])
            self.assertEqual(report["prompt_language"], "ko")
            self.assertEqual(report["health_after"]["models"][0]["revision"],
                             "dfd606fff30d52963c0073659ff9a8f6bf1fce6d")
            self.assertEqual(report["requests"]["error_count"], 0)
            self.assertEqual(report["classification"]["all"]["error_count"], 0)
            self.assertTrue(all(row["provider"] == "ko-decision"
                                for row in (entry["result"] for entry in report["classification"]["results"])))
            self.assertTrue(all(any("가" <= c <= "힣" for c in row["questions"]["decision"]["instructions"])
                                for row in requests))

    def test_failed_or_abstaining_category_does_not_disappear_from_denominator(self):
        taxonomy = {"categories": {"x": "X"}, "tags": {"a": "A"}}
        rows = [
            {"category": "x", "tags": [], "elapsed_ms": 1, "result": None, "error": "timeout"},
            {"category": "x", "tags": [], "elapsed_ms": 1,
             "result": {"category": None, "tags": [], "review_required": True}},
        ]
        result = benchmark.classification_metrics(rows, taxonomy)
        self.assertEqual(result["error_count"], 1)
        self.assertEqual(result["review_required_count"], 1)
        self.assertEqual(result["category_accuracy"], 0)
        self.assertEqual(result["tag_exact_match"], 0.5)
        self.assertEqual(result["tag_sample_f1"], 0.5)

    def test_false_matches_and_misses_are_explicit(self):
        report = {"queries": [{"relevant": ["right.md"], "requested": None,
                               "baseline": {"paths": ["wrong.md"], "recall_at_k": 0, "reciprocal_rank": 0}}]}
        benchmark.annotate_retrieval(report, [{"id": "hold-01", "language": "ko"}])
        row = report["queries"][0]
        self.assertEqual(row["baseline"]["misses"], ["right.md"])
        self.assertEqual(row["baseline"]["false_matches"], ["wrong.md"])

    def test_frozen_suite_is_complete_and_splits_do_not_overlap(self):
        suite = _path.parent / "bilingual-v1"
        self.assertEqual(benchmark.validate_suite(suite)["suite"], "bilingual-v1")

    def test_unfrozen_nested_or_uppercase_markdown_is_rejected(self):
        for relative in ("nested/extra.md", "EXTRA.MD"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                copied = Path(directory) / "suite"
                shutil.copytree(_path.parent / "bilingual-v1", copied,
                                ignore=shutil.ignore_patterns("reports"))
                extra = copied / "vault" / relative
                extra.parent.mkdir(parents=True, exist_ok=True)
                extra.write_text("# Extra searchable document\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "frozen manifest"):
                    benchmark.validate_suite(copied)


if __name__ == "__main__":
    unittest.main()
