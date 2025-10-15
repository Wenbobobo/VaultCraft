from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_metrics_post():
    c = TestClient(app)
    nav = [1.0, 1.01, 0.99, 1.02]
    r = c.post("/metrics", json=nav)
    assert r.status_code == 200
    body = r.json()
    for k in ["ann_return", "ann_vol", "sharpe", "mdd", "recovery_days"]:
        assert k in body


def test_api_metrics_series_query():
    c = TestClient(app)
    r = c.get("/api/v1/metrics/0xabc", params={"series": "1,1.01,1.02"})
    assert r.status_code == 200
    body = r.json()
    assert body["ann_return"] > 0


def test_api_nav_and_events():
    c = TestClient(app)
    r = c.get("/api/v1/nav/0xabc", params={"window": 10})
    assert r.status_code == 200
    nav = r.json()["nav"]
    assert isinstance(nav, list) and len(nav) == 10

    r2 = c.get("/api/v1/events/0xabc")
    assert r2.status_code == 200
    assert isinstance(r2.json()["events"], list)

