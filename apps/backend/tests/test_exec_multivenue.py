from __future__ import annotations

from app.exec_service import ExecService
from app.hyper_exec import Order


def test_mock_gold_driver_allows_xau(monkeypatch, tmp_path):
    monkeypatch.setenv("EXEC_ALLOWED_VENUES", "hyper,mock_gold")
    monkeypatch.setenv("EXEC_ALLOWED_SYMBOLS", "ETH,XAU")
    monkeypatch.setenv("POSITIONS_FILE", str(tmp_path / "positions.json"))
    monkeypatch.setattr(
        "app.exec_service.PriceRouter.get_index_prices",
        lambda self, symbols: {s: 2000.0 for s in symbols},
        raising=False,
    )
    svc = ExecService()

    res = svc.open("vault-xau", Order(symbol="XAU", size=1.0, side="buy", venue="mock_gold"))
    assert res["ok"] is True
    assert res["dry_run"] is True
    assert res["venue"] == "mock_gold"

    res_close = svc.close("vault-xau", symbol="XAU", venue="mock_gold")
    assert res_close["ok"] is True
    assert res_close["dry_run"] is True
