"""Whole-note recommendations and local host validation preserve source notes."""

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from brain_openkit.cli import main
from brain_openkit.providers import ProviderError
from brain_openkit.workflows import classify


TAXONOMY = {"categories": {"frontend": "React interfaces", "testing": "Testing systems"},
            "tags": {"react": "React state", "testing": "Testing as the main topic"}}
SUGGESTION = {"category": "frontend", "tags": ["react"],
              "rationale": "React 상태 관리가 중심이며 테스트는 검증 예시입니다.", "review_required": False}


class DocumentProvider:
    name = "fixture"

    def __init__(self, suggestion=None):
        self.suggestion = copy.deepcopy(SUGGESTION if suggestion is None else suggestion)
        self.calls = []

    def choose(self, *args):
        raise AssertionError("Document classification must not classify individual passages")

    def classify_document(self, document, taxonomy, *, prompt_language):
        self.calls.append((document, taxonomy, prompt_language))
        return {"suggestion": self.suggestion, "model": "fixture", "usage": {}, "elapsed_ms": 1.0}


class DocumentClassificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.note = self.vault / "react.md"
        self.source = ("---\r\ntitle: React 상태\r\n---\r\n# React 상태\r\n\r\n"
                       + "상태는 렌더링을 결정한다. " * 100
                       + "\r\n\r\n## 테스트 예시\r\n부수적인 테스트 예시.\r\n").encode("utf-8")
        self.note.write_bytes(self.source)
        self.taxonomy = self.root / "taxonomy.json"
        self.taxonomy.write_text(json.dumps(TAXONOMY), encoding="utf-8")
        self.suggestions = self.root / "suggestions.json"
        self.suggestions.write_text(json.dumps(SUGGESTION, ensure_ascii=False), encoding="utf-8")

    def run_cli(self, *args, json_output=True):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            status = main([*args, "--vault", str(self.vault), *(["--json"] if json_output else [])])
        return status, json.loads(output.getvalue()) if json_output else output.getvalue()

    def test_document_provider_receives_entire_note_once_and_keeps_citations(self):
        provider = DocumentProvider()
        report = classify(self.vault, self.note, TAXONOMY, provider, prompt_language="ko")
        self.assertEqual(len(provider.calls), 1)
        document, taxonomy, language = provider.calls[0]
        self.assertEqual(document["text"].encode("utf-8"), self.source)
        self.assertEqual(document["path"], "react.md")
        self.assertEqual(taxonomy, TAXONOMY)
        self.assertEqual(language, "ko")
        self.assertEqual(report["classification_scope"], "document")
        self.assertEqual(report["category"], "frontend")
        self.assertEqual(report["tags"], ["react"])
        self.assertFalse(report["review_required"])
        self.assertGreater(len(report["passages"]), 1)
        lines = self.source.decode().splitlines(keepends=True)
        for passage in report["passages"]:
            self.assertEqual(passage["text"], "".join(lines[passage["start_line"] - 1:passage["end_line"]]))
            self.assertNotIn("category_decision", passage)
        self.assertEqual(self.note.read_bytes(), self.source)

    def test_invalid_document_results_fail_closed(self):
        cases = [{**SUGGESTION, "category": "unknown"}, {**SUGGESTION, "tags": ["unknown"]},
                 {**SUGGESTION, "tags": ["react", "react"]}, {**SUGGESTION, "tags": "react"},
                 {**SUGGESTION, "tags": [[]]}, {**SUGGESTION, "category": None},
                 {**SUGGESTION, "review_required": 1}, {**SUGGESTION, "rationale": " "},
                 {**SUGGESTION, "rationale": "x" * 2001}, {**SUGGESTION, "extra": True}]
        for suggestion in cases:
            with self.subTest(suggestion=suggestion), self.assertRaises(ProviderError):
                classify(self.vault, self.note, TAXONOMY, DocumentProvider(suggestion))
        self.assertEqual(self.note.read_bytes(), self.source)

    def test_provider_failure_does_not_fall_back_to_passage_or_change_source(self):
        provider = DocumentProvider()
        with patch.object(provider, "classify_document", side_effect=ProviderError("offline")):
            with self.assertRaisesRegex(ProviderError, "offline"):
                classify(self.vault, self.note, TAXONOMY, provider)
        self.assertEqual(self.note.read_bytes(), self.source)

    def test_host_validation_avoids_all_provider_construction_even_with_saved_config(self):
        config = self.root / "config.json"
        config.write_text(json.dumps({"provider": "jev"}), encoding="utf-8")
        with patch("brain_openkit.cli._provider", side_effect=AssertionError("No model call")):
            status, report = self.run_cli("classify", "react.md", "--taxonomy", str(self.taxonomy),
                                          "--suggestions", str(self.suggestions), "--config", str(config))
        self.assertEqual(status, 0, report)
        self.assertEqual(report["provider"], "host")
        self.assertIsNone(report["model"])
        self.assertEqual(report["category"], "frontend")
        self.assertEqual(report["rationale"], SUGGESTION["rationale"])
        self.assertFalse(report["note_modified"])
        self.assertEqual(self.note.read_bytes(), self.source)

    def test_host_validation_rejects_unknown_labels_duplicate_json_and_provider_conflict(self):
        with patch("brain_openkit.cli._provider", side_effect=AssertionError("No model call")):
            for body in ('null', '{"category":"frontend","category":"testing","tags":[],"rationale":"x","review_required":false}',
                         json.dumps({**SUGGESTION, "tags": ["invented"]})):
                self.suggestions.write_text(body, encoding="utf-8")
                status, report = self.run_cli("classify", "react.md", "--taxonomy", str(self.taxonomy),
                                              "--suggestions", str(self.suggestions))
                self.assertEqual(status, 2, report)
            self.suggestions.write_text(json.dumps(SUGGESTION), encoding="utf-8")
            status, report = self.run_cli("classify", "react.md", "--taxonomy", str(self.taxonomy),
                                          "--suggestions", str(self.suggestions), "--provider", "codex")
            self.assertEqual(status, 2, report)
        self.assertEqual(self.note.read_bytes(), self.source)

    def test_host_suggestion_can_preview_apply_and_undo_without_losing_body(self):
        status, report = self.run_cli("classify", "react.md", "--taxonomy", str(self.taxonomy),
                                      "--suggestions", str(self.suggestions))
        self.assertEqual(status, 0, report)
        plan_path = self.root / "plan.json"
        status, plan = self.run_cli("organize", "react.md", "--category", report["category"],
                                    "--tag", report["tags"][0], "--plan", str(plan_path))
        self.assertEqual(status, 0, plan)
        self.assertEqual(self.note.read_bytes(), self.source)
        status, applied = self.run_cli("apply", str(plan_path), "--approve", plan["id"])
        self.assertEqual(status, 0, applied)
        self.assertIn(b'category: "frontend"', self.note.read_bytes())
        self.assertIn(self.source.split(b"---\r\n", 2)[2], self.note.read_bytes())
        status, undone = self.run_cli("undo", applied["transaction_id"])
        self.assertEqual(status, 0, undone)
        self.assertEqual(self.note.read_bytes(), self.source)

    def test_document_text_output_preserves_model_review_flag_without_fake_probabilities(self):
        self.suggestions.write_text(json.dumps({**SUGGESTION, "review_required": True}), encoding="utf-8")
        status, text = self.run_cli("classify", "react.md", "--taxonomy", str(self.taxonomy),
                                    "--suggestions", str(self.suggestions), json_output=False)
        self.assertEqual(status, 0, text)
        self.assertIn("frontend", text)
        self.assertIn("Review required: yes", text)
        self.assertIn(SUGGESTION["rationale"], text)
        self.assertNotIn("probabilities", text)


if __name__ == "__main__":
    unittest.main()
