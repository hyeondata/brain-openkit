"""Batch provider decisions preserve workflow results and atomic failure handling."""

import tempfile
import unittest
from pathlib import Path

from brain_openkit.providers import Decision, ProviderError
from brain_openkit.workflows import classify, search


class SequentialProvider:
    name = "fixture"

    def __init__(self, answers=()):
        self.answers = iter(answers)
        self.requests = []

    def choose(self, state, question, choices):
        self.requests.append((state, question, choices))
        choice = next(self.answers, next(iter(choices)))
        probabilities = {key: (0.9 if key == choice else 0.1) for key in choices}
        return Decision(choice, probabilities, None, "fixture", {}, 1.0)


class BatchProvider(SequentialProvider):
    def __init__(self, answers=(), *, bad_count=0, fail_batch=None):
        super().__init__(answers)
        self.batches = []
        self.bad_count = bad_count
        self.fail_batch = fail_batch

    def choose(self, state, question, choices):
        raise AssertionError("A batch-capable provider must use choose_many")

    def choose_many(self, requests):
        self.batches.append(requests)
        if len(self.batches) == self.fail_batch:
            raise ProviderError("batch_unavailable")
        decisions = [super(BatchProvider, self).choose(*request) for request in requests]
        if self.bad_count == -1:
            return decisions[:-1]
        if self.bad_count == 1:
            return decisions + decisions[:1]
        return decisions


class WorkflowBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.cache = self.root / "cache"
        (self.vault / "a.md").write_text("# Search\n\nSearch local notes.\n", encoding="utf-8")
        (self.vault / "b.md").write_text("# Search\n\nSearch remote notes.\n", encoding="utf-8")

    def test_search_batch_preserves_requests_scores_and_source(self):
        source = {p.name: p.read_bytes() for p in self.vault.iterdir()}
        sequential = SequentialProvider(["B", "A"])
        batch = BatchProvider(["B", "A"])
        expected = search(self.vault, "search", cache_dir=self.cache,
                          provider=sequential, prompt_language="ko")
        actual = search(self.vault, "search", cache_dir=self.cache,
                        provider=batch, prompt_language="ko")
        self.assertEqual(actual["rerank_status"], "complete")
        self.assertEqual(actual["results"], expected["results"])
        self.assertEqual(batch.requests, sequential.requests)
        self.assertEqual(len(batch.batches), 1)
        self.assertEqual(source, {p.name: p.read_bytes() for p in self.vault.iterdir()})

    def test_search_wrong_batch_count_restores_complete_bm25(self):
        baseline = search(self.vault, "search", cache_dir=self.cache)
        for bad_count in (-1, 1):
            with self.subTest(bad_count=bad_count):
                result = search(self.vault, "search", cache_dir=self.cache,
                                provider=BatchProvider(bad_count=bad_count))
                self.assertEqual(result["rerank_status"], "unavailable")
                self.assertEqual(result["results"], baseline["results"])
                self.assertIsNone(result["model"])

    def test_search_later_batch_failure_discards_earlier_decisions(self):
        for i in range(68):
            (self.vault / f"note-{i}.md").write_text(f"Search topic {i}.\n", encoding="utf-8")
        baseline = search(self.vault, "search", cache_dir=self.cache, candidates=100, limit=100)
        provider = BatchProvider(fail_batch=2)
        result = search(self.vault, "search", cache_dir=self.cache, provider=provider,
                        candidates=100, limit=100)
        self.assertEqual(result["candidate_count"], 70)
        self.assertEqual(result["rerank_status"], "unavailable")
        self.assertEqual(result["results"], baseline["results"])
        self.assertEqual([len(batch) for batch in provider.batches], [64, 6])

    def test_classification_batch_preserves_passage_category_and_tag_mapping(self):
        note = self.vault / "long.md"
        source = (("First topic. " * 80) + "\n\n" + ("Second topic. " * 80) + "\n").encode()
        note.write_bytes(source)
        taxonomy = {"categories": {"work": "Work", "study": "Study"},
                    "tags": {"local": "Local", "ai": "AI"}}
        answers = ["A", "A", "B", "B", "B", "A"]
        sequential, batch = SequentialProvider(answers), BatchProvider(answers)
        expected = classify(self.vault, note, taxonomy, sequential, prompt_language="ko")
        actual = classify(self.vault, note, taxonomy, batch, prompt_language="ko")
        self.assertEqual(actual, expected)
        self.assertEqual(actual["category_candidates"], ["study", "work"])
        self.assertEqual(actual["tags"], ["ai", "local"])
        self.assertEqual(batch.requests, sequential.requests)
        self.assertEqual(len(batch.batches), 1)
        self.assertEqual(note.read_bytes(), source)

    def test_classification_batches_are_bounded_across_passage_boundaries(self):
        note = self.vault / "long.md"
        note.write_text("\n\n".join("Passage. " * 120 for _ in range(3)), encoding="utf-8")
        taxonomy = {"categories": {"work": "Work", "study": "Study"},
                    "tags": {f"tag-{i}": f"Tag {i}" for i in range(30)}}
        provider = BatchProvider()
        result = classify(self.vault, note, taxonomy, provider)
        self.assertEqual(len(result["passages"]), 3)
        self.assertEqual(result["category"], "work")
        self.assertEqual(len(result["tags"]), 30)
        self.assertEqual([len(batch) for batch in provider.batches], [64, 29])

    def test_classification_wrong_batch_count_fails_without_modifying_note(self):
        note = self.vault / "a.md"
        source = note.read_bytes()
        for bad_count in (-1, 1):
            with self.subTest(bad_count=bad_count), self.assertRaises(ProviderError):
                classify(self.vault, note, {"categories": {"work": "Work"}},
                         BatchProvider(bad_count=bad_count))
            self.assertEqual(note.read_bytes(), source)


if __name__ == "__main__":
    unittest.main()
