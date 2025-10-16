from __future__ import annotations

from app.exec_service import ExecService
from app.hyper_exec import Order


def test_exec_validation_symbol_and_notional(monkeypatch, tmp_path):
    # Isolate positions file
    monkeypatch.setenv("POSITIONS_FILE", str(tmp_path / "positions.json"))
    monkeypatch.setenv("ENABLE_LIVE_EXEC", "0")
    # Restrict to ETH only and tiny max notional
    from app import settings as settings_mod
    monkeypatch.setenv("EXEC_ALLOWED_SYMBOLS", "ETH")
    monkeypatch.setenv("EXEC_MAX_NOTIONAL_USD", "1000")

    # Patch price to deterministic 2000 USD
    from app import exec_service as exec_mod

    class FakePR:
        def get_index_prices(self, symbols):
            return {s: 2000.0 for s in symbols}

    monkeypatch.setattr(exec_mod, "PriceRouter", lambda: FakePR())

    svc = ExecService()

    # Wrong symbol rejected
    r1 = svc.open("0xv", Order(symbol="BTC", size=1.0, side="buy"))
    assert r1["ok"] is False and "symbol not allowed" in r1["error"]

    # Notional too large: size=1 @2000 > 1000
    r2 = svc.open("0xv", Order(symbol="ETH", size=1.0, side="buy"))
    assert r2["ok"] is False and "notional exceeds" in r2["error"]

    # Allowed when size small
    r3 = svc.open("0xv", Order(symbol="ETH", size=0.4, side="buy"))
    assert r3["ok"] is True
