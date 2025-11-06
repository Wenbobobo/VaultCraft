from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional


FetchStatusFn = Callable[[], Dict[str, Any]]
FetchVaultsFn = Callable[[], Iterable[str]]
FetchMetricsFn = Callable[[str], Dict[str, Any]]
SinkFn = Callable[[Dict[str, Any]], None]
SleepFn = Callable[[float], None]
NowFn = Callable[[], float]


@dataclass
class SoakEntry:
    timestamp: float
    status: Dict[str, Any]
    vaults: List[str]
    metrics: Dict[str, Dict[str, Any]]
    errors: List[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def run_soak(
    duration_sec: float,
    interval_sec: float,
    fetch_status: FetchStatusFn,
    fetch_vaults: FetchVaultsFn,
    fetch_metrics: FetchMetricsFn,
    sink: SinkFn,
    sleep: SleepFn = time.sleep,
    now: NowFn = time.time,
) -> Dict[str, Any]:
    """Run soak loop, returning summary statistics."""
    if interval_sec <= 0:
        raise ValueError("interval_sec must be > 0")
    start = now()
    deadline = start + duration_sec
    iterations = 0
    errors_total: List[str] = []

    while True:
        current = now()
        if current >= deadline:
            break
        status: Dict[str, Any] = {}
        vault_ids: List[str] = []
        metrics_bundle: Dict[str, Dict[str, Any]] = {}
        iteration_errors: List[str] = []

        try:
            status = fetch_status()
        except Exception as exc:  # pragma: no cover
            msg = f"status_error:{type(exc).__name__}:{exc}"
            iteration_errors.append(msg)

        try:
            vault_ids = list(fetch_vaults())
        except Exception as exc:  # pragma: no cover
            msg = f"vaults_error:{type(exc).__name__}:{exc}"
            iteration_errors.append(msg)

        for vid in vault_ids:
            try:
                metrics_bundle[vid] = fetch_metrics(vid)
            except Exception as exc:  # pragma: no cover
                msg = f"metrics_error:{vid}:{type(exc).__name__}:{exc}"
                iteration_errors.append(msg)

        entry = SoakEntry(
            timestamp=current,
            status=status,
            vaults=vault_ids,
            metrics=metrics_bundle,
            errors=iteration_errors,
        )
        sink(asdict(entry))
        errors_total.extend(iteration_errors)
        iterations += 1

        next_sleep = min(interval_sec, max(0.0, deadline - now()))
        if next_sleep > 0:
            sleep(next_sleep)

    end = now()
    return {
        "iterations": iterations,
        "errors": errors_total,
        "start_ts": start,
        "end_ts": end,
        "elapsed_sec": end - start,
    }


def file_sink(path: Path) -> SinkFn:
    path.parent.mkdir(parents=True, exist_ok=True)

    def _sink(payload: Dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False))
            fh.write("\n")

    return _sink
