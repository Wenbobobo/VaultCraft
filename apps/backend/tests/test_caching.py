from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app, _price_provider, _nav_cache
from app.price_provider import PriceRouter


def test_price_cache(monkeypatch):
    calls = {"n": 0}

    def fake_prices(self, symbols):
        calls["n"] += 1
        return {s: 1000.0 for s in symbols}

    # Ensure clean cache and patch underlying PriceRouter.get_index_prices used by CachedPriceRouter
    _price_provider.cache.clear()
    monkeypatch.setattr(PriceRouter, "get_index_prices", fake_prices)

    c = TestClient(app)
    r1 = c.get("/api/v1/price", params={"symbols": "BTC,ETH"})
    assert r1.status_code == 200
    r2 = c.get("/api/v1/price", params={"symbols": "BTC,ETH"})
    assert r2.status_code == 200
    # first call populates cache, second call should not invoke underlying router
    assert calls["n"] == 1


def test_nav_cache(monkeypatch):
    # Clear cache
    _nav_cache.clear()
    # Force deterministic prices by patching PriceRouter.get_index_prices
    calls = {"n": 0}

    def fake_prices(self, symbols):
        calls["n"] += 1
        return {s: 1000.0 for s in symbols}

    monkeypatch.setattr(PriceRouter, "get_index_prices", fake_prices)
    c = TestClient(app)
    vid = "0x1234...5678"
    r1 = c.get(f"/api/v1/nav/{vid}", params={"window": 5})
    assert r1.status_code == 200
    nav1 = r1.json()["nav"]
    r2 = c.get(f"/api/v1/nav/{vid}", params={"window": 5})
    nav2 = r2.json()["nav"]
    assert nav1 == nav2
    # prices should be fetched once due to NAV cache
    assert calls["n"] == 1
