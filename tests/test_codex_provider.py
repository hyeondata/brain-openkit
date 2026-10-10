"""Codex transport/decision contract without making cloud requests."""

import copy
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from brain_openkit.codex_provider import CodexProvider, CodexRunner, CodexRunResult
from brain_openkit.providers import ProviderError


def prediction():
    return {"decisions": [{"request_id": 0, "choice": "A", "confidence": 0.8,
                           "probabilities": [{"choice": "A", "probability": 0.9},
                                             {"choice": "B", "probability": 0.1}]}]}


class FakeRunner:
    model = "gpt-6-astra"
    reasoning_effort = "ultra"

    def __init__(self, data=None):
        self.data = prediction() if data is None else data
        self.calls = []

    def run(self, prompt, schema):
        self.calls.append((prompt, schema))
        return CodexRunResult(self.data, self.model, {"input_tokens": 30, "output_tokens": 20}, 100.0)


class CodexDecisionTests(unittest.TestCase):
    request = ("한국어 원문", "이 글의 주제는?", {"A": "백업", "B": "요리"})

    def test_decision_preserves_sources_and_marks_self_assessed_probabilities(self):
        runner = FakeRunner()
        result = CodexProvider(runner=runner).choose(*self.request)
        self.assertEqual(result.choice, "A")
        self.assertEqual(result.probabilities, {"A": 0.9, "B": 0.1})
        self.assertEqual(result.model, "gpt-6-astra")
        self.assertEqual(result.usage["confidence_kind"], "self_assessed_uncalibrated")
        self.assertIn("한국어 원문", runner.calls[0][0])
        self.assertIn("이 글의 주제는?", runner.calls[0][0])

    def test_batch_preserves_order_and_marks_shared_usage(self):
        body = prediction()
        body["decisions"].append({"request_id": 1, "choice": "yes", "confidence": 0.6,
                                   "probabilities": [{"choice": "yes", "probability": 0.7},
                                                     {"choice": "no", "probability": 0.3}]})
        runner = FakeRunner(body)
        result = CodexProvider(runner=runner).choose_many([
            self.request, ("두 번째", "관련?", {"yes": "관련 있음", "no": "관련 없음"})])
        self.assertEqual([item.choice for item in result], ["A", "yes"])
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(result[0].usage["batch_size"], 2)
        self.assertEqual(result[0].usage["usage_scope"], "shared_batch")
        self.assertEqual(sum(item.elapsed_ms for item in result), 100.0)

    def test_invalid_batch_cannot_return_partial_or_misordered_results(self):
        mutations = [lambda b: b["decisions"].clear(),
                     lambda b: b["decisions"].append(copy.deepcopy(b["decisions"][0])),
                     lambda b: b["decisions"][0].update(request_id=1),
                     lambda b: b["decisions"][0].update(choice="B"),
                     lambda b: b["decisions"][0].update(confidence=True),
                     lambda b: b["decisions"][0]["probabilities"].pop(),
                     lambda b: b["decisions"][0]["probabilities"][1].update(choice="A"),
                     lambda b: b["decisions"][0]["probabilities"][1].update(probability=0.5)]
        for mutate in mutations:
            body = prediction()
            mutate(body)
            with self.subTest(body=body), self.assertRaises(ProviderError):
                CodexProvider(runner=FakeRunner(body)).choose(*self.request)

    def test_invalid_input_never_calls_codex(self):
        runner = FakeRunner()
        provider = CodexProvider(runner=runner)
        cases = [("", "q", {"A": "a"}), ("s", "", {"A": "a"}), ("s", "q", {}),
                 ("s", "q", {"A\n": "a"}), ("x" * (64 * 1024 + 1), "q", {"A": "a"})]
        for item in cases:
            with self.subTest(item=str(item)[:40]), self.assertRaises(ProviderError):
                provider.choose(*item)
        with self.assertRaises(ProviderError):
            provider.choose_many([self.request] * 65)
        self.assertEqual(runner.calls, [])


@unittest.skipIf(os.name == "nt", "Executable fixture uses POSIX shebang")
class CodexTransportTests(unittest.TestCase):
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}},
              "required": ["ok"], "additionalProperties": False}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.executable = self.root / "fake-codex"

    def fixture(self, body):
        self.executable.write_text(f"#!{sys.executable}\nimport json, os, pathlib, sys, time\n" + body,
                                   encoding="utf-8")
        self.executable.chmod(0o700)
        return str(self.executable)

    def success_fixture(self, extra=""):
        return self.fixture('''
args = sys.argv[1:]
assert '--ignore-user-config' in args and '--ephemeral' in args
assert args[args.index('--sandbox') + 1] == 'read-only'
assert args[args.index('--model') + 1] == 'gpt-6-astra'
assert pathlib.Path.cwd() != pathlib.Path(__file__).parent
assert sys.stdin.read() == 'private prompt'
pathlib.Path(args[args.index('--output-last-message') + 1]).write_text('{"ok":true}')
print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 40, 'cached_input_tokens': 10, 'output_tokens': 5}}))
''' + extra)

    def test_actual_child_receives_isolated_command_and_returns_structured_result(self):
        result = CodexRunner(executable=self.success_fixture()).run("private prompt", self.schema)
        self.assertEqual(result.data, {"ok": True})
        self.assertEqual(result.usage["input_tokens"], 40)
        self.assertEqual(result.usage["output_tokens"], 5)
        self.assertGreater(result.elapsed_ms, 0)

    def test_failed_child_does_not_disclose_logs(self):
        executable = self.fixture("print('private note TOKEN'); sys.stderr.write('private credential'); sys.exit(7)")
        with self.assertRaisesRegex(ProviderError, "^codex_exit_7$"):
            CodexRunner(executable=executable).run("private prompt", self.schema)

    def test_timeout_terminates_instead_of_retries(self):
        executable = self.fixture("time.sleep(5)")
        with self.assertRaisesRegex(ProviderError, "^codex_timeout$"):
            CodexRunner(executable=executable, timeout=0.15).run("private prompt", self.schema)

    def test_large_prompt_reaches_slow_stdin_reader_completely_and_with_eof(self):
        executable = self.fixture('''
args = sys.argv[1:]
time.sleep(0.2)
raw = sys.stdin.buffer.read()
assert raw == ('한국어 긴 본문\\n' * 12000).encode('utf-8')
pathlib.Path(args[args.index('--output-last-message') + 1]).write_text('{"ok":true}')
print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 50000, 'output_tokens': 5}}))
''')
        result = CodexRunner(executable=executable, timeout=3).run("한국어 긴 본문\n" * 12000, self.schema)
        self.assertEqual(result.data, {"ok": True})
        self.assertEqual(result.usage["input_tokens"], 50000)

    def test_oversized_log_is_rejected(self):
        executable = self.fixture("sys.stdout.write('x' * (3 * 1024 * 1024)); sys.stdout.flush(); time.sleep(5)")
        with self.assertRaisesRegex(ProviderError, "^codex_output_too_large$"):
            CodexRunner(executable=executable, timeout=2).run("private prompt", self.schema)

    def test_unexpected_tool_call_rejects_output(self):
        executable = self.success_fixture("print(json.dumps({'type':'item.completed','item':{'type':'command_execution'}}))")
        with self.assertRaisesRegex(ProviderError, "^codex_unexpected_tool_use$"):
            CodexRunner(executable=executable).run("private prompt", self.schema)

    def test_schema_violation_is_not_a_success(self):
        executable = self.success_fixture()
        wrong = {"type": "object", "properties": {"ok": {"type": "string"}},
                 "required": ["ok"], "additionalProperties": False}
        with self.assertRaisesRegex(ProviderError, "^codex_invalid_response$"):
            CodexRunner(executable=executable).run("private prompt", wrong)

    def test_duplicate_json_and_nonfinite_final_values_are_rejected(self):
        for answer in ('{"ok":true,"ok":false}', '{"ok":NaN}', 'not-json'):
            executable = self.success_fixture(
                f"pathlib.Path(args[args.index('--output-last-message') + 1]).write_text({answer!r})")
            with self.subTest(answer=answer), self.assertRaisesRegex(ProviderError, "^codex_invalid_response$"):
                CodexRunner(executable=executable).run("private prompt", self.schema)

    def test_reported_model_downgrade_is_not_accepted(self):
        executable = self.success_fixture("print(json.dumps({'type':'thread.started','model':'gpt-other'}))")
        with self.assertRaisesRegex(ProviderError, "^invalid_model_route$"):
            CodexRunner(executable=executable).run("private prompt", self.schema)

    def test_authentication_and_routing_environment_overrides_are_not_inherited(self):
        executable = self.success_fixture('''
assert 'OPENAI_API_KEY' not in os.environ
assert 'OPENAI_BASE_URL' not in os.environ
assert 'PRIVATE_TOKEN' not in os.environ
assert 'NODE_OPTIONS' not in os.environ
assert 'features.plugins=false' in args and 'features.apps=false' in args
assert 'project_doc_max_bytes=0' in args and 'features.shell_tool=false' in args
''')
        with patch.dict(os.environ, {"OPENAI_API_KEY": "private-key", "OPENAI_BASE_URL": "https://example.com",
                                     "PRIVATE_TOKEN": "secret", "NODE_OPTIONS": "--require=untrusted.js"}):
            result = CodexRunner(executable=executable).run("private prompt", self.schema)
        self.assertEqual(result.data, {"ok": True})
        self.assertFalse(result.usage["routed_model_verified"])

    def test_health_does_not_infer_authentication_from_installed_binary(self):
        executable = self.fixture("assert sys.argv[1:] == ['--version']; print('codex-cli 0.162.0')")
        report = CodexRunner(executable=executable).health()
        self.assertEqual(report["version"], "0.162.0")
        self.assertFalse(report["authentication_verified"])
        self.assertFalse(report["inference_verified"])

    def test_relative_executable_path_is_resolved_before_isolating_child_directory(self):
        self.fixture("assert sys.argv[1:] == ['--version']; print('codex-cli 0.162.0')")
        with contextlib.chdir(self.root):
            report = CodexRunner(executable="./fake-codex").health()
        self.assertEqual(report["version"], "0.162.0")

    def test_failed_wrapper_does_not_leave_a_child_running(self):
        marker = self.root / "escaped-child.txt"
        child = ("import pathlib,time; time.sleep(0.35); "
                 f"pathlib.Path({str(marker)!r}).write_text('still running')")
        executable = self.fixture(f"import subprocess\nsubprocess.Popen([sys.executable, '-c', {child!r}])\nsys.exit(7)")
        with self.assertRaisesRegex(ProviderError, "^codex_exit_7$"):
            CodexRunner(executable=executable).run("private prompt", self.schema)
        import time
        time.sleep(0.6)
        self.assertFalse(marker.exists(), "A child outlived the failed Codex wrapper")

    def test_missing_binary_and_invalid_configuration_fail_without_inference(self):
        with self.assertRaisesRegex(ProviderError, "^codex_not_found$"):
            CodexRunner(executable=str(self.root / "missing")).run("private prompt", self.schema)
        for options in ({"model": "x --unexpected"}, {"timeout": 0}, {"timeout": True},
                        {"reasoning_effort": "unknown"}, {"executable": ""}):
            with self.subTest(options=options), self.assertRaisesRegex(ProviderError, "^invalid_codex_configuration$"):
                CodexRunner(**options)


if __name__ == "__main__":
    unittest.main()
