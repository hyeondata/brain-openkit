"""TypeSafe Jev choice adapter, separate from Laya's local wire extensions.

Contract: https://docs.typesafe.ai/api and https://api.typesafe.ai/openapi.json
Cross-checked against typesafe-sdk-python 0.7.2, revision
f078f1e208a0d885154dc758344ae4fce77ac168. Contract fixtures are not live inference.
"""

from ipaddress import ip_address
from time import perf_counter
from urllib.parse import urlsplit

from .providers import Decision, ProviderError, _HTTPClient, _count, _probability, _text


class JevProvider:
    """Explicit hosted decisions; no automatic retry of a billable POST.

    Keep Jev's reported confidence unchanged. Its Choice confidence uses the
    top probability relative to a uniform distribution, not Laya's entropy.
    """

    name = "jev"

    def __init__(self, base_url="https://api.typesafe.ai", api_key=None,
                 model="jev-latest", timeout=10.0):
        if api_key is None or api_key == "":
            raise ProviderError("missing_api_key")
        if not _text(model) or len(model) > 128 or any(ord(c) < 32 or ord(c) == 127 for c in model):
            raise ProviderError("invalid_configuration")
        # Constructing the transport validates every setting without connecting.
        self._http = _HTTPClient(base_url, api_key, timeout)
        parsed = urlsplit(self._http.base_url)
        if parsed.scheme == "http":
            try:
                loopback = ip_address(parsed.hostname).is_loopback
            except ValueError:
                loopback = parsed.hostname == "localhost"
            if not loopback:
                raise ProviderError("insecure_endpoint")
        self.base_url = self._http.base_url
        self.timeout = self._http.timeout
        self.model = model

    def health(self) -> dict:
        """Authenticate and list models without requesting an evaluation."""
        response = self._http.request("/v1/models")
        models = response.get("models") if isinstance(response, dict) else None
        if not isinstance(models, list) or any(
            not isinstance(model, dict)
            or not all(_text(model.get(key)) for key in ("name", "description", "release_date"))
            for model in models
        ):
            raise ProviderError("invalid_health_response")
        return {"status": "ok", "models": models}

    def choose(self, state: str, question: str, choices: dict[str, str]) -> Decision:
        if not _text(state) or not _text(question) or not isinstance(choices, dict) or not 1 <= len(choices) <= 255:
            raise ProviderError("invalid_request")
        if any(not _text(key) or not _text(value) or any(ord(c) < 32 or ord(c) == 127 for c in key)
               for key, value in choices.items()):
            raise ProviderError("invalid_request")
        started = perf_counter()
        response = self._http.request("/v1/systemone", {
            "model": self.model, "state": state,
            "questions": {"decision": {"type": "choice", "instructions": question, "criteria": choices}},
        })
        elapsed_ms = (perf_counter() - started) * 1000
        if not isinstance(response, dict) or not _text(response.get("model")):
            raise ProviderError("invalid_response")
        answers = response.get("answers")
        answer = answers.get("decision") if isinstance(answers, dict) else None
        if not isinstance(answer, dict) or answer.get("type") != "choice":
            raise ProviderError("invalid_answer")
        choice, probabilities = answer.get("choice"), answer.get("probabilities")
        if not isinstance(choice, str) or choice not in choices or not isinstance(probabilities, dict):
            raise ProviderError("invalid_answer")
        if set(probabilities) != set(choices) or not all(_probability(p) for p in probabilities.values()):
            raise ProviderError("invalid_probabilities")
        if abs(sum(probabilities.values()) - 1) > 0.001 or probabilities[choice] < max(probabilities.values()):
            raise ProviderError("invalid_probabilities")
        confidence = answer.get("confidence")
        if not _probability(confidence):
            raise ProviderError("invalid_confidence")
        usage = response.get("usage")
        if not isinstance(usage, dict) or not all(_count(usage.get(key)) for key in ("input_tokens", "output_tokens")):
            raise ProviderError("invalid_usage")
        return Decision(choice, probabilities, confidence, response["model"], usage, elapsed_ms)
