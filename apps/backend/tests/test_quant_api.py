from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.settings import settings


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
