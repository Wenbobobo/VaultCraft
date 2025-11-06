from __future__ import annotations

from typing import Dict, List

import pytest

from app.soak import run_soak


def test_run_soak_collects_iterations():
    outputs: List[Dict] = []

    class Clock:
        def __init__(self):
            self.t = 0.0

        def now(self) -> float:
            return self.t

        def sleep(self, dt: float) -> None:
            self.t += dt

    clock = Clock()

    status_data = {"ok": True}
    vaults = ["0x1", "0x2"]

    def fetch_status():
        return status_data

    def fetch_vaults():
        return vaults

    def fetch_metrics(vault_id: str):
        return {"vault": vault_id, "ann_return": 0.1}

    summary = run_soak(
        duration_sec=0.25,
        interval_sec=0.1,
        fetch_status=fetch_status,
        fetch_vaults=fetch_vaults,
        fetch_metrics=fetch_metrics,
        sink=lambda entry: outputs.append(entry),
        sleep=clock.sleep,
        now=clock.now,
    )

    assert summary["iterations"] >= 2
    assert outputs, "should capture entries"
    for entry in outputs:
        assert entry["status"]["ok"] is True
        assert entry["vaults"] == vaults
        for vid in vaults:
            assert entry["metrics"][vid]["vault"] == vid


def test_run_soak_interval_guard():
    with pytest.raises(ValueError):
        run_soak(
            duration_sec=10,
            interval_sec=0,
            fetch_status=lambda: {},
            fetch_vaults=lambda: [],
            fetch_metrics=lambda _: {},
            sink=lambda _: None,
        )
