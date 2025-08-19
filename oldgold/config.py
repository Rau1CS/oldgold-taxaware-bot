"""Configuration utilities for OldGold."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Chain:
    name: str
    rpc: str
    router: str
    factory: str
    wrapped: str


CHAIN_CONFIGS: Dict[str, Chain] = {
    "eth": Chain(
        name="eth",
        rpc=os.getenv("RPC_ETH", ""),
        router="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        factory="0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
        wrapped="0xC02aaA39b223FE8D0A0e5C4f27eAD9083C756Cc2",
    ),
    "bsc": Chain(
        name="bsc",
        rpc=os.getenv("RPC_BSC", ""),
        router="0x10ED43C718714eb63d5aA57B78B54704E256024E",
        factory="0xBCfCcbde45cE874adCB698cC183deBcF17952812",
        wrapped="0xBB4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    ),
}

SUBGRAPHS = {
    "eth_univ2": os.getenv(
        "SUBGRAPH_ETH_UNIV2",
        "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2",
    )
}

# generic env helpers
OG_MIN_LIQ_USD = float(os.getenv("OG_MIN_LIQ_USD", "10000"))
OG_MAX_PAGES = int(os.getenv("OG_MAX_PAGES", "5"))
OG_LIMIT = int(os.getenv("OG_LIMIT", "200"))
MAX_FEE_GWEI = float(os.getenv("MAX_FEE_GWEI", "15"))
PRIO_FEE_GWEI = float(os.getenv("PRIO_FEE_GWEI", "1.5"))
PK = os.getenv("PK")
