"""Local HTTP fixtures for Kev's choice API, not model quality evaluations."""

import json
from pathlib import Path
import tempfile
import unittest

from brain_openkit.kev import KevProvider
from brain_openkit.providers import ProviderError
from brain_openkit.workflows import classify, search
from test_providers import server


def prediction():
    return {
        "model": "kev-latest",
        "answers": {"decision": {
            "type": "choice", "choice": "A", "confidence": 0.8,
            "probabilities": {"A": 0.9, "B": 0.1},
        }},
        # Kev counts serialized answer tokens even though it does not generate.
        "usage": {"input_tokens": 101, "output_tokens": 161},
        "latency_ms": 125,
    }


class KevTests(unittest.TestCase):
    choices = {"A": "Relevant", "B": "Unrelated"}

    def choose(self, provider):
        return provider.choose("한국어 원문", "Is the note relevant?", self.choices)

    def test_local_default_requires_no_key_and_uses_native_contract(self):
        self.assertEqual(KevProvider().base_url, "http://127.0.0.1:8009")
        self.assertEqual(KevProvider.name, "kev")
        with server([{"body": prediction()}]) as (url, requests):
            result = self.choose(KevProvider(url))
        method, path, headers, raw = requests[0]
        self.assertEqual((method, path), ("POST", "/v1/systemone"))
        self.assertNotIn("Authorization", headers)
        self.assertEqual(json.loads(raw), {
            "model": "kev-latest", "state": "한국어 원문",
            "questions": {"decision": {"type": "choice", "instructions": "Is the note relevant?",
                                        "criteria": self.choices}},
        })
        self.assertEqual(result.choice, "A")
        self.assertEqual(result.confidence, 0.8)
        self.assertIsNone(result.answer_confidence)
        self.assertEqual(result.model, "kev-latest")
        self.assertEqual(result.usage, {"input_tokens": 101, "output_tokens": 161})

    def test_optional_bearer_key_gateway_and_server_alias(self):
        with server([{"body": prediction()}]) as (url, requests):
            self.choose(KevProvider(url + "/gateway/", api_key="fixture-key", model="kev-custom"))
        self.assertEqual(requests[0][1], "/gateway/v1/systemone")
        self.assertEqual(requests[0][2]["Authorization"], "Bearer fixture-key")
        self.assertEqual(json.loads(requests[0][3])["model"], "kev-custom")

    def test_health_lists_loaded_checkpoint_without_inference(self):
        card = {"name": "kev-latest", "description": "Kev on Qwen2.5-0.5B",
                "release_date": "2026-09-17", "run": "jaredpalmer/kev-0.5b@v0.1",
                "base": "Qwen/Qwen2.5-0.5B", "backend": "torch", "truncate_states": False}
        with server([{"body": {"models": [card]}}]) as (url, requests):
            health = KevProvider(url).health()
        self.assertEqual(health, {"status": "ok", "models": [card]})
        self.assertEqual(requests[0][0:2], ("GET", "/v1/models"))
        self.assertEqual(requests[0][3], b"")
        self.assertNotIn("Authorization", requests[0][2])

    def test_invalid_configuration_never_transmits(self):
        for options in ({"base_url": "http://models.example.com"},
                        {"base_url": "http://127.0.0.1.example.com"},
                        {"base_url": "http://192.168.1.2"},
                        {"base_url": "https://user:secret@example.com"},
                        {"model": ""}, {"model": "kev\nsecret"},
                        {"api_key": "secret\nInjected:yes"}, {"api_key": 1},
                        {"timeout": False}):
            with self.subTest(options=options), self.assertRaises(ProviderError):
                KevProvider(**options)
        for url in ("http://127.0.0.1", "http://[::1]", "http://localhost", "https://models.example.com"):
            self.assertEqual(KevProvider(url).base_url, url)

    def test_errors_are_sanitized_and_post_is_never_retried(self):
        for status in (401, 422, 429, 502, 503, 504):
            with self.subTest(status=status), server([{
                "status": status, "body": {"detail": "private note fixture-key"},
                "headers": {"Retry-After": "99999"},
            }]) as (url, requests):
                with self.assertRaisesRegex(ProviderError, f"^http_{status}$"):
                    self.choose(KevProvider(url))
                self.assertEqual(len(requests), 1)

    def test_redirect_cannot_send_notes_or_credentials_elsewhere(self):
        with server([{"body": prediction()}]) as (destination, leaked):
            with server([{"status": 307, "headers": {"Location": destination}}]) as (url, requests):
                with self.assertRaisesRegex(ProviderError, "http_307"):
                    self.choose(KevProvider(url, api_key="fixture-key"))
                self.assertEqual(len(requests), 1)
            self.assertEqual(leaked, [])

    def test_malformed_answers_are_rejected(self):
        mutations = [lambda b: b.pop("model"), lambda b: b["answers"].pop("decision"),
                     lambda b: b["answers"]["decision"].update(choice="B"),
                     lambda b: b["answers"]["decision"].update(probabilities={"A": 0.9}),
                     lambda b: b["answers"]["decision"].update(confidence=True),
                     lambda b: b["usage"].update(output_tokens=-1)]
        for mutate in mutations:
            body = prediction()
            mutate(body)
            with self.subTest(body=body), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(KevProvider(url))

    def test_rounded_255_option_distribution_is_accepted(self):
        body = prediction()
        choices = {str(i): f"Option {i}" for i in range(255)}
        body["answers"]["decision"].update(
            choice="0", probabilities={key: round(1 / 255, 4) for key in choices}, confidence=0)
        with server([{"body": body}]) as (url, _):
            result = KevProvider(url).choose("State", "Question", choices)
        self.assertEqual(result.choice, "0")
        self.assertEqual(result.confidence, 0)

    def test_rounding_tolerance_does_not_accept_unnormalized_small_distributions(self):
        body = prediction()
        body["answers"]["decision"]["probabilities"] = {"A": 0.91, "B": 0.1}
        with server([{"body": body}]) as (url, _), self.assertRaisesRegex(ProviderError, "invalid_probabilities"):
            self.choose(KevProvider(url))

    def test_explicit_nontruncation_marks_are_accepted(self):
        body = prediction()
        body["truncated"] = False
        body["usage"].update(state_tokens=30, state_tokens_used=30)
        with server([{"body": body}]) as (url, _):
            result = self.choose(KevProvider(url))
        self.assertEqual(result.usage["state_tokens_used"], 30)

    def test_truncation_and_inconsistent_marks_are_rejected(self):
        cases = [(True, 30, 20), (False, 30, 20), ("false", 30, 30),
                 (False, 30, 31), (False, True, 1), (False, 30, -1),
                 (False, None, 30), (None, 30, 30)]
        for flag, total, used in cases:
            body = prediction()
            if flag is not None:
                body["truncated"] = flag
            body["usage"].update(state_tokens=total, state_tokens_used=used)
            with self.subTest(case=(flag, total, used)), server([{"body": body}]) as (url, _), self.assertRaises(ProviderError):
                self.choose(KevProvider(url))

    def test_workflows_use_kev_and_restore_bm25_on_failure_without_changing_notes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vault = root / "vault"
            vault.mkdir()
            note = vault / "note.md"
            note.write_bytes("# Search\r\n\r\nLocal search 한국어 notes.\r\n".encode())
            original = note.read_bytes()
            with server([{"body": prediction()}]) as (url, _):
                provider = KevProvider(url)
                found = search(vault, "search", cache_dir=root / "cache", provider=provider)
                classified = classify(vault, Path("note.md"),
                                      {"categories": {"knowledge": "Notes", "food": "Cooking"},
                                       "tags": {"retrieval": "Searching notes"}}, provider)
            self.assertEqual(found["provider"], "kev")
            self.assertEqual(found["rerank_status"], "complete")
            self.assertEqual(classified["provider"], "kev")
            self.assertEqual(classified["category"], "knowledge")
            self.assertEqual(classified["tags"], ["retrieval"])
            baseline = search(vault, "search", cache_dir=root / "cache")
            with server([{"status": 503}]) as (url, requests):
                fallback = search(vault, "search", cache_dir=root / "cache", provider=KevProvider(url))
            self.assertEqual(fallback["provider"], "kev")
            self.assertEqual(fallback["rerank_status"], "unavailable")
            self.assertEqual(fallback["results"], baseline["results"])
            self.assertEqual(len(requests), 1)
            self.assertEqual(note.read_bytes(), original)

    def test_truncated_later_candidate_discards_all_model_scores(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vault = root / "vault"
            vault.mkdir()
            for name in ("first", "second"):
                (vault / f"{name}.md").write_text(f"# {name}\n\nSearch retrieval notes.\n")
            originals = {p.name: p.read_bytes() for p in vault.iterdir()}
            baseline = search(vault, "search", cache_dir=root / "cache")
            truncated = prediction()
            truncated["truncated"] = True
            truncated["usage"].update(state_tokens=30, state_tokens_used=20)
            with server([{"body": prediction()}, {"body": truncated}]) as (url, requests):
                result = search(vault, "search", cache_dir=root / "cache", provider=KevProvider(url))
            self.assertEqual(len(requests), 2)
            self.assertEqual(result["rerank_status"], "unavailable")
            self.assertEqual(result["results"], baseline["results"])
            self.assertEqual({p.name: p.read_bytes() for p in vault.iterdir()}, originals)


if __name__ == "__main__":
    unittest.main()
