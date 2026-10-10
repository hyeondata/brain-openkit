"""Exercise the CLI against local fixtures, without downloading model weights."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from brain_openkit.cli import main
from test_providers import server


MODEL = "mmetamong/ko-decision-roberta-large"
REVISION = "dfd606fff30d52963c0073659ff9a8f6bf1fce6d"


def catalog(model=MODEL):
    return {"models": [{"name": model, "description": "Korean choice model",
                        "release_date": "2026-10-05", "revision": REVISION,
                        "max_length": 512, "truncate_states": False}]}


def prediction(model=MODEL):
    return {"model": model, "model_revision": REVISION,
            "answers": {"decision": {"type": "choice", "choice": "A",
                        "probabilities": {"A": 0.8, "B": 0.2}, "confidence": 0.6}},
            "usage": {"input_tokens": 80, "output_tokens": 0, "state_tokens": 30,
                      "state_tokens_dropped": 0, "truncated": False,
                      "truncated_questions": [], "max_pair_tokens": 40,
                      "model_revision": REVISION}}


class KoDecisionCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main([*args, "--json"])
        self.assertEqual(errors.getvalue(), "")
        return code, json.loads(output.getvalue())

    def test_doctor_checks_catalog_without_inference_or_key(self):
        with patch.dict(os.environ, {}, clear=True), server([{"body": catalog()}]) as (url, requests):
            code, report = self.run_cli("doctor", "--provider", "ko-decision", "--base-url", url)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["provider"], "ko-decision")
        self.assertFalse(report["inference_verified"])
        self.assertEqual([(r[0], r[1]) for r in requests], [("GET", "/v1/models")])
        self.assertNotIn("Authorization", requests[0][2])

    def test_switch_uses_ko_configuration_and_its_own_optional_key(self):
        config = self.root / "config.json"
        with server([{"body": catalog()}, {"body": prediction()}]) as (url, requests):
            config.write_text(json.dumps({"provider": "kev", "ko_decision_base_url": url,
                                          "ko_decision_model": MODEL}), encoding="utf-8")
            with patch.dict(os.environ, {"KO_DECISION_API_KEY": "ko-key", "KEV_API_KEY": "wrong-key"}, clear=True):
                code, report = self.run_cli("doctor", "--config", str(config), "--provider", "ko-decision", "--probe")
        self.assertEqual(code, 0, report)
        self.assertTrue(report["inference_verified"])
        self.assertEqual(report["probe"]["usage"]["model_revision"], REVISION)
        self.assertEqual(requests[1][2]["Authorization"], "Bearer ko-key")
        self.assertEqual(json.loads(requests[1][3])["model"], MODEL)

    def test_explicit_endpoint_and_model_override_configured_alias(self):
        config = self.root / "config.json"
        config.write_text(json.dumps({"provider": "ko-decision", "ko_decision_base_url": "http://127.0.0.1:1",
                                      "ko_decision_model": "wrong-alias"}), encoding="utf-8")
        with server([{"body": catalog("ko-test")}, {"body": prediction("ko-test")}]) as (url, requests):
            code, report = self.run_cli("doctor", "--config", str(config), "--base-url", url,
                                       "--model", "ko-test", "--probe")
        self.assertEqual(code, 0, report)
        self.assertEqual(report["probe"]["model"], "ko-test")
        self.assertEqual(json.loads(requests[1][3])["model"], "ko-test")

    def test_invalid_configuration_fails_without_connecting(self):
        config = self.root / "config.json"
        for item in ({"ko_decision_base_url": 42}, {"ko_decision_model": ""}):
            with self.subTest(item=item):
                config.write_text(json.dumps({"provider": "ko-decision", **item}), encoding="utf-8")
                code, report = self.run_cli("doctor", "--config", str(config))
                self.assertEqual(code, 2, report)
                self.assertIn("ko_decision_", report["error"]["message"])

    def test_classification_and_search_fallback_preserve_notes(self):
        vault = self.root / "vault"
        vault.mkdir()
        note = vault / "note.md"
        original = "# 백업\n\n옵시디언 노트를 외장 디스크에 백업한다.\n".encode()
        note.write_bytes(original)
        taxonomy = self.root / "taxonomy.json"
        taxonomy.write_text('{"categories":{"software":"소프트웨어 기록","cooking":"요리 기록"},"tags":{"backup":"백업"}}', encoding="utf-8")
        common = ["--vault", str(vault), "--cache-dir", str(self.root / "cache")]
        code, baseline = self.run_cli("search", "백업", *common)
        self.assertEqual(code, 0, baseline)
        oversized = prediction()
        oversized["usage"].update(truncated=True, state_tokens_dropped=4)
        with server([{"body": prediction()}, {"body": prediction()}, {"body": oversized}]) as (url, _):
            selected = ["--provider", "ko-decision", "--base-url", url, *common]
            code, classified = self.run_cli("classify", "note.md", "--taxonomy", str(taxonomy), *selected)
            self.assertEqual(code, 0, classified)
            self.assertEqual(classified["category"], "software")
            self.assertEqual(classified["tags"], ["backup"])
            self.assertFalse(classified["note_modified"])
            code, found = self.run_cli("search", "백업", *selected)
        self.assertEqual(code, 0, found)
        self.assertEqual(found["rerank_status"], "unavailable")
        self.assertEqual(found["fallback_reason"], "truncated_input")
        self.assertEqual([r["path"] for r in found["results"]], [r["path"] for r in baseline["results"]])
        self.assertTrue(all(r["decision"] is None for r in found["results"]))
        self.assertEqual(note.read_bytes(), original)

    def test_probe_does_not_report_success_for_wrong_model(self):
        body = prediction("unexpected-model")
        with server([{"body": catalog()}, {"body": body}]) as (url, _):
            code, report = self.run_cli("doctor", "--provider", "ko-decision", "--base-url", url, "--probe")
        self.assertEqual(code, 2, report)
        self.assertEqual(report["error"]["message"], "invalid_model_route")


if __name__ == "__main__":
    unittest.main()
