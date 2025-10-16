from fastapi import FastAPI
from typing import Optional, List, Dict
import os
import json
from pathlib import Path

from .metrics import compute_metrics
from .hyper_client import HyperHTTP, DEFAULT_API
from .price_provider import PriceRouter, CachedPriceRouter
from .hyper_exec import HyperExecClient
from .cache import TTLCache
from .settings import settings

app = FastAPI(title="VaultCraft v0 API")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/metrics")
def metrics_endpoint(nav_series: list[float]):
    """Compute basic metrics from a NAV series (daily)."""
    return compute_metrics(nav_series)


# --- v1 API skeleton ---
@app.get("/api/v1/metrics/{address}")
def api_metrics(address: str, series: Optional[str] = None):
    """Compute metrics for a vault address.

    - Optional query `series` as comma-separated NAV values for demo/testing.
    - In production, NAV would be sourced from storage/indexer.
    """
    if series:
        try:
            nav = [float(x) for x in series.split(",") if x]
        except ValueError:
            return {"error": "invalid series"}
        return compute_metrics(nav)
    # Fallback demo series
    demo = [1.0, 1.01, 0.99, 1.03, 1.05]
    return compute_metrics(demo)


_nav_cache = TTLCache[str, List[float]](ttl_seconds=float(getattr(settings, "NAV_CACHE_TTL", 2.0)))


@app.get("/api/v1/nav/{address}")
def api_nav(address: str, window: int = 30):
    """Return NAV series for a vault.

    v0 demo: compute NAV from a static cash+positions profile per vault id using
    current index prices. Series is a flat timeline using the same NAV value
    repeated, suitable for UI until storage/backfill is added.
    """
    cache_key = f"{address}:{window}"
    cached = _nav_cache.get(cache_key)
    if cached is not None:
        return {"address": address, "nav": cached}
    profiles = _demo_nav_profiles()
    profile = profiles.get(address) or profiles.get("default")
    router = PriceRouter()
    syms = list(profile["positions"].keys()) if profile else []
    try:
        prices = router.get_index_prices(syms) if syms else {}
    except Exception:
        prices = {s: 1000.0 + 100.0 * i for i, s in enumerate(syms)}
    nav_val = HyperExecClient.pnl_to_nav(cash=profile.get("cash", 1_000_000.0), positions=profile.get("positions", {}), index_prices=prices)
    nav = [round(nav_val / profile.get("denom", 1_000_000.0), 6)] * max(1, window)
    _nav_cache.set(cache_key, nav)
    return {"address": address, "nav": nav}


@app.get("/api/v1/events/{address}")
def api_events(address: str):
    """Return recent events (placeholder). In production, chain + offchain events."""
    return {
        "address": address,
        "events": [
            {"type": "init", "ts": 0, "msg": "vault created"},
            {"type": "param", "ts": 1, "msg": "perf_fee_bps=1000"},
        ],
    }


# --- Markets & Prices ---
def _load_pairs_from_deployments() -> List[Dict[str, object]]:
    f = Path("deployments") / "hyper-testnet.json"
    if f.exists():
        try:
            data = json.loads(f.read_text())
            pairs = data.get("config", {}).get("pairs", [])
            if isinstance(pairs, list) and pairs:
                return pairs
        except Exception:
            pass
    return [{"symbol": "BTC", "leverage": 5}, {"symbol": "ETH", "leverage": 5}]


@app.get("/api/v1/markets")
def api_markets():
    return {"pairs": _load_pairs_from_deployments()}


_price_provider = CachedPriceRouter()


@app.get("/api/v1/price")
def api_price(symbols: str):
    """Return prices for given symbols, comma-separated."""
    syms = [s for s in symbols.split(",") if s]
    try:
        prices = _price_provider.get_index_prices(syms)
        if not prices:
            raise RuntimeError("empty prices")
    except Exception:
        # graceful fallback: deterministic demo pricing
        prices = {s: 1000.0 + 100.0 * i for i, s in enumerate(syms)}
    return {"prices": prices}


# --- Vaults directory (demo) ---
def _demo_vaults() -> List[Dict[str, object]]:
    return [
        {
            "id": "0x1234...5678",
            "name": "Alpha Momentum Strategy",
            "type": "public",
        },
        {
            "id": "0x8765...4321",
            "name": "Quant Arbitrage Fund",
            "type": "private",
        },
    ]


def _demo_nav_profiles() -> Dict[str, Dict[str, object]]:
    """Cash + positions profile for demo NAV computation.

    denom: normalize NAV to unit value (e.g., total shares or initial AUM)
    """
    return {
        "0x1234...5678": {
            "cash": 1_000_000.0,
            "positions": {"BTC": 0.1, "ETH": 2.0},
            "denom": 1_000_000.0,
        },
        "0x8765...4321": {
            "cash": 500_000.0,
            "positions": {"BTC": -0.05, "ETH": 1.0},
            "denom": 500_000.0,
        },
        "default": {
            "cash": 1_000_000.0,
            "positions": {"BTC": 0.0, "ETH": 0.0},
            "denom": 1_000_000.0,
        },
    }


@app.get("/api/v1/vaults")
def api_vaults():
    return {"vaults": _demo_vaults()}


@app.get("/api/v1/vaults/{vault_id}")
def api_vault_detail(vault_id: str):
    # basic info from demo list
    info = next((v for v in _demo_vaults() if v["id"] == vault_id), None)
    if info is None:
        info = {"id": vault_id, "name": "Vault", "type": "private"}
    # demo NAV
    nav_series = api_nav(vault_id, window=60)["nav"]
    m = compute_metrics(nav_series)
    return {
        **info,
        "metrics": m,
        "unitNav": nav_series[-1] if nav_series else 1.0,
        "lockDays": 1,
        "performanceFee": 10,
        "managementFee": 0,
        "aum": 1_000_000,
        "totalShares": 1_000_000,
    }
