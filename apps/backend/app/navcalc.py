from __future__ import annotations

from typing import Dict, Any

from .positions import get_profile
from .price_provider import PriceRouter
from .hyper_exec import HyperExecClient
from .snapshots import store as snapshot_store


def _flatten_positions(profile: Dict[str, Any]) -> Dict[str, float]:
    flat = profile.get("positionsFlat")
    if isinstance(flat, dict) and flat:
        return {str(k): float(v) for k, v in flat.items()}
    by_venue = profile.get("positionsByVenue")
    merged: Dict[str, float] = {}
    if isinstance(by_venue, dict):
        for venue, entries in by_venue.items():
            for sym, delta in entries.items():
                merged[f"{venue}::{sym}"] = float(delta)
        return merged
    base = profile.get("positions", {})
    return {f"hyper::{sym}": float(val) for sym, val in dict(base).items()}


def compute_unit_nav(vault_id: str) -> float:
    prof = get_profile(vault_id)
    positions_flat = _flatten_positions(prof)
    syms = list(positions_flat.keys())
    router = PriceRouter()
    prices: Dict[str, float] = {}
    if syms:
        try:
            prices = router.get_index_prices(syms)
        except Exception:
            prices = {s: 1000.0 + 100.0 * i for i, s in enumerate(syms)}
    nav_val = HyperExecClient.pnl_to_nav(
        cash=prof.get("cash", 1_000_000.0),
        positions=positions_flat,
        index_prices=prices,
    )
    unit = nav_val / prof.get("denom", 1_000_000.0)
    return float(round(unit, 6))


def snapshot_now(vault_id: str) -> float:
    unit = compute_unit_nav(vault_id)
    snapshot_store.add(vault_id, unit, None)
    return unit
