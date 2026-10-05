"""Provider switching at the CLI boundary using real local HTTP fixtures."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from brain_openkit.cli import main
from test_providers import prediction as laya_prediction, server
from test_jev import prediction as jev_prediction


CATALOG = {"models": [{"name": "kev-latest", "description": "Kev local decision model",
                       "release_date": "2026-09-17"}]}


class KevCLITests(unittest.TestCase):
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

    def test_kev_doctor_needs_no_key_and_does_not_infer_without_probe(self):
        with patch.dict(os.environ, {}, clear=True), server([{"body": CATALOG}]) as (url, requests):
            code, report = self.run_cli("doctor", "--provider", "kev", "--base-url", url)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["provider"], "kev")
        self.assertFalse(report["inference_verified"])
        self.assertEqual([(r[0], r[1]) for r in requests], [("GET", "/v1/models")])
        self.assertNotIn("Authorization", requests[0][2])

    def test_switching_preserves_each_provider_endpoint_model_and_credentials(self):
        kev_answer = jev_prediction()
        kev_answer["model"] = "kev-latest"
        with server([{"body": CATALOG}, {"body": kev_answer}]) as (kev_url, kev_requests), \
                server([{"body": {"status": "ok"}}, {"body": laya_prediction()}]) as (laya_url, laya_requests), \
                server([{"body": CATALOG}, {"body": jev_prediction()}]) as (jev_url, jev_requests):
            config = self.root / "providers.json"
            config.write_text(json.dumps({"provider": "kev", "kev_base_url": kev_url,
                                          "kev_model": "kev-test", "laya_base_url": laya_url,
                                          "jev_base_url": jev_url, "jev_model": "jev-test"}), encoding="utf-8")
            with patch.dict(os.environ, {"KEV_API_KEY": "kev-key", "LAYA_API_KEY": "laya-key",
                                         "TYPESAFE_API_KEY": "jev-key"}, clear=True):
                for provider in ("kev", "laya", "jev"):
                    code, report = self.run_cli("doctor", "--config", str(config),
                                               "--provider", provider, "--probe")
                    self.assertEqual(code, 0, report)
                    self.assertEqual(report["provider"], provider)
                    self.assertTrue(report["inference_verified"])
        for requests, key, model in ((kev_requests, "kev-key", "kev-test"),
                                     (laya_requests, "laya-key", "multilingual"),
                                     (jev_requests, "jev-key", "jev-test")):
            self.assertEqual(len(requests), 2)
            self.assertEqual(requests[1][2]["Authorization"], "Bearer " + key)
            self.assertEqual(json.loads(requests[1][3])["model"], model)

    def test_explicit_model_and_endpoint_override_selected_provider_configuration(self):
        config = self.root / "providers.json"
        config.write_text(json.dumps({"provider": "kev", "kev_base_url": "http://127.0.0.1:1",
                                      "kev_model": "configured-alias"}), encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True), \
                server([{"body": CATALOG}, {"body": jev_prediction()}]) as (url, requests):
            code, report = self.run_cli("doctor", "--config", str(config), "--base-url", url,
                                       "--model", "kev-0.5b", "--probe")
        self.assertEqual(code, 0, report)
        self.assertEqual(json.loads(requests[1][3])["model"], "kev-0.5b")

    def test_invalid_kev_configuration_fails_before_connecting(self):
        config = self.root / "providers.json"
        for item in ({"kev_base_url": 42}, {"kev_model": ""}, {"model": []}):
            with self.subTest(item=item):
                config.write_text(json.dumps({"provider": "kev", **item}), encoding="utf-8")
                code, report = self.run_cli("doctor", "--config", str(config))
                self.assertEqual(code, 2, report)
                self.assertIn("error", report)


if __name__ == "__main__":
    unittest.main()
