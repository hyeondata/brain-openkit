import tempfile
import unittest
from pathlib import Path

from brain_openkit.providers import Decision, ProviderError
from brain_openkit.workflows import classify, search, validate_taxonomy


class FixedProvider:
    def __init__(self, choices=None, fail_after=None):
        self.choices = iter(choices or [])
        self.fail_after = fail_after
        self.calls = 0

    def choose(self, state, question, choices):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise ProviderError("unavailable")
        choice = next(self.choices, next(iter(choices)))
        probabilities = {key: (0.9 if key == choice else 0.1 / max(1, len(choices)-1)) for key in choices}
        return Decision(choice, probabilities, 0.3, "test-double", {}, 1.0)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.cache = self.root / "cache"
        (self.vault / "a.md").write_text("# Local search\n\nSearch local notes with a local index.\n", encoding="utf-8")
        (self.vault / "b.md").write_text("# Other search\n\nSearch remote notes.\n", encoding="utf-8")

    def test_search_refreshes_deleted_notes_and_preserves_exact_source_slice(self):
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=repr(newline)):
                path = self.vault / "a.md"
                source = newline.join(["# Local 검색", "", "Search local notes.", ""]).encode("utf-8")
                path.write_bytes(source)
                result = search(self.vault, "local", cache_dir=self.cache)
                self.assertEqual(result["rerank_status"], "disabled")
                hit = result["results"][0]
                self.assertEqual(hit["path"], "a.md")
                lines = source.splitlines(keepends=True)
                self.assertEqual(hit["text"].encode("utf-8"), b"".join(lines[hit["start_line"]-1:hit["end_line"]]))
                self.assertEqual(path.read_bytes(), source)
                self.assertIsNone(hit["model_score"])
                path.unlink()
                self.assertEqual(search(self.vault, "local", cache_dir=self.cache)["results"], [])

    def test_partial_failure_rolls_back_entire_reranking(self):
        baseline = search(self.vault, "search", cache_dir=self.cache)
        result = search(self.vault, "search", cache_dir=self.cache, provider=FixedProvider(fail_after=1))
        self.assertEqual(result["rerank_status"], "unavailable")
        self.assertEqual(result["results"], baseline["results"])
        self.assertIn("unavailable", result["fallback_reason"])

    def test_model_reranks_then_deduplicates_notes(self):
        result = search(self.vault, "search", cache_dir=self.cache, provider=FixedProvider(), candidates=20)
        self.assertEqual(result["rerank_status"], "complete")
        self.assertEqual(len({hit["path"] for hit in result["results"]}), len(result["results"]))
        self.assertTrue(all(hit["model_score"] == 0.9 for hit in result["results"]))
        self.assertEqual(result["model"], "test-double")

    def test_empty_candidates_do_not_call_provider(self):
        provider = FixedProvider()
        result = search(self.vault, "missingzzzzz", cache_dir=self.cache, provider=provider)
        self.assertEqual(result["results"], [])
        self.assertEqual(provider.calls, 0)
        self.assertNotEqual(result["rerank_status"], "complete")

    def test_classification_conflicts_are_visible_and_tags_independent(self):
        note = self.vault / "one.md"
        original = "First topic. " * 80 + "\n\n" + "Second topic. " * 80 + "\n"
        note.write_text(original)
        taxonomy = {"categories": {"work": "Work", "study": "Study"}, "tags": {"local": "Local", "ai": "AI"}}
        result = classify(self.vault, note, taxonomy, FixedProvider(["A", "A", "B", "B", "B", "A"]))
        self.assertTrue(result["review_required"])
        self.assertIsNone(result["category"])
        self.assertEqual(result["tags"], ["ai", "local"])
        self.assertEqual(len(result["passages"]), 2)
        self.assertEqual(note.read_text(), original)

    def test_classification_does_not_fabricate_a_fallback(self):
        with self.assertRaises(ProviderError):
            classify(self.vault, self.vault / "a.md", {"categories": {"work": "Work"}}, FixedProvider(fail_after=0))

    def test_taxonomy_invalid_inputs(self):
        for bad in [None, {}, {"categories": []}, {"categories": {"": "Description"}},
                    {"categories": {"a": "A"}, "tags": {"b": 1}},
                    {"categories": {str(i): "x" for i in range(11)}}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_taxonomy(bad)

    def test_invalid_search_limits_and_blank_query(self):
        for options in [{"limit": 0}, {"candidates": 0}, {"limit": 5, "candidates": 2}]:
            with self.assertRaises(ValueError):
                search(self.vault, "local", cache_dir=self.cache, **options)
        with self.assertRaises(ValueError):
            search(self.vault, "  ", cache_dir=self.cache)


if __name__ == "__main__":
    unittest.main()
