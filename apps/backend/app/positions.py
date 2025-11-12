from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple


def _repo_root() -> Path:
    root = Path(__file__).resolve()
    for _ in range(10):
        if (root / ".git").exists() or (root / "README.md").exists():
            break
        if root.parent == root:
            break
        root = root.parent
    return root


def _positions_path() -> Path:
    p = os.getenv("POSITIONS_FILE") or "deployments/positions.json"
    path = Path(p)
    if not path.is_absolute():
        path = _repo_root() / path
    return path


def _read_all() -> Dict[str, Any]:
    store = _positions_path()
    if not store.exists():
        return {}
    try:
        return json.loads(store.read_text() or "{}")
    except Exception:
        return {}


def _write_all(data: Dict[str, Any]) -> None:
    store = _positions_path()
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _compose_key(symbol: str, venue: str | None) -> str:
    venue_key = (venue or "hyper").lower()
    return f"{venue_key}::{str(symbol).upper()}"


def _split_key(raw: str) -> Tuple[str, str]:
    if "::" in raw:
        venue, sym = raw.split("::", 1)
        return venue.lower(), sym.upper()
    return "hyper", raw.upper()


def _prepare_raw_positions(profile: Dict[str, Any]) -> Dict[str, float]:
    if "positionsFlat" in profile:
        source = dict(profile.get("positionsFlat", {}))
        return {str(k): float(v) for k, v in source.items()}
    raw: Dict[str, float] = {}
    by_venue = profile.get("positionsByVenue")
    if isinstance(by_venue, dict):
        for venue, entries in by_venue.items():
            for sym, val in dict(entries).items():
                raw[_compose_key(sym, venue)] = float(val)
        return raw
    positions = profile.get("positions")
    if isinstance(positions, dict):
        for sym, val in positions.items():
            raw[_compose_key(sym, "hyper")] = float(val)
    return raw


def get_profile(vault_id: str) -> Dict[str, Any]:
    """Return profile dict with aggregated + per-venue exposure."""
    data = _read_all()
    prof = data.get(vault_id, {})
    raw_positions = {str(k): float(v) for k, v in dict(prof.get("positions", {})).items()}
    per_venue: Dict[str, Dict[str, float]] = {}
    aggregated: Dict[str, float] = {}
    for key, val in raw_positions.items():
        venue, sym = _split_key(key)
        venue_bucket = per_venue.setdefault(venue, {})
        venue_bucket[sym] = venue_bucket.get(sym, 0.0) + val
        aggregated[sym] = aggregated.get(sym, 0.0) + val
    cash = float(prof.get("cash", 1_000_000.0))
    denom = float(prof.get("denom", max(cash, 1.0)))
    return {
        "cash": cash,
        "positions": aggregated,
        "positionsByVenue": per_venue,
        "positionsFlat": raw_positions,
        "denom": denom,
    }


def set_profile(vault_id: str, profile: Dict[str, Any]) -> None:
    raw = _prepare_raw_positions(profile)
    cash = float(profile.get("cash", 0.0))
    denom = float(profile.get("denom", max(cash, 1.0)))
    data = _read_all()
    data[vault_id] = {"cash": cash, "positions": raw, "denom": denom}
    _write_all(data)


def apply_fill(vault_id: str, symbol: str, size: float, side: str, *, venue: str = "hyper") -> Dict[str, Any]:
    """Apply a filled order (open) and persist."""
    delta = float(size) if side == "buy" else -float(size)
    data = _read_all()
    prof = dict(data.get(vault_id, {}))
    raw = {str(k): float(v) for k, v in dict(prof.get("positions", {})).items()}
    key = _compose_key(symbol, venue)
    raw[key] = raw.get(key, 0.0) + delta
    prof["positions"] = raw
    prof.setdefault("cash", 1_000_000.0)
    prof.setdefault("denom", max(float(prof["cash"]), 1.0))
    data[vault_id] = prof
    _write_all(data)
    return get_profile(vault_id)


def apply_close(vault_id: str, symbol: str, size: float | None = None, *, venue: str = "hyper") -> Dict[str, Any]:
    """Reduce exposure. If size=None, fully close the venue-specific leg."""
    data = _read_all()
    prof = dict(data.get(vault_id, {}))
    raw = {str(k): float(v) for k, v in dict(prof.get("positions", {})).items()}
    key = _compose_key(symbol, venue)
    cur = raw.get(key, 0.0)
    if size is None:
        raw[key] = 0.0
    else:
        s = float(size)
        if cur > 0:
            raw[key] = max(0.0, cur - s)
        elif cur < 0:
            raw[key] = min(0.0, cur + s)
        else:
            raw[key] = 0.0
    prof["positions"] = raw
    prof.setdefault("cash", 1_000_000.0)
    prof.setdefault("denom", max(float(prof["cash"]), 1.0))
    data[vault_id] = prof
    _write_all(data)
    return get_profile(vault_id)
