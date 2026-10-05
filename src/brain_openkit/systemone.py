"""The shared TypeSafe System One choice contract used by Jev and Kev."""

from ipaddress import ip_address
from time import perf_counter
from urllib.parse import urlsplit

from .providers import Decision, ProviderError, _HTTPClient, _count, _probability, _text


class _SystemOneProvider:
    """Bounded choice requests with no automatic POST retry.

    Preserve the server's confidence: System One uses the top probability
    relative to uniform, unlike Laya's entropy-based confidence.
    """

    _probability_rounding = 0.0

    def __init__(self, base_url, api_key, model, timeout):
        if not _text(model) or len(model) > 128 or any(ord(c) < 32 or ord(c) == 127 for c in model):
            raise ProviderError("invalid_configuration")
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
        """List models without requesting an evaluation."""
        response = self._http.request("/v1/models")
        models = response.get("models") if isinstance(response, dict) else None
        if not isinstance(models, list) or any(
            not isinstance(model, dict)
            or not all(_text(model.get(key)) for key in ("name", "description", "release_date"))
            for model in models
        ):
            raise ProviderError("invalid_health_response")
        return {"status": "ok", "models": models}

    def _validate_usage(self, response, usage):
        """Providers may additionally validate their input-consumption metadata."""

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
        tolerance = max(0.001, len(choices) * self._probability_rounding)
        if abs(sum(probabilities.values()) - 1) > tolerance or probabilities[choice] < max(probabilities.values()):
            raise ProviderError("invalid_probabilities")
        confidence = answer.get("confidence")
        if not _probability(confidence):
            raise ProviderError("invalid_confidence")
        usage = response.get("usage")
        if not isinstance(usage, dict) or not all(_count(usage.get(key)) for key in ("input_tokens", "output_tokens")):
            raise ProviderError("invalid_usage")
        self._validate_usage(response, usage)
        return Decision(choice, probabilities, confidence, response["model"], usage, elapsed_ms)
