"""Exercise the adapter against an actual local HTTP server, without model weights."""

import json
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from brain_openkit.providers import Decision, LayaProvider, ProviderError


def prediction():
    return {
        "model": "laya-rl-agent",
        "answers": {"decision": {
            "type": "choice", "choice": "A",
            "probabilities": {"A": 0.8, "B": 0.2},
            "confidence": 0.2781, "answer_confidence": 0.8,
            "action": {"act_probability": 0.9},
        }},
        "usage": {
            "input_tokens": 80, "output_tokens": 0,
            "state_tokens": 30, "state_tokens_dropped": 0,
            "truncated": False, "truncated_questions": [],
        },
        "routing": {"model": "multilingual", "repo": "convaiinnovations/laya-multilingual"},
    }


@contextmanager
def server(responses):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.reply()

        def do_POST(self):
            self.reply()

        def reply(self):
            length = int(self.headers.get("Content-Length", 0))
            requests.append((self.command, self.path, dict(self.headers), self.rfile.read(length)))
            item = responses[min(len(requests) - 1, len(responses) - 1)]
            if item.get("delay"):
                time.sleep(item["delay"])
            body = item.get("body", prediction())
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(item.get("status", 200))
            self.send_header("Content-Type", item.get("content_type", "application/json"))
            self.send_header("Content-Length", str(len(body)))
            for key, value in item.get("headers", {}).items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", requests
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.choices = {"A": "관련 있음", "B": "관련 없음"}

    def choose(self, provider):
        return provider.choose("한국어 원문", "관련된 노트인가?", self.choices)

    def test_real_wire_payload_and_confidence_fields(self):
        with server([{}]) as (url, requests):
            result = self.choose(LayaProvider(url + "/", api_key="test-key"))
        method, path, headers, body = requests[0]
        self.assertEqual((method, path), ("POST", "/v1/systemone"))
        self.assertEqual(headers["Authorization"], "Bearer test-key")
        self.assertEqual(json.loads(body), {
            "model": "multilingual", "state": "한국어 원문",
            "questions": {"decision": {"type": "choice", "instructions": "관련된 노트인가?",
                                        "criteria": {"A": "관련 있음", "B": "관련 없음"}}},
            "max_len": 1024, "head_max_len": 256,
        })
        self.assertIn("한국어 원문".encode(), body)
        self.assertIsInstance(result, Decision)
        self.assertEqual(result.choice, "A")
        self.assertEqual(result.probabilities, {"A": 0.8, "B": 0.2})
        self.assertEqual(result.confidence, 0.2781)
        self.assertEqual(result.answer_confidence, 0.8)
        self.assertEqual(result.model, "convaiinnovations/laya-multilingual")
        self.assertEqual(result.usage, prediction()["usage"])
        self.assertGreaterEqual(result.elapsed_ms, 0)

    def test_health_only_calls_get_without_prediction(self):
        with server([{"body": {"status": "ok"}}]) as (url, requests):
            self.assertEqual(LayaProvider(url).health(), {"status": "ok"})
        self.assertEqual([(x[0], x[1], x[3]) for x in requests], [("GET", "/health", b"")])
        self.assertNotIn("Authorization", requests[0][2])

    def test_single_label_and_optional_answer_confidence(self):
        body = prediction()
        body["answers"]["decision"].update(probabilities={"분류": 1}, choice="분류", confidence=1)
        del body["answers"]["decision"]["answer_confidence"]
        del body["routing"]["repo"]
        with server([{"body": body}]) as (url, _):
            decision = LayaProvider(url, max_tokens=8192).choose("노트", "종류?", {"분류": "유일한 분류"})
        self.assertEqual(decision.choice, "분류")
        self.assertEqual(decision.model, "multilingual")
        self.assertIsNone(decision.answer_confidence)

    def test_configuration_is_rejected_before_io(self):
        invalid = [
            {"base_url": "ftp://localhost"}, {"base_url": "http://"},
            {"base_url": "http://user:secret@localhost"},
            {"base_url": "http://localhost?key=secret"}, {"base_url": "http://localhost/#fragment"},
            {"base_url": "http://localhost:99999"}, {"base_url": "http://local host"},
            {"timeout": 0}, {"timeout": -1}, {"timeout": float("nan")},
            {"timeout": float("inf")}, {"timeout": True}, {"timeout": "1"},
            {"timeout": 10 ** 1000},
            {"max_tokens": 0}, {"max_tokens": 8193}, {"max_tokens": 1.5}, {"max_tokens": True},
            {"api_key": "secret\nInjected: header"}, {"api_key": 4},
        ]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ProviderError):
                LayaProvider(**kwargs)

    def test_input_shape_and_utf8_size_bound_before_transmission(self):
        with server([{}]) as (url, requests):
            provider = LayaProvider(url)
            for state, question, choices in [
                (None, "q", self.choices), ("", "q", self.choices),
                ("s", "", self.choices), ("s", "q", {}),
                ("s", "q", {str(i): "label" for i in range(11)}),
                ("s", "q", {1: "x"}), ("s", "q", {"": "x"}),
                ("s", "q", {"A": {"description": "x"}}),
                ("s", "q", {"A\nB": "x"}), ("\ud800", "q", self.choices),
                ("한" * 23000, "q", self.choices),
            ]:
                with self.subTest(state_type=type(state), count=len(choices)), self.assertRaises(ProviderError):
                    provider.choose(state, question, choices)
        self.assertEqual(requests, [])

    def test_http_permanent_errors_hide_server_body_and_do_not_retry(self):
        for status in (400, 401, 403, 422, 500):
            with self.subTest(status=status), server([{"status": status, "body": {"detail": "secret note and api key"}}]) as (url, requests):
                with self.assertRaises(ProviderError) as error:
                    self.choose(LayaProvider(url))
                self.assertIn(str(status), str(error.exception))
                self.assertNotIn("secret", str(error.exception))
                self.assertEqual(len(requests), 1)

    def test_transient_errors_retry_once_then_succeed(self):
        for status in (502, 503, 504):
            with self.subTest(status=status), server([{"status": status, "headers": {"Retry-After": "99999"}}, {}]) as (url, requests):
                self.assertEqual(self.choose(LayaProvider(url)).choice, "A")
                self.assertEqual(len(requests), 2)

    def test_persistent_transient_error_stops_after_second_attempt(self):
        with server([{"status": 503}]) as (url, requests):
            with self.assertRaises(ProviderError):
                self.choose(LayaProvider(url))
            self.assertEqual(len(requests), 2)

    def test_timeout_is_bounded_and_does_not_retry(self):
        with server([{"delay": 0.15}]) as (url, requests):
            started = time.monotonic()
            with self.assertRaises(ProviderError):
                self.choose(LayaProvider(url, timeout=0.025))
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertEqual(len(requests), 1)

    def test_redirect_does_not_send_the_request_or_key_to_destination(self):
        with server([{}]) as (destination, leaked):
            for status in (301, 302, 303, 307, 308):
                with self.subTest(status=status), server([{"status": status, "headers": {"Location": destination}}]) as (url, requests):
                    with self.assertRaises(ProviderError):
                        self.choose(LayaProvider(url, api_key="sensitive-key"))
                    self.assertEqual(len(requests), 1)
            self.assertEqual(leaked, [])

    def test_malformed_or_oversized_response_is_rejected(self):
        cases = [b"{broken", b"\xff", b"x" * (1024 * 1024), b"[]",
                 b'{"status":"ok","status":"bad"}',
                 json.dumps(prediction()).replace('0.2781', 'NaN').encode()]
        for body in cases:
            with self.subTest(size=len(body)), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(LayaProvider(url))

    def test_health_validates_json_and_status(self):
        for body in ({}, {"status": "error"}, [], {"status": True}):
            with self.subTest(body=body), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                LayaProvider(url).health()

    def test_wrong_route_or_incomplete_answer_is_rejected(self):
        mutations = [
            lambda b: b.pop("model"),
            lambda b: b.update(model=7),
            lambda b: b.pop("routing"),
            lambda b: b["routing"].update(model="english"),
            lambda b: b["routing"].update(repo=3),
            lambda b: b["answers"].pop("decision"),
            lambda b: b["answers"]["decision"].update(type="noul"),
            lambda b: b["answers"]["decision"].update(choice="unknown"),
            lambda b: b["answers"]["decision"].update(choice="B"),
            lambda b: b["answers"]["decision"].update(confidence=True),
            lambda b: b["answers"]["decision"].update(answer_confidence=-0.1),
        ]
        for mutate in mutations:
            body = prediction()
            mutate(body)
            with self.subTest(body=body), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(LayaProvider(url))

    def test_server_abstention_is_not_reported_as_a_completed_decision(self):
        for fields in (
            {"low_confidence": True},
            {"abstention": "abstained", "abstention_threshold": 0.9},
            {"abstention": "unevaluated", "abstention_threshold": 0.9},
            {"abstention": "passed"},
            {"abstention": "passed", "abstention_threshold": True},
        ):
            body = prediction()
            body["answers"]["decision"].update(fields)
            with self.subTest(fields=fields), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(LayaProvider(url))

    def test_probabilities_are_a_complete_finite_normalized_distribution(self):
        cases = [{"A": 0.8}, {"A": 0.8, "B": 0.2, "C": 0.0},
                 {"A": True, "B": 0}, {"A": 0.8, "B": "0.2"},
                 {"A": 1.1, "B": -0.1}, {"A": 0.8, "B": 0.8},
                 {"A": 10 ** 1000, "B": 0},
                 {"A": float("inf"), "B": 0}, {"A": float("nan"), "B": 0}]
        for probabilities in cases:
            body = prediction()
            body["answers"]["decision"]["probabilities"] = probabilities
            with self.subTest(probabilities=probabilities), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(LayaProvider(url))

    def test_four_decimal_rounding_does_not_reject_a_distribution(self):
        body = prediction()
        body["answers"]["decision"]["probabilities"] = {"A": 0.3333, "B": 0.3333, "C": 0.3333}
        with server([{"body": body}]) as (url, _):
            result = LayaProvider(url).choose("s", "q", {"A": "one", "B": "two", "C": "three"})
        self.assertEqual(result.choice, "A")

    def test_every_truncation_indicator_fails_closed(self):
        mutations = [
            lambda u: u.update(truncated=True),
            lambda u: u.update(state_tokens_dropped=1),
            lambda u: u.update(truncated_questions=["decision"]),
            lambda u: u.update(options={"decision": {"total": 2, "distinct": 1, "tokens_per_option": 4}}),
            lambda u: u.update(options={"decision": {"total": True, "distinct": 1, "tokens_per_option": 4}}),
            lambda u: u.update(input_tokens=True),
            lambda u: u.update(state_tokens=-1),
            lambda u: u.update(truncated="false"),
            lambda u: u.update(truncated_questions=""),
        ]
        mutations += [lambda u, field=field: u.pop(field) for field in prediction()["usage"]]
        for mutate in mutations:
            body = prediction()
            mutate(body["usage"])
            with self.subTest(usage=body["usage"]), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(LayaProvider(url))


if __name__ == "__main__":
    unittest.main()
