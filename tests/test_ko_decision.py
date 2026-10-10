"""Verify the Korean adapter's safety contract with actual local HTTP requests."""

import json
import unittest

from brain_openkit.ko_decision import KoDecisionProvider
from brain_openkit.providers import ProviderError
from test_cli_ko_decision import MODEL, REVISION, catalog, prediction
from test_providers import server

class KoDecisionTests(unittest.TestCase):
    choices = {"A": "관련 있음", "B": "관련 없음"}

    def choose(self, provider):
        return provider.choose("한국어 원문", "이 노트가 검색어와 관련이 있습니까?", self.choices)

    def test_real_request_keeps_korean_options_and_model_revision(self):
        with server([{"body": prediction()}]) as (url, requests):
            result = self.choose(KoDecisionProvider(url))
        self.assertEqual(requests[0][:2], ("POST", "/v1/systemone"))
        self.assertNotIn("Authorization", requests[0][2])
        self.assertEqual(json.loads(requests[0][3]), {
            "model": MODEL, "state": "한국어 원문", "questions": {"decision": {
                "type": "choice", "instructions": "이 노트가 검색어와 관련이 있습니까?",
                "criteria": self.choices}}})
        self.assertEqual(result.choice, "A")
        self.assertEqual(result.probabilities, {"A": 0.8, "B": 0.2})
        self.assertEqual(result.confidence, 0.6)
        self.assertEqual(result.model, MODEL)
        self.assertEqual(result.usage["model_revision"], REVISION)
        self.assertEqual(result.usage["output_tokens"], 0)

    def test_health_finds_requested_model_without_inference(self):
        body = catalog()
        body["models"].insert(0, {"name": "unrelated", "description": "Unrelated model", "release_date": "2026-01-01"})
        with server([{"body": body}]) as (url, requests):
            health = KoDecisionProvider(url).health()
        self.assertEqual(health["status"], "ok")
        self.assertEqual([(r[0], r[1], r[3]) for r in requests], [("GET", "/v1/models", b"")])

    def test_unavailable_or_unsafe_loaded_model_is_rejected(self):
        cases = [[], [catalog("wrong-model")["models"][0]], catalog()["models"] * 2]
        for changes in ({"revision": "unverified"}, {"max_length": 513}, {"max_length": True},
                        {"truncate_states": True}, {"truncate_states": "false"}):
            card = catalog()["models"][0]
            card.update(changes)
            cases.append([card])
        for key in ("revision", "max_length", "truncate_states"):
            card = catalog()["models"][0]
            del card[key]
            cases.append([card])
        for cards in cases:
            with self.subTest(cards=cards), server([{"body": {"models": cards}}]) as (url, _):
                with self.assertRaises(ProviderError):
                    KoDecisionProvider(url).health()

    def test_invalid_input_and_too_many_options_never_transmit(self):
        with server([{"body": prediction()}]) as (url, requests):
            for state, question, choices in [("", "q", self.choices), ("s", "", self.choices),
                                             ("s", "q", {}), ("s", "q", {str(i): "선택" for i in range(11)}),
                                             ("s", "q", {"A\n": "선택"}), ("s", "q", None)]:
                with self.subTest(choices=choices), self.assertRaisesRegex(ProviderError, "invalid_request"):
                    KoDecisionProvider(url).choose(state, question, choices)
            self.assertEqual(requests, [])

    def test_model_and_revision_mismatch_are_rejected(self):
        for mutate in (lambda b: b.update(model="wrong-model"),
                       lambda b: b.pop("model_revision"),
                       lambda b: b.update(model_revision="wrong-revision"),
                       lambda b: b["usage"].update(model_revision="wrong-revision")):
            body = prediction()
            mutate(body)
            with server([{"body": body}]) as (url, _), self.assertRaisesRegex(ProviderError, "invalid_model_route"):
                self.choose(KoDecisionProvider(url))

    def test_every_consumption_field_is_required(self):
        for key in prediction()["usage"]:
            body = prediction()
            del body["usage"][key]
            with self.subTest(key=key), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(KoDecisionProvider(url))

    def test_invalid_consumption_metadata_is_rejected(self):
        for changes in ({"output_tokens": 1}, {"state_tokens": True}, {"state_tokens": -1},
                        {"state_tokens": 41}, {"max_pair_tokens": 0}, {"max_pair_tokens": 513},
                        {"max_pair_tokens": False}, {"input_tokens": 39}, {"input_tokens": 81},
                        {"truncated": "false"}, {"truncated_questions": ""},
                        {"truncated_questions": [1]}, {"state_tokens_dropped": True}):
            body = prediction()
            body["usage"].update(changes)
            with self.subTest(changes=changes), server([{"body": body}]) as (url, _), self.assertRaisesRegex(ProviderError, "invalid_usage"):
                self.choose(KoDecisionProvider(url))

    def test_any_truncation_indicator_refuses_prediction(self):
        for changes in ({"truncated": True}, {"state_tokens_dropped": 1}, {"truncated_questions": ["decision"]}):
            body = prediction()
            body["usage"].update(changes)
            with self.subTest(changes=changes), server([{"body": body}]) as (url, _), self.assertRaisesRegex(ProviderError, "truncated_input"):
                self.choose(KoDecisionProvider(url))

    def test_malformed_probability_or_json_response_is_rejected(self):
        for mutate in (lambda b: b["answers"]["decision"].update(choice="B"),
                       lambda b: b["answers"]["decision"].update(probabilities={"A": 0.8}),
                       lambda b: b["answers"]["decision"].update(probabilities={"A": 0.9, "B": 0.2}),
                       lambda b: b["answers"]["decision"].update(confidence=True)):
            body = prediction()
            mutate(body)
            with server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(KoDecisionProvider(url))
        with server([{"body": b'not-json'}]) as (url, _), self.assertRaisesRegex(ProviderError, "invalid_response"):
            self.choose(KoDecisionProvider(url))

    def test_error_body_is_not_disclosed_and_post_is_not_retried(self):
        for status in (401, 413, 422, 429, 503):
            with self.subTest(status=status), server([{"status": status, "body": {"detail": "private Korean note ko-key"}}]) as (url, requests):
                with self.assertRaisesRegex(ProviderError, f"^http_{status}$"):
                    self.choose(KoDecisionProvider(url, api_key="ko-key"))
                self.assertEqual(len(requests), 1)

    def test_remote_plain_http_and_header_injection_are_refused(self):
        for options in ({"base_url": "http://models.example.com"}, {"api_key": "key\nInjected: yes"}):
            with self.subTest(options=options), self.assertRaises(ProviderError):
                KoDecisionProvider(**options)

    def test_redirect_cannot_forward_note_or_key(self):
        with server([{"body": prediction()}]) as (destination, leaked):
            with server([{"status": 307, "headers": {"Location": destination}}]) as (url, _):
                with self.assertRaisesRegex(ProviderError, "http_307"):
                    self.choose(KoDecisionProvider(url, api_key="ko-key"))
            self.assertEqual(leaked, [])


if __name__ == "__main__":
    unittest.main()
