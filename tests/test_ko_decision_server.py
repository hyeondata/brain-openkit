"""Local runtime contracts without downloading a model or importing PyTorch."""

from pathlib import Path
from contextlib import contextmanager
from http.client import HTTPConnection
import io
import json
import math
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from brain_openkit import ko_decision_server as runtime


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts/serve-ko-decision.py"


def request(state="원문 두 단어", criteria=None):
    return {
        "model": "mmetamong/ko-decision-roberta-large", "state": state,
        "questions": {"decision": {"type": "choice", "instructions": "분류하세요",
                                    "criteria": criteria or {"A": "과학", "B": "문학"}}},
    }


class WordTokenizer:
    """Deterministic token IDs make inference-boundary inputs observable."""

    def encode(self, text, add_special_tokens=False):
        if add_special_tokens:
            raise AssertionError("State counts must omit special tokens")
        return [10] * len(text.split())

    def __call__(self, texts, states, **kwargs):
        if kwargs != {"padding": False, "truncation": False, "return_token_type_ids": False}:
            raise AssertionError("The runtime must not silently truncate or request token types")
        # Two question tokens + two fake separator tokens + state tokens.
        ids = [[1, *([20] * len(text.split())), 2, *self.encode(state)]
               for text, state in zip(texts, states)]
        return {"input_ids": ids, "attention_mask": [[1] * len(row) for row in ids]}


class RuntimeDecisionTests(unittest.TestCase):
    def engine(self, score_batch, **kwargs):
        self.assertTrue(hasattr(runtime, "DecisionEngine"), "Missing bounded decision runtime")
        return runtime.DecisionEngine(WordTokenizer(), score_batch, **kwargs)

    def test_logits_become_complete_distribution_and_token_usage(self):
        engine = self.engine(lambda batch: [0.0, math.log(3)])
        response = engine.decide(request())
        answer = response["answers"]["decision"]
        self.assertEqual(answer["choice"], "B")
        self.assertAlmostEqual(answer["probabilities"]["A"], 0.25)
        self.assertAlmostEqual(answer["probabilities"]["B"], 0.75)
        self.assertAlmostEqual(answer["confidence"], 0.5)
        self.assertEqual(response["model"], "mmetamong/ko-decision-roberta-large")
        self.assertEqual(response["model_revision"], "dfd606fff30d52963c0073659ff9a8f6bf1fce6d")
        self.assertEqual(response["usage"], {
            "input_tokens": 14, "output_tokens": 0, "state_tokens": 3,
            "state_tokens_dropped": 0, "truncated": False, "truncated_questions": [],
            "max_pair_tokens": 7, "model_revision": "dfd606fff30d52963c0073659ff9a8f6bf1fce6d",
        })

    def test_option_ids_do_not_enter_the_model_input(self):
        class InspectTokenizer(WordTokenizer):
            def __call__(self, texts, states, **kwargs):
                if texts != ["분류하세요 과학", "분류하세요 문학"] or states != ["원문 두 단어"] * 2:
                    raise AssertionError("Wrong instruction/option/state pair construction")
                return super().__call__(texts, states, **kwargs)

        engine = self.engine(lambda batch: [0.0, 0.0])
        engine.tokenizer = InspectTokenizer()
        response = engine.decide(request(criteria={"SECRET_ID": "과학", "OTHER_ID": "문학"}))
        self.assertEqual(response["answers"]["decision"]["probabilities"], {"SECRET_ID": 0.5, "OTHER_ID": 0.5})

    def test_batching_keeps_choice_order_and_single_choice_has_full_confidence(self):
        engine = self.engine(lambda batch: [float(row.count(20)) for row in batch["input_ids"]], batch_size=1)
        response = engine.decide(request(criteria={"A": "하나", "B": "둘 셋", "C": "넷 다섯 여섯"}))
        self.assertEqual(response["answers"]["decision"]["choice"], "C")
        single = engine.decide(request(criteria={"only": "유일한 항목"}))["answers"]["decision"]
        self.assertEqual(single["probabilities"], {"only": 1.0})
        self.assertEqual(single["confidence"], 1.0)

    def test_512_token_boundary_rejects_long_pairs_before_inference(self):
        engine = self.engine(lambda batch: [0.0] * len(batch["input_ids"]))
        accepted = engine.decide(request(state=" ".join(["단어"] * 508)))
        self.assertEqual(accepted["usage"]["max_pair_tokens"], 512)

        def must_not_score(batch):
            self.fail("Overlong input reached the model")

        engine = self.engine(must_not_score)
        with self.assertRaises(runtime.DecisionRequestError) as caught:
            engine.decide(request(state=" ".join(["단어"] * 509)))
        self.assertEqual((caught.exception.status, caught.exception.code), (413, "input_too_long"))

    def test_invalid_model_or_request_shape_never_reaches_inference(self):
        bad = [[], {}, request(), request(), request(), request(), request(), request()]
        bad[2]["model"] = "different-model"
        bad[3]["questions"]["decision"]["type"] = "noul"
        bad[4]["questions"]["decision"]["criteria"] = {str(i): "항목" for i in range(11)}
        bad[5]["questions"]["decision"]["criteria"] = {"A\nB": "항목"}
        bad[6]["state"] = " "
        bad[7]["questions"]["extra"] = bad[7]["questions"]["decision"]
        engine = self.engine(lambda batch: self.fail("Invalid request reached the model"))
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(runtime.DecisionRequestError):
                engine.decide(payload)

    def test_nonfinite_or_wrong_number_of_logits_is_not_a_valid_prediction(self):
        for scores in ([0.0], [float("nan"), 0.0], [float("inf"), 0.0]):
            engine = self.engine(lambda batch, scores=scores: scores)
            with self.subTest(scores=scores), self.assertRaises(RuntimeError):
                engine.decide(request())


class RuntimeStartupTests(unittest.TestCase):
    def test_help_runs_without_optional_dependencies_or_model_downloads(self):
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(LAUNCHER), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--local-files-only", result.stdout)

    def test_import_does_not_load_inference_libraries(self):
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-c",
             "import sys; sys.path.insert(0, sys.argv[1]); "
             "import brain_openkit.ko_decision_server; "
             "assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules",
             str(ROOT / "src")], capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_non_loopback_binding_and_invalid_limits_fail_before_loading(self):
        for args in (("--host", "0.0.0.0"), ("--host", "example.com"), ("--port", "0"),
                     ("--threads", "0"), ("--batch-size", "11")):
            result = subprocess.run([sys.executable, "-I", "-S", str(LAUNCHER), *args],
                                    capture_output=True, text=True, timeout=10)
            with self.subTest(args=args):
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)

    def test_missing_optional_runtime_is_an_actionable_safe_error(self):
        result = subprocess.run([sys.executable, "-I", "-S", str(LAUNCHER)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("ko-decision", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


@contextmanager
def running_server(engine):
    httpd = runtime.create_server(engine, port=0)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield httpd.server_port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


class RuntimeHTTPTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(runtime, "create_server"), "Missing loopback HTTP runtime")
        self.engine = runtime.DecisionEngine(WordTokenizer(), lambda batch: [0.0] * len(batch["input_ids"]))

    def exchange(self, port, method="POST", path="/v1/systemone", body=None, headers=None):
        if body is None and method == "POST":
            body = json.dumps(request(), ensure_ascii=False).encode()
        connection = HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            connection.request(method, path, body, headers or {"Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), json.loads(response.read())
        finally:
            connection.close()

    def test_models_and_choice_work_over_real_loopback_http(self):
        with running_server(self.engine) as port:
            status, _, health = self.exchange(port, "GET", "/v1/models")
            self.assertEqual(status, 200)
            model = health["models"][0]
            self.assertEqual((model["name"], model["revision"], model["max_length"], model["truncate_states"]),
                             ("mmetamong/ko-decision-roberta-large", "dfd606fff30d52963c0073659ff9a8f6bf1fce6d", 512, False))
            status, _, payload = self.exchange(port)
            self.assertEqual(status, 200)
            self.assertEqual(payload["answers"]["decision"]["probabilities"], {"A": 0.5, "B": 0.5})

    def test_long_body_or_token_overflow_returns_413_without_echoing_source(self):
        with running_server(self.engine) as port:
            for body in (b"secret" * 12000, json.dumps(request(state="secret " * 509)).encode()):
                status, _, payload = self.exchange(port, body=body)
                self.assertEqual(status, 413)
                self.assertNotIn("secret", json.dumps(payload))

    def test_malformed_json_duplicate_keys_and_browser_requests_are_rejected(self):
        cases = [(b'{"state":"one","state":"two"}', {}, 400), (b"not json", {}, 400),
                 (b'{"x":NaN}', {}, 400), (b"{}", {"Content-Type": "text/plain"}, 415),
                 (b"{}", {"Content-Type": "application/json", "Origin": "https://example.com"}, 403)]
        with running_server(self.engine) as port:
            for body, headers, expected in cases:
                with self.subTest(body=body, headers=headers):
                    status, response_headers, _ = self.exchange(port, body=body, headers=headers)
                    self.assertEqual(status, expected)
                    self.assertNotIn("Access-Control-Allow-Origin", response_headers)

    def test_unbounded_decimal_content_length_returns_safe_error(self):
        with running_server(self.engine) as port:
            status, _, payload = self.exchange(port, body=b"{}", headers={
                "Content-Type": "application/json", "Content-Length": "9" * 5000,
            })
        self.assertEqual(status, 400)
        self.assertEqual(payload, {"error": {"code": "invalid_content_length"}})

    def test_inference_exceptions_and_urls_never_leak_note_text_to_body_or_logs(self):
        self.engine.score_batch = lambda batch: (_ for _ in ()).throw(RuntimeError("secret source note"))
        output = io.StringIO()
        with patch("sys.stderr", output), running_server(self.engine) as port:
            status, _, payload = self.exchange(port)
            self.assertEqual((status, payload), (500, {"error": {"code": "inference_failed"}}))
            status, _, payload = self.exchange(port, "GET", "/secret-source-note")
            self.assertEqual((status, payload), (404, {"error": {"code": "not_found"}}))
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
