"""Codex CLI settings and real workflow output, with cloud transport stubbed."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from brain_openkit.cli import main


class CodexCLITests(unittest.TestCase):
    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main([*args, "--json"])
        return code, json.loads(output.getvalue())

    def test_codex_is_selectable_with_distinct_timeout_and_reasoning(self):
        from brain_openkit.codex_provider import CodexRunResult
        captured = []

        def run(runner, prompt, schema):
            captured.append((runner.model, runner.reasoning_effort, runner.timeout))
            return CodexRunResult({"decisions": [{"request_id": 0, "choice": "A", "confidence": 0.8,
                "probabilities": [{"choice": "A", "probability": 0.9}, {"choice": "B", "probability": 0.1}]}]},
                runner.model, {}, 100.0)

        with patch("brain_openkit.codex_provider.CodexProvider.health", return_value={"status": "available"}), \
             patch("brain_openkit.codex_provider.CodexRunner.run", run):
            code, report = self.run_cli("doctor", "--provider", "codex", "--probe", "--codex-timeout", "450",
                                       "--reasoning-effort", "high")
        self.assertEqual(code, 0, report)
        self.assertEqual(captured, [("gpt-6-astra", "high", 450.0)])
        self.assertTrue(report["inference_verified"])

    def test_provider_specific_config_and_model_override(self):
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / "config.json"
            config.write_text(json.dumps({"provider": "codex", "codex_model": "gpt-6-astra",
                                           "codex_timeout": 500, "reasoning_effort": "ultra"}))
            from brain_openkit.cli import _parser, _provider, _settings
            provider = _provider(_settings(_parser().parse_args(["doctor", "--config", str(config)])))
        self.assertEqual(provider.model, "gpt-6-astra")
        self.assertEqual(provider.runner.timeout, 500.0)
        self.assertEqual(provider.runner.reasoning_effort, "ultra")

    def test_codex_rejects_http_endpoint_instead_of_silently_ignoring_it(self):
        code, report = self.run_cli("doctor", "--provider", "codex", "--base-url", "https://example.com")
        self.assertEqual(code, 2)
        self.assertIn("base_url", report["error"]["message"])


if __name__ == "__main__":
    unittest.main()
