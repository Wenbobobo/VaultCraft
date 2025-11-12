from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app


def _seed_deployments(tmp_path, payload: dict | None = None) -> None:
    deployments_dir = tmp_path / "deployments"
    deployments_dir.mkdir(parents=True, exist_ok=True)
    doc = payload or {"network": "hyperTestnet", "deployments": []}
    (deployments_dir / "hyper-testnet.json").write_text(json.dumps(doc))


def test_vault_risk_get_and_update(monkeypatch, tmp_path):
    from app import main as main_mod

    monkeypatch.setattr(main_mod, "REPO_ROOT", tmp_path, raising=False)
    _seed_deployments(
        tmp_path,
        {
            "network": "hyperTestnet",
            "deployments": [
                {"vault": "0xABC", "asset": "0xASSET", "risk": {"minLeverage": 1.0}},
            ],
        },
    )
    client = TestClient(app)
    resp = client.get("/api/v1/vaults/0xABC/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert data["override"]["minLeverage"] == 1.0
    assert data["effective"]["minLeverage"] == 1.0

    update = client.put(
        "/api/v1/vaults/0xABC/risk",
        json={"maxNotionalUsd": 5_000, "allowedSymbols": ["btc", "ETH"]},
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["override"]["maxNotionalUsd"] == 5000
    assert updated["override"]["allowedSymbols"] == "BTC,ETH"

    cleared = client.put("/api/v1/vaults/0xABC/risk", json={})
    assert cleared.status_code == 200
    assert cleared.json()["override"] == {}

    stored = json.loads((tmp_path / "deployments" / "hyper-testnet.json").read_text())
    assert "risk" not in stored["deployments"][0]


def test_vault_risk_creates_entry(monkeypatch, tmp_path):
    from app import main as main_mod

    monkeypatch.setattr(main_mod, "REPO_ROOT", tmp_path, raising=False)
    _seed_deployments(tmp_path)
    client = TestClient(app)
    resp = client.put("/api/v1/vaults/0xNEW/risk", json={"minLeverage": 2})
    assert resp.status_code == 200
    doc = json.loads((tmp_path / "deployments" / "hyper-testnet.json").read_text())
    assert doc["deployments"][0]["vault"] == "0xNEW"
    assert doc["deployments"][0]["risk"]["minLeverage"] == 2.0
