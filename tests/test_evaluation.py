import json
from pathlib import Path
import tempfile
import unittest

from brain_openkit.evaluation import evaluate
from brain_openkit.index import Index
from brain_openkit.providers import Decision, ProviderError


class PreferMarkedProvider:
    def choose(self, state, question, choices):
        probability = 0.95 if "preferred" in state else 0.05
        return Decision(
            choice="A" if probability > 0.5 else "B",
            probabilities={"A": probability, "B": 1 - probability},
            confidence=None,
            model="test-only-decisions",
            usage={},
            elapsed_ms=0.0,
        )


class UnavailableProvider:
    def choose(self, state, question, choices):
        raise ProviderError("Test provider is unavailable")


class CountingProvider(PreferMarkedProvider):
    def __init__(self):
        self.calls = 0

    def choose(self, state, question, choices):
        self.calls += 1
        return super().choose(state, question, choices)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        (self.vault / "a.md").write_text("# Comet\n\nComet observations.\n", encoding="utf-8")
        (self.vault / "b.md").write_text(
            "# Comet\n\nComet observations from the preferred observing location.\n", encoding="utf-8"
        )
        (self.vault / "korean.md").write_text("# 독서 기록\n\n한국어 독서 기록을 정리합니다.\n", encoding="utf-8")
        self.cache = self.root / "cache"
        index = Index(self.vault, self.cache)
        try:
            index.update()
        finally:
            index.close()
        self.dataset = self.root / "evaluation.jsonl"

    def write_dataset(self, rows):
        self.dataset.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8"
        )

    def test_bm25_reports_macro_recall_and_reciprocal_rank_at_limit(self):
        self.write_dataset([
            {"query": "comet", "relevant": ["a.md", "b.md"]},
            {"query": "unmatchableterm", "relevant": ["korean.md"]},
        ])
        report = evaluate(self.vault, self.dataset, cache_dir=self.cache, limit=1)
        self.assertEqual(report["query_count"], 2)
        self.assertEqual(report["baseline"]["recall_at_k"], 0.25)
        self.assertEqual(report["baseline"]["mrr"], 0.5)
        self.assertEqual(report["baseline"]["model_query_count"], 0)
        self.assertEqual(report["baseline"]["fallback_query_count"], 0)
        self.assertIsNone(report["requested"])
        self.assertGreaterEqual(report["baseline"]["elapsed_ms"], 0)
        self.assertEqual(report["queries"][1]["baseline"]["paths"], [])

    def test_requested_provider_metrics_are_separate_from_baseline(self):
        self.write_dataset([{"query": "comet", "relevant": ["b.md"]}])
        report = evaluate(
            self.vault, self.dataset, cache_dir=self.cache,
            provider=PreferMarkedProvider(), limit=1,
        )
        self.assertEqual(report["baseline"]["recall_at_k"], 0)
        self.assertEqual(report["baseline"]["mrr"], 0)
        self.assertEqual(report["requested"]["recall_at_k"], 1)
        self.assertEqual(report["requested"]["mrr"], 1)
        self.assertEqual(report["requested"]["model_query_count"], 1)
        self.assertEqual(report["requested"]["fallback_query_count"], 0)
        self.assertEqual(report["queries"][0]["requested"]["paths"], ["b.md"])
        self.assertEqual(report["queries"][0]["requested"]["rerank_status"], "complete")

    def test_failed_provider_reports_bm25_fallback_without_model_success(self):
        self.write_dataset([{"query": "comet", "relevant": ["a.md"]}])
        report = evaluate(
            self.vault, self.dataset, cache_dir=self.cache,
            provider=UnavailableProvider(), limit=1,
        )
        self.assertEqual(report["requested"]["recall_at_k"], report["baseline"]["recall_at_k"])
        self.assertEqual(report["requested"]["model_query_count"], 0)
        self.assertEqual(report["requested"]["fallback_query_count"], 1)
        self.assertEqual(report["queries"][0]["requested"]["rerank_status"], "unavailable")
        self.assertTrue(report["queries"][0]["requested"]["fallback_reason"])

    def test_no_candidates_do_not_count_as_model_inference(self):
        self.write_dataset([{"query": "unmatchableterm", "relevant": ["a.md"]}])
        report = evaluate(
            self.vault, self.dataset, cache_dir=self.cache,
            provider=UnavailableProvider(), limit=1,
        )
        self.assertEqual(report["requested"]["model_query_count"], 0)
        self.assertEqual(report["requested"]["fallback_query_count"], 0)
        self.assertEqual(report["requested"]["recall_at_k"], 0)
        self.assertEqual(report["queries"][0]["requested"]["paths"], [])

    def test_duplicate_relevance_labels_do_not_change_recall_denominator(self):
        self.write_dataset([{"query": "comet", "relevant": ["a.md", "a.md"]}])
        report = evaluate(self.vault, self.dataset, cache_dir=self.cache, limit=1)
        self.assertEqual(report["baseline"]["recall_at_k"], 1)
        self.assertEqual(report["queries"][0]["relevant"], ["a.md"])

    def test_invalid_dataset_rows_include_line_number(self):
        bad_rows = [
            [], {}, {"query": " ", "relevant": ["a.md"]},
            {"query": 3, "relevant": ["a.md"]},
            {"query": "comet", "relevant": []},
            {"query": "comet", "relevant": "a.md"},
            {"query": "comet", "relevant": [None]},
            {"query": "comet", "relevant": ["missing.md"]},
            {"query": "comet", "relevant": ["../outside.md"]},
            {"query": "comet", "relevant": [str(self.vault / "a.md")]},
            {"query": "comet", "relevant": ["C:\\vault\\a.md"]},
            {"query": "comet", "relevant": ["note.txt"]},
            {"query": "comet", "relevant": ["invalid\u0000.md"]},
        ]
        (self.root / "outside.md").write_text("outside", encoding="utf-8")
        (self.vault / "note.txt").write_text("not Markdown", encoding="utf-8")
        for row in bad_rows:
            with self.subTest(row=row):
                self.write_dataset([{"query": "comet", "relevant": ["a.md"]}, row])
                with self.assertRaisesRegex(ValueError, "line 2"):
                    evaluate(self.vault, self.dataset, cache_dir=self.cache)

    def test_symlink_labels_are_rejected(self):
        outside = self.root / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        link = self.vault / "linked.md"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Symbolic links are unavailable")
        self.write_dataset([{"query": "outside", "relevant": ["linked.md"]}])
        with self.assertRaisesRegex(ValueError, "line 1"):
            evaluate(self.vault, self.dataset, cache_dir=self.cache)

    def test_empty_malformed_and_unreadable_datasets_fail_clearly(self):
        for content, message in [("\n \n", "empty"), ("{broken}\n", "line 1")]:
            with self.subTest(content=content):
                self.dataset.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    evaluate(self.vault, self.dataset, cache_dir=self.cache)
        self.dataset.unlink()
        with self.assertRaisesRegex(ValueError, "[Dd]ataset"):
            evaluate(self.vault, self.dataset, cache_dir=self.cache)
        self.dataset.write_bytes(b"\xff")
        with self.assertRaisesRegex(ValueError, "[Dd]ataset"):
            evaluate(self.vault, self.dataset, cache_dir=self.cache)

    def test_limits_must_be_positive_integers(self):
        self.write_dataset([{"query": "comet", "relevant": ["a.md"]}])
        for option in ("limit", "candidates"):
            for value in (0, -1, True, 1.5):
                with self.subTest(option=option, value=value):
                    with self.assertRaisesRegex(ValueError, option):
                        evaluate(self.vault, self.dataset, cache_dir=self.cache, **{option: value})

    def test_excluded_invalid_utf8_and_empty_labels_stop_all_model_requests(self):
        labels = {
            ".obsidian/private.md": b"# Private configuration\n",
            "node_modules/dependency.md": b"# Dependency\n",
            "__pycache__/generated.md": b"# Generated\n",
            "bad.md": b"\xff",
            "empty.md": b" \n\t\n",
        }
        for label, data in labels.items():
            with self.subTest(label=label):
                target = self.vault / label
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(data)
                self.write_dataset([
                    {"query": "comet", "relevant": ["a.md"]},
                    {"query": "private", "relevant": [label]},
                ])
                provider = CountingProvider()
                with self.assertRaisesRegex(ValueError, "line 2"):
                    evaluate(self.vault, self.dataset, cache_dir=self.cache, provider=provider)
                self.assertEqual(provider.calls, 0)
                target.unlink()

    def test_configured_cache_notes_cannot_be_relevance_labels(self):
        cache = self.vault / "generated-cache"
        cache.mkdir()
        (cache / "cached.md").write_text("# Comet\nCached source copy.\n", encoding="utf-8")
        self.write_dataset([
            {"query": "comet", "relevant": ["a.md"]},
            {"query": "cached", "relevant": ["generated-cache/cached.md"]},
        ])
        provider = CountingProvider()
        with self.assertRaisesRegex(ValueError, "line 2"):
            evaluate(self.vault, self.dataset, cache_dir=cache, provider=provider)
        self.assertEqual(provider.calls, 0)

    def test_symlink_vault_is_rejected_before_resolving_it(self):
        alias = self.root / "vault-alias"
        try:
            alias.symlink_to(self.vault, target_is_directory=True)
        except OSError:
            self.skipTest("Symbolic links are unavailable")
        self.write_dataset([{"query": "comet", "relevant": ["a.md"]}])
        provider = CountingProvider()
        with self.assertRaisesRegex(ValueError, "symlink"):
            evaluate(alias, self.dataset, cache_dir=self.cache, provider=provider)
        self.assertEqual(provider.calls, 0)

    def test_non_label_index_errors_fail_instead_of_publishing_partial_metrics(self):
        (self.vault / "unreadable.md").write_bytes(b"\xff")
        self.write_dataset([{"query": "comet", "relevant": ["a.md"]}])
        provider = CountingProvider()
        with self.assertRaisesRegex(ValueError, "[Ii]ndex"):
            evaluate(self.vault, self.dataset, cache_dir=self.cache, provider=provider)
        self.assertEqual(provider.calls, 0)

    def test_candidate_bounds_are_checked_before_dataset_or_vault_reads(self):
        for limit, candidates in ((2, 1), (1, 201), (201, 201)):
            with self.subTest(limit=limit, candidates=candidates):
                with self.assertRaisesRegex(ValueError, "limit.*candidates"):
                    evaluate(self.root / "missing-vault", self.dataset, cache_dir=self.cache,
                             limit=limit, candidates=candidates)

    def test_all_query_text_is_validated_before_first_model_call(self):
        for query in ("x" * 8001, "㍿" * 2001, "\ud800"):
            with self.subTest(query_length=len(query)):
                self.dataset.write_text("\n".join(json.dumps(row) for row in [
                    {"query": "comet", "relevant": ["a.md"]},
                    {"query": query, "relevant": ["b.md"]},
                ]), encoding="utf-8")
                provider = CountingProvider()
                with self.assertRaisesRegex(ValueError, "line 2"):
                    evaluate(self.vault, self.dataset, cache_dir=self.cache, provider=provider)
                self.assertEqual(provider.calls, 0)

    def test_unicode_separators_in_json_strings_do_not_split_dataset_rows(self):
        self.write_dataset([
            {"query": "comet\u2028observations", "relevant": ["a.md"]},
            {"query": "comet\u2029observations", "relevant": ["b.md"]},
        ])
        report = evaluate(self.vault, self.dataset, cache_dir=self.cache)
        self.assertEqual(report["query_count"], 2)
        self.assertEqual([row["query"] for row in report["queries"]],
                         ["comet\u2028observations", "comet\u2029observations"])
        self.assertEqual(report["baseline"]["recall_at_k"], 1)


if __name__ == "__main__":
    unittest.main()
