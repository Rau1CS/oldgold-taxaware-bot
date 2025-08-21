from web3 import Web3
import os, json
from ..config import CHAIN_CONFIGS, PK

WBNB_ABI = [{"name": "deposit", "type": "function", "stateMutability": "payable", "inputs": [], "outputs": []}]

def main(chain: str = "bsc", amount_eth: float = 0.001):
    cfg = CHAIN_CONFIGS[chain]
    w3 = Web3(Web3.HTTPProvider(cfg.rpc))
    acct = w3.eth.account.from_key(PK)
    me = acct.address
    wbnb = w3.eth.contract(address=cfg.wrapped, abi=WBNB_ABI)
    tx = wbnb.functions.deposit().build_transaction(
        {
            "from": me,
            "value": w3.to_wei(amount_eth, "ether"),
            "nonce": w3.eth.get_transaction_count(me),
            "maxFeePerGas": w3.to_wei(float(os.getenv("MAX_FEE_GWEI", "3")), "gwei"),
            "maxPriorityFeePerGas": w3.to_wei(float(os.getenv("PRIO_FEE_GWEI", "1")), "gwei"),
            "gas": 120_000,
        }
    )
    stx = w3.eth.account.sign_transaction(tx, PK)
    h = w3.eth.send_raw_transaction(stx.rawTransaction)
    print(json.dumps({"tx": h.hex()}, indent=2))


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--chain", default="bsc")
    p.add_argument("--amount", type=float, default=0.001)
    a = p.parse_args()
    main(chain=a.chain, amount_eth=a.amount)
