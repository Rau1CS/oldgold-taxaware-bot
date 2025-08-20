"""Dust swap tax probe using live swaps.

This module performs tiny buy and sell swaps against a router to estimate
buy and sell taxes for a token.  It sends real transactions using the
account key provided via environment variables and compares the received
amounts against ``getAmountsOut`` expectations.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any

from eth_account import Account
from web3 import Web3

from ..config import CHAIN_CONFIGS, PK
from ..logging_conf import LOGGER
from ..utils import now_deadline, retry_call
from .abi_fragments import ERC20, ROUTER
from .cache import get as cache_get, put as cache_put


def main(
    chain: str = "bsc",
    token: str = "",
    dust: float = float(os.getenv("DUST_BASE", "0.0002")),
    dry_run: bool = False,
    force_probe: bool = False,
) -> Any:
    """Execute small buy/sell swaps and estimate token taxes."""

    cfg = CHAIN_CONFIGS[chain]

    if dry_run:
        result = {
            "token": Web3.to_checksum_address(token),
            "router": cfg.router,
            "symbol": "DRY",
            "decimals": 18,
            "buy_tax_est": 0.0,
            "sell_tax_est": 0.0,
            "honeypot_buy": False,
            "honeypot_sell": False,
            "expected_buy": "0",
            "got_tokens": "0",
            "got_weth": "0",
            "tx_buy": None,
            "tx_sell": None,
            "dry_run": True,
        }
        print(json.dumps(result, indent=2))
        return result

    w3 = Web3(Web3.HTTPProvider(cfg.rpc))
    router_c = w3.eth.contract(address=cfg.router, abi=ROUTER)

    if not force_probe:
        cached = cache_get(chain, token, cfg.router)
        if cached:
            cached.pop("ts", None)
            print(json.dumps(cached, indent=2))
            return cached

    if not PK:
        raise SystemExit("PK is not set. Put a DUST-ONLY key in .env (PK=0x...)")
    acct = Account.from_key(PK)
    me = acct.address
    weth = cfg.wrapped

    def erc20(addr: str):
        return w3.eth.contract(address=addr, abi=ERC20)

    def approve(token_addr: str, spender: str, amount: int) -> None:
        tx_args = {
            "from": me,
            "nonce": w3.eth.get_transaction_count(me),
            "maxFeePerGas": w3.to_wei(float(os.getenv("MAX_FEE_GWEI", "15")), "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(float(os.getenv("PRIO_FEE_GWEI", "1.5")), "gwei"),
            "gas": 80_000,
        }
        try:
            tx = erc20(token_addr).functions.approve(spender, amount).build_transaction(tx_args)
            signed = w3.eth.account.sign_transaction(tx, PK)
            h = w3.eth.send_raw_transaction(signed.rawTransaction)
            w3.eth.wait_for_transaction_receipt(h, timeout=120)
        except Exception:
            tx0 = erc20(token_addr).functions.approve(spender, 0).build_transaction(tx_args)
            signed0 = w3.eth.account.sign_transaction(tx0, PK)
            h0 = w3.eth.send_raw_transaction(signed0.rawTransaction)
            w3.eth.wait_for_transaction_receipt(h0, timeout=120)
            tx1 = erc20(token_addr).functions.approve(spender, amount).build_transaction(tx_args)
            signed1 = w3.eth.account.sign_transaction(tx1, PK)
            h1 = w3.eth.send_raw_transaction(signed1.rawTransaction)
            w3.eth.wait_for_transaction_receipt(h1, timeout=120)

    token_c = erc20(token)
    try:
        symbol = token_c.functions.symbol().call()
    except Exception as e:
        LOGGER.warning("symbol failed: %s", e)
        symbol = ""
    try:
        decimals = token_c.functions.decimals().call()
    except Exception as e:
        LOGGER.warning("decimals failed: %s", e)
        decimals = 18

    if w3.eth.chain_id in (56, 1) and dust <= 0.0:
        raise SystemExit("dust must be > 0")

    amount_in = int(dust * 10**18)  # wrapped base assumed 18 dec

    try:
        expected_buy = retry_call(3, lambda: router_c.functions.getAmountsOut(amount_in, [weth, token]).call())[-1]
    except Exception as e:  # pragma: no cover - network dependent
        LOGGER.warning("getAmountsOut failed: %s", e)
        expected_buy = 0

    # approve router to spend wrapped base and token
    approve(weth, cfg.router, amount_in)

    nonce = w3.eth.get_transaction_count(me)
    tx_buy = router_c.functions.swapExactTokensForTokensSupportingFeeOnTransferTokens(
        amount_in, 0, [weth, token], me, now_deadline(3)
    ).build_transaction(
        {
            "from": me,
            "nonce": nonce,
            "maxFeePerGas": w3.to_wei(float(os.getenv("MAX_FEE_GWEI", "15")), "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(
                float(os.getenv("PRIO_FEE_GWEI", "1.5")), "gwei"
            ),
            "gas": 350_000,
        }
    )
    signed_buy = w3.eth.account.sign_transaction(tx_buy, PK)
    rcpt_buy = w3.eth.wait_for_transaction_receipt(
        w3.eth.send_raw_transaction(signed_buy.rawTransaction), timeout=180
    )

    bal_tok_after = token_c.functions.balanceOf(me).call()
    got_tok = bal_tok_after  # assume zero balance before

    buy_tax_est = 0.0
    if expected_buy and got_tok:
        shortfall = max(expected_buy - got_tok, 0)
        buy_tax_est = min(shortfall / max(expected_buy, 1), 0.99)
    honeypot_buy = got_tok == 0

    weth_bal = erc20(weth).functions.balanceOf(me).call()
    if weth_bal < int(dust * 10**18):
        raise SystemExit("Insufficient WETH/WBNB for dust probe. Wrap first or lower DUST_BASE")

    sell_amt = int(got_tok * 0.8)
    if sell_amt == 0:
        honeypot_sell = True
        got_weth = 0
        rcpt_sell = None
        expected_sell = 0
    else:
        approve(token, cfg.router, sell_amt)
        try:
            expected_sell = retry_call(3, lambda: router_c.functions.getAmountsOut(sell_amt, [token, weth]).call())[-1]
        except Exception as e:
            LOGGER.warning("getAmountsOut failed: %s", e)
            expected_sell = 0

        bal_weth_before = erc20(weth).functions.balanceOf(me).call()
        nonce += 1
        tx_sell = router_c.functions.swapExactTokensForTokensSupportingFeeOnTransferTokens(
            sell_amt, 0, [token, weth], me, now_deadline(3)
        ).build_transaction(
            {
                "from": me,
                "nonce": nonce,
                "maxFeePerGas": w3.to_wei(float(os.getenv("MAX_FEE_GWEI", "15")), "gwei"),
                "maxPriorityFeePerGas": w3.to_wei(
                    float(os.getenv("PRIO_FEE_GWEI", "1.5")), "gwei"
                ),
                "gas": 350_000,
            }
        )
        signed_sell = w3.eth.account.sign_transaction(tx_sell, PK)
        rcpt_sell = w3.eth.wait_for_transaction_receipt(
            w3.eth.send_raw_transaction(signed_sell.rawTransaction), timeout=180
        )

        bal_weth_after = erc20(weth).functions.balanceOf(me).call()
        got_weth = max(bal_weth_after - bal_weth_before, 0)
        honeypot_sell = got_weth == 0

    sell_tax_est = 0.0
    if expected_sell and got_weth:
        shortfall2 = max(expected_sell - got_weth, 0)
        sell_tax_est = min(shortfall2 / max(expected_sell, 1), 0.99)

    result = {
        "token": Web3.to_checksum_address(token),
        "router": cfg.router,
        "symbol": symbol,
        "decimals": decimals,
        "buy_tax_est": float(buy_tax_est),
        "sell_tax_est": float(sell_tax_est),
        "honeypot_buy": bool(honeypot_buy),
        "honeypot_sell": bool(honeypot_sell),
        "expected_buy": str(expected_buy),
        "got_tokens": str(got_tok),
        "got_weth": str(got_weth),
        "tx_buy": rcpt_buy.transactionHash.hex(),
        "tx_sell": rcpt_sell.transactionHash.hex() if not honeypot_sell else None,
        "dry_run": False,
    }

    if not force_probe:
        cache_put(chain, token, cfg.router, result)

    print(json.dumps(result, indent=2))
    return result


def cli() -> None:  # pragma: no cover
    p = argparse.ArgumentParser()
    p.add_argument("--chain", default="bsc")
    p.add_argument("--token", required=True)
    p.add_argument("--dust", type=float, default=float(os.getenv("DUST_BASE", "0.0002")))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force-probe", action="store_true")
    args = p.parse_args()
    main(chain=args.chain, token=args.token, dust=args.dust, dry_run=args.dry_run, force_probe=args.force_probe)


if __name__ == "__main__":  # pragma: no cover
    cli()

