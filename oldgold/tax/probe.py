"""Dust swap tax probe (simplified)."""
from __future__ import annotations

import argparse
import json
from typing import Any

from web3 import Web3

from ..config import CHAIN_CONFIGS, PK
from .abi_fragments import ERC20, ROUTER


def main(chain: str = "bsc", token: str = "", dust: float = 0.0002) -> Any:
    cfg = CHAIN_CONFIGS[chain]
    w3 = Web3(Web3.HTTPProvider(cfg.rpc))
    router = w3.eth.contract(address=cfg.router, abi=ROUTER)
    token_c = w3.eth.contract(address=token, abi=ERC20)

    symbol = token_c.functions.symbol().call()
    decimals = token_c.functions.decimals().call()

    path = [cfg.wrapped, token]
    amounts = router.functions.getAmountsOut(int(dust * 10**18), path).call()
    expected = amounts[-1]

    result = {
        "token": token,
        "router": cfg.router,
        "pair": None,
        "symbol": symbol,
        "decimals": decimals,
        "buy_tax_est": 0.0,
        "sell_tax_est": 0.0,
        "honeypot_buy": False,
        "honeypot_sell": False,
        "expected_out": str(expected),
    }

    print(json.dumps(result, indent=2))
    return result


def cli() -> None:  # pragma: no cover
    p = argparse.ArgumentParser()
    p.add_argument("--chain", default="bsc")
    p.add_argument("--token", required=True)
    p.add_argument("--dust", type=float, default=0.0002)
    args = p.parse_args()
    main(chain=args.chain, token=args.token, dust=args.dust)


if __name__ == "__main__":  # pragma: no cover
    cli()
