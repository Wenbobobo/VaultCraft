from __future__ import annotations

import threading
import time
from typing import Dict

_last_ack: Dict[str, float] = {}
_lock = threading.Lock()


def record(vault: str) -> None:
    ts = time.time()
    if not vault:
        vault = "_global"
    with _lock:
        _last_ack[vault] = ts
        _last_ack["_latest"] = ts


def last(vault: str | None = None) -> float | Dict[str, float] | None:
    with _lock:
        if vault is None:
            return dict(_last_ack)
        return _last_ack.get(vault)
