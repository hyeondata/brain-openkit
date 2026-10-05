"""Bounded HTTP decisions, without importing Laya or downloading model weights.

Wire contract checked against NandhaKishorM/laya 0.3.26, revision
2e4d9c87e8b1621deb344eac7de5c7258f32f849 (serve.py and agent.py).
"""

from dataclasses import dataclass
from http.client import HTTPException
import json
import math
import time
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 256 * 1024


class ProviderError(Exception):
    """A safe error code; never contains server bodies, source notes or credentials."""


@dataclass(frozen=True)
class Decision:
    choice: str
    probabilities: dict[str, float]
    confidence: float | None
    model: str
    usage: dict
    elapsed_ms: float
    answer_confidence: float | None = None


class DecisionProvider(Protocol):
    def choose(self, state: str, question: str, choices: dict[str, str]) -> Decision: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _probability(value):
    return _number(value) and 0 <= value <= 1


def _count(value):
    return type(value) is int and value >= 0


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("non-finite number")


class _HTTPClient:
    """Shared bounded JSON transport; providers own their wire contracts."""

    def __init__(self, base_url, api_key, timeout, retry_statuses=()):
        if not isinstance(base_url, str) or any(c.isspace() or ord(c) < 32 for c in base_url) or "\\" in base_url:
            raise ProviderError("invalid_configuration")
        try:
            parsed = urlsplit(base_url)
            valid = (parsed.scheme in ("http", "https") and parsed.hostname
                     and parsed.username is None and parsed.password is None
                     and not parsed.query and not parsed.fragment
                     and (parsed.port is None or 1 <= parsed.port <= 65535))
            base_url.encode("ascii")
        except (ValueError, UnicodeError):
            raise ProviderError("invalid_configuration") from None
        if not valid or not _number(timeout) or timeout <= 0:
            raise ProviderError("invalid_configuration")
        if api_key is not None and (not isinstance(api_key, str)
                                    or any(not 33 <= ord(c) <= 126 for c in api_key)):
            raise ProviderError("invalid_configuration")
        self.base_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
        self.timeout = float(timeout)
        self._retry_statuses = retry_statuses
        self._api_key = api_key
        # A direct connection keeps local note traffic out of ambient proxy settings.
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def request(self, path, payload=None):
        data = None
        if payload is not None:
            try:
                data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            except (TypeError, ValueError, UnicodeError):
                raise ProviderError("invalid_request") from None
            if len(data) > MAX_REQUEST_BYTES:
                raise ProviderError("request_too_large")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self._api_key:
            headers["Authorization"] = "Bearer " + self._api_key
        request = Request(self.base_url + path, data=data, headers=headers)
        for attempt in range(2 if self._retry_statuses else 1):
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ProviderError("response_too_large")
                try:
                    return json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                                      parse_constant=_reject_constant)
                except (ValueError, UnicodeError, RecursionError):
                    raise ProviderError("invalid_response") from None
            except HTTPError as error:
                status = error.code
                error.close()
                if status in self._retry_statuses and attempt == 0:
                    # Exactly one short retry; server-controlled Retry-After cannot
                    # turn a CLI invocation into an unbounded wait.
                    time.sleep(0.05)
                    continue
                raise ProviderError(f"http_{status}") from None
            except (URLError, OSError, HTTPException):
                raise ProviderError("connection_failed") from None
        raise ProviderError("connection_failed")


class LayaProvider:
    """Use the explicit multilingual checkpoint over HTTP.

    ``Decision.confidence`` preserves Laya's entropy-based choice confidence;
    ``answer_confidence`` separately preserves its answer probability metadata.
    ``Decision.model`` identifies ``routing.repo`` when present, otherwise the
    verified ``routing.model``. Laya's root model is only a generic agent name.
    """

    name = "laya"

    def __init__(self, base_url="http://127.0.0.1:8000", api_key=None,
                 timeout=10.0, max_tokens=1024):
        if type(max_tokens) is not int or not 1 <= max_tokens <= 8192:
            raise ProviderError("invalid_configuration")
        self._http = _HTTPClient(base_url, api_key, timeout, retry_statuses=(502, 503, 504))
        self.base_url = self._http.base_url
        self.timeout = self._http.timeout
        self.max_tokens = max_tokens

    def _request(self, path, payload=None):
        return self._http.request(path, payload)

    def health(self) -> dict:
        """Check server liveness without asking it to load or run a checkpoint."""
        response = self._request("/health")
        if not isinstance(response, dict) or response.get("status") != "ok":
            raise ProviderError("invalid_health_response")
        return response

    def choose(self, state: str, question: str, choices: dict[str, str]) -> Decision:
        if not _text(state) or not _text(question) or not isinstance(choices, dict) or not 1 <= len(choices) <= 10:
            raise ProviderError("invalid_request")
        if any(not _text(key) or not _text(value) or any(ord(c) < 32 for c in key)
               for key, value in choices.items()):
            raise ProviderError("invalid_request")
        started = time.perf_counter()
        response = self._request("/v1/systemone", {
            "model": "multilingual", "state": state,
            "questions": {"decision": {"type": "choice", "instructions": question, "criteria": choices}},
            "max_len": self.max_tokens, "head_max_len": 256,
        })
        return self._decision(response, choices, (time.perf_counter() - started) * 1000)

    @staticmethod
    def _decision(response, choices, elapsed_ms):
        if not isinstance(response, dict) or not _text(response.get("model")):
            raise ProviderError("invalid_response")
        routing = response.get("routing")
        if not isinstance(routing, dict) or routing.get("model") != "multilingual":
            raise ProviderError("invalid_model_route")
        model = routing.get("repo", routing["model"])
        if not _text(model):
            raise ProviderError("invalid_model_route")
        answers = response.get("answers")
        answer = answers.get("decision") if isinstance(answers, dict) else None
        if not isinstance(answer, dict) or answer.get("type") != "choice":
            raise ProviderError("invalid_answer")
        choice = answer.get("choice")
        probabilities = answer.get("probabilities")
        if not isinstance(choice, str) or choice not in choices or not isinstance(probabilities, dict):
            raise ProviderError("invalid_answer")
        if set(probabilities) != set(choices) or not all(_probability(p) for p in probabilities.values()):
            raise ProviderError("invalid_probabilities")
        # Official outputs round each probability to four decimal places.
        if abs(sum(probabilities.values()) - 1) > 0.001 or probabilities[choice] + 0.0001 < max(probabilities.values()):
            raise ProviderError("invalid_probabilities")
        confidence = answer.get("confidence")
        answer_confidence = answer.get("answer_confidence")
        if not _probability(confidence) or ("answer_confidence" in answer and not _probability(answer_confidence)):
            raise ProviderError("invalid_confidence")
        if "low_confidence" in answer:
            if answer["low_confidence"] is not True:
                raise ProviderError("invalid_abstention")
            raise ProviderError("abstained_answer")
        if "abstention" in answer or "abstention_threshold" in answer:
            if (answer.get("abstention") not in ("passed", "abstained", "unevaluated")
                    or not _probability(answer.get("abstention_threshold"))):
                raise ProviderError("invalid_abstention")
            if answer["abstention"] != "passed":
                raise ProviderError("abstained_answer")
        usage = response.get("usage")
        if not isinstance(usage, dict):
            raise ProviderError("invalid_usage")
        for key in ("input_tokens", "output_tokens", "state_tokens", "state_tokens_dropped"):
            if not _count(usage.get(key)):
                raise ProviderError("invalid_usage")
        if type(usage.get("truncated")) is not bool or not isinstance(usage.get("truncated_questions"), list):
            raise ProviderError("invalid_usage")
        if not all(isinstance(qid, str) for qid in usage["truncated_questions"]):
            raise ProviderError("invalid_usage")
        if usage["truncated"] or usage["state_tokens_dropped"] or usage["truncated_questions"]:
            raise ProviderError("truncated_input")
        if "options" in usage:
            options = usage["options"]
            if not isinstance(options, dict):
                raise ProviderError("invalid_usage")
            for collapse in options.values():
                if (not isinstance(collapse, dict) or not _count(collapse.get("total"))
                        or not _count(collapse.get("distinct")) or collapse["total"] < 1
                        or not 0 <= collapse["distinct"] <= collapse["total"]
                        or "tokens_per_option" not in collapse
                        or (collapse["tokens_per_option"] is not None
                            and (not _count(collapse["tokens_per_option"]) or collapse["tokens_per_option"] < 1))):
                    raise ProviderError("invalid_usage")
                if collapse["distinct"] < collapse["total"]:
                    raise ProviderError("collapsed_options")
        return Decision(choice, probabilities, confidence, model, usage, elapsed_ms, answer_confidence)
