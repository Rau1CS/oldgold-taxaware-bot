"""Utilities for fetching pair information and reserves.

This module provides helpers to locate liquidity pool pairs on a given
chain and fetch their reserves.  It also contains a small CLI used for
manual verification and development tooling.

The functions rely on on-chain factory contracts to resolve pair
addresses and may use subgraph queries for heuristics such as selecting
an active pool with the deepest liquidity.
"""
from __future__ import annotations

from dataclasses import dataclass
import json

from web3 import Web3

from ..config import CHAIN_CONFIGS, SUBGRAPHS
from ..logging_conf import LOGGER
from ..utils import retry_call
from .subgraph_client import post

# Minimal ABI fragments for factory/pair contracts.  Only the methods we
# use are included which keeps the dependency light.
FACTORY_ABI = json.loads(
    """[
    {"name": "getPair", "inputs": [{"name": "tokenA", "type": "address"}, {"name": "tokenB", "type": "address"}], "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"}
    ]"""
)
PAIR_ABI = json.loads(
    """[
    {"name": "token0", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"name": "token1", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"name": "getReserves", "outputs": [{"type": "uint112"}, {"type": "uint112"}, {"type": "uint32"}], "stateMutability": "view", "type": "function"}
    ]"""
)


@dataclass
class PairReserves:
    """Simple container for pair address and directional reserves."""

    address: str
    r_in: float
    r_out: float


def _w3(chain: str) -> Web3:
    cfg = CHAIN_CONFIGS[chain]
    return Web3(Web3.HTTPProvider(cfg.rpc))


def get_pair(chain: str, token_in: str, token_out: str) -> PairReserves:
    """Return pair address and reserves for ``token_in``→``token_out``.

    Parameters
    ----------
    chain: str
        Chain key as defined in :mod:`oldgold.config`.
    token_in: str
        Address of the input token.
    token_out: str
        Address of the output token.
    """

    w3 = _w3(chain)
    cfg = CHAIN_CONFIGS[chain]
    factory = w3.eth.contract(address=cfg.factory, abi=FACTORY_ABI)
    pair_addr: str = factory.functions.getPair(token_in, token_out).call()
    if int(pair_addr, 16) == 0:
        raise ValueError("pair does not exist")
    pair_c = w3.eth.contract(address=pair_addr, abi=PAIR_ABI)
    token0 = pair_c.functions.token0().call()
    token1 = pair_c.functions.token1().call()
    r0, r1, _ = retry_call(3, lambda: pair_c.functions.getReserves().call())
    if token_in.lower() == token0.lower():
        r_in, r_out = r0, r1
    else:
        r_in, r_out = r1, r0
    return PairReserves(pair_addr, float(r_in), float(r_out))


def active_pool_for_token(chain: str, token: str, base: str) -> str:
    """Return the address of the deepest pool for ``token``/``base``.

    The implementation performs a simple subgraph query and selects the
    pool with the largest ``reserveUSD``.  When no subgraph endpoint is
    configured the function returns an empty string.
    """

    endpoint = SUBGRAPHS.get(f"{chain}_univ2")
    if not endpoint:
        LOGGER.warning("no subgraph endpoint configured for %s", chain)
        return ""
    query = """
    query ($token: String!, $base: String!) {
      pairs(where: {
        token0_in: [$token, $base],
        token1_in: [$token, $base]
      }) {
        id
        reserveUSD
        token0 { id }
        token1 { id }
      }
    }
    """
    try:
        data = post(endpoint, query, {"token": token.lower(), "base": base.lower()})
    except Exception as exc:  # pragma: no cover - network issues
        LOGGER.error("subgraph query failed: %s", exc)
        return ""
    pairs = data.get("pairs", [])
    best = max(pairs, key=lambda p: float(p.get("reserveUSD", 0)), default=None)
    return best["id"] if best else ""


def main(chain: str = "bsc", token: str = "", base: str = "WBNB") -> None:
    """Small helper CLI to print pair address and reserves."""

    cfg = CHAIN_CONFIGS[chain]
    base_addr = base if base.lower().startswith("0x") else cfg.wrapped
    res = get_pair(chain, token, base_addr)
    print(
        json.dumps(
            {
                "pair": res.address,
                "r_in": res.r_in,
                "r_out": res.r_out,
            },
            indent=2,
        )
    )


if __name__ == "__main__":  # pragma: no cover - manual CLI use
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--chain", default="bsc")
    p.add_argument("--token", required=True)
    p.add_argument("--base", default="WBNB")
    a = p.parse_args()
    main(chain=a.chain, token=a.token, base=a.base)
