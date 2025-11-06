from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.settings import settings


def test_snapshot_post_and_get_window(monkeypatch):
    c = TestClient(app)
    vid = "0xsnap"
    # Push three snapshots with explicit navs
    token = "snap-token"
    monkeypatch.setattr(settings, "DEPLOYMENT_API_TOKEN", token, raising=False)
    for v in [1.0, 1.1, 1.2]:
        r = c.post(f"/api/v1/nav/snapshot/{vid}", params={"nav": v})
        assert r.status_code == 401
        r_ok = c.post(
            f"/api/v1/nav/snapshot/{vid}",
            params={"nav": v},
            headers={"X-Deployment-Key": token},
        )
        assert r_ok.status_code == 200
    r2 = c.get(f"/api/v1/nav/{vid}", params={"window": 2})
    assert r2.status_code == 200
    assert r2.json()["nav"] == [1.1, 1.2]


def test_snapshot_compute_when_nav_omitted(tmp_path, monkeypatch):
    # Prepare positions and deterministic prices to exercise compute path
    from app.positions import set_profile
    store = tmp_path / "positions.json"
    monkeypatch.setenv("POSITIONS_FILE", str(store))
    vid = "0xcomp"
    set_profile(vid, {"cash": 1000.0, "positions": {"ETH": 1.0}, "denom": 1000.0})
    from app import main as main_mod

    def fake_prices(self, symbols):
        return {s: 2000.0 for s in symbols}

    monkeypatch.setattr(main_mod.PriceRouter, "get_index_prices", fake_prices)
    c = TestClient(app)
    token = "snap-token"
    monkeypatch.setattr(settings, "DEPLOYMENT_API_TOKEN", token, raising=False)

    r = c.post(f"/api/v1/nav/snapshot/{vid}")  # no nav param → compute
    assert r.status_code == 401

    r_ok = c.post(
        f"/api/v1/nav/snapshot/{vid}",
        headers={"X-Deployment-Key": token},
    )
    assert r_ok.status_code == 200
    body = r_ok.json()
    # 1000 + 1 * 2000 = 3000; denom=1000 ⇒ unit nav=3.0
    assert abs(body["nav"] - 3.0) < 1e-9
    r2 = c.get(f"/api/v1/nav/{vid}", params={"window": 1})
    assert r2.status_code == 200
    assert abs(r2.json()["nav"][0] - 3.0) < 1e-9
