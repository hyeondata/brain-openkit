"""Verify metric semantics, including failures, without running a model."""

import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

_path = Path(__file__).resolve().parents[1] / "benchmarks" / "run_bilingual.py"
_spec = importlib.util.spec_from_file_location("benchmark_runner", _path)
benchmark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(benchmark)


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
