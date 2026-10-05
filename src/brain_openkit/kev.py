"""Kev's locally served choice API, including Hugging Face checkpoints.

Contract: https://github.com/jaredpalmer/kev/tree/
fe64b1274ea7f80d4095866df90666abb03e9cf6 (kev/api.py and kev/serve.py).
The server's --run selects a checkpoint; this client's model is an API alias.
"""

from .providers import ProviderError, _count
from .systemone import _SystemOneProvider


class KevProvider(_SystemOneProvider):
    """Connect to an existing Kev server; local serving needs no API key."""

    name = "kev"
    # Upstream rounds each probability to four decimal places, up to 255 options.
    _probability_rounding = 0.00005

    def __init__(self, base_url="http://127.0.0.1:8009", api_key=None,
                 model="kev-latest", timeout=10.0):
        super().__init__(base_url, api_key, model, timeout)

    def _validate_usage(self, response, usage):
        # Default Kev refuses oversized input. Its optional truncation mode
        # adds all three fields; never treat a partially read note as complete.
        if "truncated" in response or "state_tokens" in usage or "state_tokens_used" in usage:
            if (type(response.get("truncated")) is not bool
                    or not _count(usage.get("state_tokens"))
                    or not _count(usage.get("state_tokens_used"))
                    or usage["state_tokens_used"] > usage["state_tokens"]):
                raise ProviderError("invalid_usage")
            if response["truncated"] or usage["state_tokens_used"] < usage["state_tokens"]:
                raise ProviderError("truncated_input")
