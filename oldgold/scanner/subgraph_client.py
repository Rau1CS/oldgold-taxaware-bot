"""Simple subgraph client with retries."""
from __future__ import annotations

import requests

from ..logging_conf import LOGGER
from ..utils import retry


def post(endpoint: str, query: str, variables: dict) -> dict:
    """POST a GraphQL query and return JSON data."""
    def _call() -> dict:
        resp = requests.post(
            endpoint, json={"query": query, "variables": variables}, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(data["errors"])
        return data["data"]

    return retry(3, _call)
