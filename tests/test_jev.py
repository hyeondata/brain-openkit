"""Contract fixtures for TypeSafe Jev; these never contact the hosted service."""

import json
from pathlib import Path
import tempfile
import time
import unittest

from brain_openkit.jev import JevProvider
from brain_openkit.providers import LayaProvider, ProviderError
from brain_openkit.workflows import classify, search
from test_providers import server


def prediction():
    return {
        "model": "jev-1.13.0",
        "answers": {"decision": {
            "type": "choice", "choice": "A",
            "probabilities": {"A": 0.9, "B": 0.1}, "confidence": 0.8,
        }},
        "usage": {"input_tokens": 120, "output_tokens": 20},
    }


class JevTests(unittest.TestCase):
    choices = {"A": "관련 있음", "B": "관련 없음"}

    def choose(self, provider):
        return provider.choose("한국어 원문", "관련된 노트인가?", self.choices)

    def test_native_request_response_and_provider_identity(self):
        with server([{"body": prediction()}]) as (url, requests):
            result = self.choose(JevProvider(url + "/", api_key="fixture-key"))
        method, path, headers, body = requests[0]
        self.assertEqual((method, path), ("POST", "/v1/systemone"))
        self.assertEqual(headers["Authorization"], "Bearer fixture-key")
        self.assertEqual(json.loads(body), {
            "model": "jev-latest", "state": "한국어 원문",
            "questions": {"decision": {"type": "choice", "instructions": "관련된 노트인가?",
                                        "criteria": self.choices}},
        })
        self.assertEqual(result.choice, "A")
        self.assertEqual(result.confidence, 0.8)
        self.assertIsNone(result.answer_confidence)
        self.assertEqual(result.model, "jev-1.13.0")
        self.assertEqual(result.usage, {"input_tokens": 120, "output_tokens": 20})
        self.assertGreaterEqual(result.elapsed_ms, 0)
        self.assertEqual(JevProvider.name, "jev")
        self.assertEqual(LayaProvider.name, "laya")

    def test_explicit_model_and_gateway_path_are_preserved(self):
        with server([{"body": prediction()}]) as (url, requests):
            self.choose(JevProvider(url + "/gateway", api_key="fixture-key", model="jev-1.13.0"))
        self.assertEqual(requests[0][1], "/gateway/v1/systemone")
        self.assertEqual(json.loads(requests[0][3])["model"], "jev-1.13.0")

    def test_missing_or_invalid_key_fails_before_any_transmission(self):
        with server([{"body": prediction()}]) as (url, requests):
            for key in (None, "", " ", "fixture key", "secret\nHeader:x", "한글", 7):
                with self.subTest(key_type=type(key).__name__), self.assertRaises(ProviderError) as error:
                    JevProvider(url, api_key=key)
                self.assertNotIn("secret", str(error.exception))
            self.assertEqual(requests, [])
        with self.assertRaisesRegex(ProviderError, "missing_api_key"):
            JevProvider()

    def test_remote_http_and_invalid_configuration_are_rejected(self):
        cases = [
            {"base_url": "http://api.typesafe.ai"},
            {"base_url": "http://127.0.0.1.example.com"},
            {"base_url": "http://192.168.1.1"},
            {"base_url": "http://2130706433"},
            {"base_url": "ftp://127.0.0.1"}, {"base_url": "https://"},
            {"base_url": "https://user:secret@example.com"},
            {"base_url": "https://example.com?key=secret"},
            {"base_url": "https://example.com/#fragment"},
            {"base_url": "https://example.com:99999"},
            {"base_url": "https://example.com\\@elsewhere"},
            {"base_url": "https://ex ample.com"},
            {"base_url": 3}, {"timeout": 0}, {"timeout": True},
            {"timeout": float("nan")}, {"timeout": float("inf")},
            {"timeout": 10 ** 1000}, {"model": ""}, {"model": "jev\nsecret"},
            {"model": None}, {"model": "x" * 129},
        ]
        for options in cases:
            with self.subTest(options=options), self.assertRaises(ProviderError):
                JevProvider(api_key="fixture-key", **options)
        self.assertEqual(JevProvider(api_key="fixture-key").base_url, "https://api.typesafe.ai")
        for url in ("http://127.0.0.1", "http://[::1]", "http://localhost"):
            self.assertEqual(JevProvider(url, api_key="fixture-key").base_url, url)

    def test_doctor_lists_models_without_inference(self):
        catalog = {"models": [{"name": "jev-latest", "description": "Jev", "release_date": "2026-09-15"}]}
        with server([{"body": catalog}]) as (url, requests):
            result = JevProvider(url, api_key="fixture-key").health()
        self.assertEqual(result, {"status": "ok", **catalog})
        self.assertEqual(requests[0][0:2], ("GET", "/v1/models"))
        self.assertEqual(requests[0][2]["Authorization"], "Bearer fixture-key")
        self.assertEqual(requests[0][3], b"")
        for body in ({}, [], {"models": {}}, {"models": ["jev"]}, {"models": [{"name": ""}]}):
            with self.subTest(body=body), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                JevProvider(url, api_key="fixture-key").health()

    def test_invalid_and_oversized_inputs_never_reach_server(self):
        cases = [("", "q", self.choices), (None, "q", self.choices),
                 ("s", "", self.choices), ("s", "q", {}),
                 ("s", "q", {str(i): "x" for i in range(256)}),
                 ("s", "q", {1: "x"}), ("s", "q", {"A": 3}),
                 ("s", "q", {"A\nB": "x"}),
                 ("\ud800", "q", self.choices), ("한" * 23000, "q", self.choices)]
        with server([{"body": prediction()}]) as (url, requests):
            provider = JevProvider(url, api_key="fixture-key")
            for state, question, choices in cases:
                with self.subTest(state_type=type(state).__name__), self.assertRaises(ProviderError):
                    provider.choose(state, question, choices)
            self.assertEqual(requests, [])

    def test_errors_hide_response_details_and_never_repeat_billable_post(self):
        for status in (400, 401, 403, 422, 429, 500, 502, 503, 504, 529):
            with self.subTest(status=status), server([{
                "status": status, "body": {"detail": "private note fixture-key"},
                "headers": {"Retry-After": "99999"},
            }]) as (url, requests):
                with self.assertRaisesRegex(ProviderError, f"^http_{status}$"):
                    self.choose(JevProvider(url, api_key="fixture-key"))
                self.assertEqual(len(requests), 1)

    def test_redirect_does_not_leak_key_or_note(self):
        with server([{"body": prediction()}]) as (destination, leaked):
            for status in (301, 302, 303, 307, 308):
                with self.subTest(status=status), server([{
                    "status": status, "headers": {"Location": destination},
                }]) as (url, requests):
                    with self.assertRaises(ProviderError):
                        self.choose(JevProvider(url, api_key="fixture-key"))
                    self.assertEqual(len(requests), 1)
            self.assertEqual(leaked, [])

    def test_timeout_fails_without_retry(self):
        with server([{"body": prediction(), "delay": 0.15}]) as (url, requests):
            started = time.monotonic()
            with self.assertRaisesRegex(ProviderError, "connection_failed"):
                self.choose(JevProvider(url, api_key="fixture-key", timeout=0.025))
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertEqual(len(requests), 1)

    def test_strict_response_json_and_size_limits(self):
        bodies = [b"{broken", b"\xff", b"x" * (256 * 1024 + 1), b"[]",
                  b'{"model":"jev","model":"different"}',
                  json.dumps(prediction()).replace('0.8', 'NaN').encode()]
        for body in bodies:
            with self.subTest(size=len(body)), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(JevProvider(url, api_key="fixture-key"))

    def test_invalid_answers_and_usage_are_rejected(self):
        mutations = [
            lambda b: b.pop("model"), lambda b: b.update(model=7),
            lambda b: b["answers"].pop("decision"),
            lambda b: b["answers"]["decision"].update(type="noul"),
            lambda b: b["answers"]["decision"].update(choice="X"),
            lambda b: b["answers"]["decision"].update(choice="B"),
            lambda b: b["answers"]["decision"].pop("confidence"),
            lambda b: b["answers"]["decision"].update(confidence=True),
            lambda b: b["answers"]["decision"].update(confidence=-1),
            lambda b: b.pop("usage"),
            lambda b: b["usage"].pop("input_tokens"),
            lambda b: b["usage"].update(input_tokens=True),
            lambda b: b["usage"].update(output_tokens=-1),
        ]
        for mutate in mutations:
            body = prediction()
            mutate(body)
            with self.subTest(body=body), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(JevProvider(url, api_key="fixture-key"))

    def test_probability_distribution_is_complete_finite_and_normalized(self):
        cases = [{"A": 0.9}, {"A": 0.9, "B": 0.1, "C": 0},
                 {"A": True, "B": 0}, {"A": 0.9, "B": "0.1"},
                 {"A": 1.1, "B": -0.1}, {"A": 0.9, "B": 0.9},
                 {"A": 10 ** 1000, "B": 0}, {"A": float("inf"), "B": 0}]
        for probabilities in cases:
            body = prediction()
            body["answers"]["decision"]["probabilities"] = probabilities
            with self.subTest(probabilities=probabilities), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(JevProvider(url, api_key="fixture-key"))

    def test_workflows_report_jev_for_success_and_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vault = root / "vault"
            vault.mkdir()
            note = vault / "note.md"
            note.write_bytes(b"# Search\n\nLocal search notes.\n")
            original = note.read_bytes()
            with server([{"body": prediction()}]) as (url, _):
                provider = JevProvider(url, api_key="fixture-key")
                found = search(vault, "search", cache_dir=root / "cache", provider=provider)
                classified = classify(vault, Path("note.md"),
                                      {"categories": {"knowledge": "Notes", "food": "Cooking"}}, provider)
            self.assertEqual(found["provider"], "jev")
            self.assertEqual(found["rerank_status"], "complete")
            self.assertEqual(classified["provider"], "jev")
            self.assertEqual(classified["category"], "knowledge")
            with server([{"status": 401}]) as (url, _):
                fallback = search(vault, "search", cache_dir=root / "cache",
                                  provider=JevProvider(url, api_key="fixture-key"))
            self.assertEqual(fallback["provider"], "jev")
            self.assertEqual(fallback["rerank_status"], "unavailable")
            self.assertIsNone(fallback["results"][0]["model_score"])
            self.assertEqual(note.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
