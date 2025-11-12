from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import app
from app.settings import settings
from app.positions import set_profile
from app.events import store as event_store
from app import main as main_mod


def test_quant_api_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "QUANT_API_KEYS", "", raising=False)
    c = TestClient(app)
    resp = c.get("/api/v1/quant/positions")
    assert resp.status_code == 503


def test_quant_api_success(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "QUANT_API_KEYS", "alpha,beta", raising=False)
    monkeypatch.setattr(settings, "QUANT_RATE_LIMIT_PER_MIN", 5, raising=False)
    monkeypatch.setenv("POSITIONS_FILE", str(tmp_path / "positions.json"))
    from app import main as main_mod
    class FakePrice:
        def get_index_prices(self, symbols):
            return {s: 1000.0 for s in symbols}
    monkeypatch.setattr(main_mod, "_price_provider", FakePrice())
    c = TestClient(app)
    unauthorized = c.get("/api/v1/quant/positions")
    assert unauthorized.status_code == 401

    ok = c.get("/api/v1/quant/positions", headers={"X-Quant-Key": "alpha"})
    assert ok.status_code == 200
    data = ok.json()
    assert "cash" in data and "positions" in data

    price = c.get("/api/v1/quant/prices", params={"symbols": "ETH,BTC"}, headers={"X-Quant-Key": "alpha"})
    assert price.status_code == 200
    assert "prices" in price.json()

    markets = c.get("/api/v1/quant/markets", headers={"X-Quant-Key": "alpha"})
    assert markets.status_code == 200
    assert "pairs" in markets.json()

    # exceed rate limit
    for _ in range(5):
        c.get("/api/v1/quant/positions", headers={"X-Quant-Key": "alpha"})
    rate = c.get("/api/v1/quant/positions", headers={"X-Quant-Key": "alpha"})
    assert rate.status_code == 429

    with c.websocket_connect("/ws/quant?vault=_global&interval=1", headers={"X-Quant-Key": "beta"}) as ws:
        data = ws.receive_json()
        assert data["type"] == "quant_snapshot"


def test_quant_ws_includes_events_and_deltas(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "QUANT_API_KEYS", "alpha", raising=False)
    monkeypatch.setattr(settings, "QUANT_RATE_LIMIT_PER_MIN", 10, raising=False)
    monkeypatch.setattr(settings, "EXEC_ALLOWED_SYMBOLS", "ETH,BTC", raising=False)
    vault = "vault-quant-ws"
    monkeypatch.setenv("POSITIONS_FILE", str(tmp_path / "positions.json"))
    from app import main as main_mod

    class FakePrice:
        def get_index_prices(self, symbols):
            return {s: 1500.0 for s in symbols}

    monkeypatch.setattr(main_mod, "_price_provider", FakePrice())
    set_profile(vault, {"cash": 1_000_000.0, "positions": {"ETH": 1.0}, "denom": 1_000_000.0})
    event_store.add(vault, {"type": "exec_open", "status": "dry_run", "symbol": "ETH"})

    c = TestClient(app)
    with c.websocket_connect(f"/ws/quant?vault={vault}&interval=0.1", headers={"X-Quant-Key": "alpha"}) as ws:
        first = ws.receive_json()
        assert first["events"], "expected bootstrap events"
        assert first["events"][-1]["type"] == "exec_open"
        assert "deltas" not in first or "positions" not in first.get("deltas", {})

        set_profile(
            vault,
            {"cash": 1_000_000.0, "positions": {"ETH": 3.0, "BTC": -1.0}, "denom": 1_000_000.0},
        )
        event_store.add(vault, {"type": "fill", "status": "applied", "symbol": "ETH", "side": "buy"})
        time.sleep(0.2)
        second = ws.receive_json()
        assert second["events"], "expected streaming events"
        assert second["events"][-1]["type"] == "fill"
        assert "deltas" in second
        delta = second["deltas"]["positions"]
        assert delta["hyper::ETH"] == 2.0
        assert delta["hyper::BTC"] == -1.0


def test_quant_orders_require_flag(monkeypatch):
    monkeypatch.setattr(settings, "QUANT_API_KEYS", "alpha", raising=False)
    monkeypatch.setattr(settings, "ENABLE_QUANT_ORDERS", False, raising=False)
    c = TestClient(app)
    resp = c.post(
        "/api/v1/quant/orders/open",
        json={"symbol": "ETH", "size": 1, "side": "buy", "venue": "hyper"},
        headers={"X-Quant-Key": "alpha"},
    )
    assert resp.status_code == 503


def test_quant_orders_open_close(monkeypatch):
    monkeypatch.setattr(settings, "QUANT_API_KEYS", "alpha", raising=False)
    monkeypatch.setattr(settings, "ENABLE_QUANT_ORDERS", True, raising=False)
    calls: dict[str, tuple] = {}

    class DummySvc:
        def open(self, vault, order):
            calls["open"] = (vault, order)
            return {"ok": True, "dry_run": True}

        def close(self, vault, symbol, size, venue="hyper"):
            calls["close"] = (vault, symbol, size, venue)
            return {"ok": True}

    monkeypatch.setattr(main_mod, "ExecService", lambda: DummySvc())
    c = TestClient(app)
    resp = c.post(
        "/api/v1/quant/orders/open",
        json={
            "symbol": "ETH",
            "size": 2.5,
            "side": "buy",
            "reduce_only": False,
            "leverage": 3,
            "vault": "vault-open",
            "venue": "hyper",
        },
        headers={"X-Quant-Key": "alpha"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["ok"] is True
    assert data["venue"] == "hyper"
    assert calls["open"][0] == "vault-open"
    assert calls["open"][1].symbol == "ETH"
    assert calls["open"][1].leverage == 3

    resp_close = c.post(
        "/api/v1/quant/orders/close",
        json={"symbol": "ETH", "vault": "vault-open", "size": 1.0, "venue": "mock_gold"},
        headers={"X-Quant-Key": "alpha"},
    )
    assert resp_close.status_code == 200
    close_body = resp_close.json()
    assert close_body["venue"] == "mock_gold"
    assert calls["close"] == ("vault-open", "ETH", 1.0, "mock_gold")
