"""TypeSafe Jev choice adapter, separate from Laya's local wire extensions.

Contract: https://docs.typesafe.ai/api and https://api.typesafe.ai/openapi.json
Cross-checked against typesafe-sdk-python 0.7.2, revision
f078f1e208a0d885154dc758344ae4fce77ac168. Contract fixtures are not live inference.
"""

from .providers import ProviderError
from .systemone import _SystemOneProvider


class JevProvider(_SystemOneProvider):
    """Explicit hosted decisions; an API key is required before connecting."""

    name = "jev"

    def __init__(self, base_url="https://api.typesafe.ai", api_key=None,
                 model="jev-latest", timeout=10.0):
        if api_key is None or api_key == "":
            raise ProviderError("missing_api_key")
        super().__init__(base_url, api_key, model, timeout)
