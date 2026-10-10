"""Connect to the separately served, pinned Korean RoBERTa decision model.

This client neither imports inference dependencies nor downloads model weights.
Option probabilities and confidence are relative scores, not calibrated certainty.
"""

from .providers import ProviderError, _count
from .systemone import _SystemOneProvider


MODEL_ID = "mmetamong/ko-decision-roberta-large"
MODEL_REVISION = "dfd606fff30d52963c0073659ff9a8f6bf1fce6d"


class KoDecisionProvider(_SystemOneProvider):
    """Require exact model provenance and fully consumed 512-token pairs."""

    name = "ko-decision"

    def __init__(self, base_url="http://127.0.0.1:8010", api_key=None,
                 model=MODEL_ID, timeout=10.0):
        super().__init__(base_url, api_key, model, timeout)

    def health(self) -> dict:
        health = super().health()
        matches = [card for card in health["models"] if card["name"] == self.model]
        if len(matches) != 1:
            raise ProviderError("invalid_model_route")
        card = matches[0]
        if (card.get("revision") != MODEL_REVISION
                or type(card.get("max_length")) is not int or card["max_length"] != 512
                or card.get("truncate_states") is not False):
            raise ProviderError("invalid_health_response")
        return health

    def choose(self, state: str, question: str, choices: dict[str, str]):
        if not isinstance(choices, dict) or not 1 <= len(choices) <= 10:
            raise ProviderError("invalid_request")
        decision = super().choose(state, question, choices)
        usage = decision.usage
        if not usage["max_pair_tokens"] <= usage["input_tokens"] <= usage["max_pair_tokens"] * len(choices):
            raise ProviderError("invalid_usage")
        return decision

    def _validate_usage(self, response, usage):
        if (response["model"] != self.model
                or response.get("model_revision") != MODEL_REVISION
                or usage.get("model_revision") != MODEL_REVISION):
            raise ProviderError("invalid_model_route")
        if (not all(_count(usage.get(key)) for key in
                    ("state_tokens", "state_tokens_dropped", "max_pair_tokens"))
                or usage["output_tokens"] != 0
                or not 1 <= usage["max_pair_tokens"] <= 512
                or usage["state_tokens"] > usage["max_pair_tokens"]
                or type(usage.get("truncated")) is not bool
                or not isinstance(usage.get("truncated_questions"), list)
                or not all(isinstance(item, str) for item in usage["truncated_questions"])):
            raise ProviderError("invalid_usage")
        if usage["truncated"] or usage["state_tokens_dropped"] or usage["truncated_questions"]:
            raise ProviderError("truncated_input")
