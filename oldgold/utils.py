"""Utility helpers."""
from __future__ import annotations

import json
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def load_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def now_deadline(minutes: float) -> int:
    """Return unix timestamp minutes from now."""
    return int(time.time() + minutes * 60)


def to_checksum(w3, addr: str) -> str:
    return w3.to_checksum_address(addr)


def wei_to_eth(wei: int) -> float:
    return wei / 10**18


def retry(times: int, func: Callable[[], T]) -> T:
    """Very small retry helper."""
    last_err = None
    for _ in range(times):
        try:
            return func()
        except Exception as e:  # pragma: no cover - simple util
            last_err = e
            time.sleep(0.5)
    raise last_err


def retry_call(n: int, fn: Callable[[], T], delay: float = 0.3) -> T:
    for i in range(n):
        try:
            return fn()
        except Exception:
            if i == n - 1:
                raise
            time.sleep(delay * (2**i))
