import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncio
import time
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict
from fastapi.middleware.cors import CORSMiddleware

from .metrics import compute_metrics
from .hyper_client import HyperHTTP, DEFAULT_API
from .price_provider import PriceRouter, CachedPriceRouter
from .hyper_exec import HyperExecClient, Order
from .cache import TTLCache
from .settings import settings
from .positions import get_profile
from .snapshots import store as snapshot_store
from .events import store as event_store
from .exec_service import ExecService
from .daemon import SnapshotDaemon
from .user_listener import UserEventsListener, last_ws_event
from .ack_tracker import last as last_ack_event
from .hyper_client import HyperHTTP
from .alerts import manager as alert_manager


def _repo_root() -> Path:
    root = Path(__file__).resolve().parent
    for _ in range(10):
        if (root / ".git").exists() or (root / "README.md").exists():
            return root
        if root.parent == root:
            break
        root = root.parent
    return root


REPO_ROOT = _repo_root()

_LOG_BASE_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
}


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _LOG_BASE_ATTRS or key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except TypeError:
                payload[key] = str(value)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> None:
    level_name = str(getattr(settings, "LOG_LEVEL", "INFO") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = str(getattr(settings, "LOG_FORMAT", "text") or "text").lower()
    log_path = getattr(settings, "LOG_PATH", None)

    handlers: List[logging.Handler] = []
    if log_path:
        path = Path(log_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))
    else:
        handlers.append(logging.StreamHandler(sys.stdout))

    if fmt == "json":
        formatter: logging.Formatter = JsonLogFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s - %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )

    for handler in handlers:
        handler.setFormatter(formatter)

    logging.basicConfig(level=level, handlers=handlers, force=True)
    logging.captureWarnings(True)


_configure_logging()
logger = logging.getLogger("vaultcraft.backend")
logger.propagate = False

app = FastAPI(title="VaultCraft v0 API")

_LOCAL_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_LOCAL_DEV_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_deployment_key(token: str | None) -> None:
    required = (getattr(settings, "DEPLOYMENT_API_TOKEN", None) or "").strip()
    if required and token != required:
        raise HTTPException(status_code=401, detail="invalid deployment token")


def require_deployment_key(
    request: Request, token: str | None = Header(default=None, alias="X-Deployment-Key")
):
    try:
        _validate_deployment_key(token)
    except HTTPException as exc:
        logger.warning(
            "deployment token rejected",
            extra={"event": "auth.reject", "path": request.url.path, "token_present": token is not None},
        )
        raise exc
    return token


_quant_limits: Dict[str, list[float]] = {}


def _validate_quant_key_value(key: str | None, path: str, *, increment: bool = True) -> str:
    keys_raw = getattr(settings, "QUANT_API_KEYS", None) or ""
    allowed = [k.strip() for k in keys_raw.split(",") if k.strip()]
    if not allowed:
        raise HTTPException(status_code=503, detail="quant api disabled")
    if key not in allowed:
        logger.warning(
            "quant key rejected",
            extra={"event": "auth.quant.reject", "path": path, "token_present": key is not None},
        )
        raise HTTPException(status_code=401, detail="invalid quant key")
    if increment:
        limit = max(1, int(getattr(settings, "QUANT_RATE_LIMIT_PER_MIN", 60)))
        now_ts = time.time()
        window = 60.0
        history = _quant_limits.setdefault(key, [])
        history[:] = [ts for ts in history if now_ts - ts < window]
        if len(history) >= limit:
            raise HTTPException(status_code=429, detail="quant api rate limit exceeded")
        history.append(now_ts)
    return key


def require_quant_key(
    request: Request, key: str | None = Header(default=None, alias="X-Quant-Key")
):
    _validate_quant_key_value(key, str(request.url))
    return key


@app.get("/health")
def health():
    return {"ok": True}


_snapshot_daemon: SnapshotDaemon | None = None
_user_listener: UserEventsListener | None = None


def _collect_status_snapshot(vault_id: str | None = None):
    # Sanitize settings for FE/ops visibility
    flags = {
        "enable_sdk": bool(getattr(settings, "ENABLE_HYPER_SDK", False)),
        "enable_live_exec": bool(getattr(settings, "ENABLE_LIVE_EXEC", False)),
        "enable_user_ws": bool(getattr(settings, "ENABLE_USER_WS_LISTENER", False)),
        "enable_snapshot_daemon": bool(getattr(settings, "ENABLE_SNAPSHOT_DAEMON", False)),
        "address": getattr(settings, "ADDRESS", None),
        "allowed_symbols": getattr(settings, "EXEC_ALLOWED_SYMBOLS", ""),
        "allowed_venues": getattr(settings, "EXEC_ALLOWED_VENUES", "hyper"),
        "exec_min_leverage": getattr(settings, "EXEC_MIN_LEVERAGE", None),
        "exec_max_leverage": getattr(settings, "EXEC_MAX_LEVERAGE", None),
        "exec_max_notional_usd": getattr(settings, "EXEC_MAX_NOTIONAL_USD", None),
        "exec_min_notional_usd": getattr(settings, "EXEC_MIN_NOTIONAL_USD", None),
    }
    risk_template = {
        "allowedSymbols": flags["allowed_symbols"],
        "allowedVenues": flags["allowed_venues"],
        "minLeverage": flags["exec_min_leverage"],
        "maxLeverage": flags["exec_max_leverage"],
        "minNotionalUsd": flags["exec_min_notional_usd"],
        "maxNotionalUsd": flags["exec_max_notional_usd"],
    }
    if vault_id:
        meta = _lookup_vault_meta(vault_id)
        risk_override = meta.get("risk") if isinstance(meta, dict) else None
        if isinstance(risk_override, dict) and risk_override:
            risk_template = {**risk_template, **risk_override}
    flags["risk_template"] = risk_template
    try:
        http = HyperHTTP()
        info = http.rpc_ping()
        rpc = {"rpc": http.rpc_url, "chainId": info.chain_id, "block": info.block_number}
    except Exception:
        rpc = {"rpc": getattr(settings, "HYPER_RPC_URL", None), "chainId": None, "block": None}
    # runtime daemon states
    listener_state = "disabled"
    if flags["enable_live_exec"] and flags["enable_user_ws"]:
        listener_state = "idle"
        if _user_listener and _user_listener.is_running():
            listener_state = "running"
    snapshot_state = "disabled"
    if flags["enable_snapshot_daemon"]:
        snapshot_state = "idle"
        if _snapshot_daemon and _snapshot_daemon.is_running():
            snapshot_state = "running"
    vault_key = flags["address"] or "_global"
    last_ws = None
    try:
        last_ws = last_ws_event(vault_key)
    except Exception:
        last_ws = None
    last_ack = None
    try:
        latest = last_ack_event("_latest")
        last_ack = latest
    except Exception:
        last_ack = None
    state = {
        "listener": listener_state,
        "snapshot": snapshot_state,
        "listenerLastTs": last_ws,
        "lastAckTs": last_ack,
    }
    return {"ok": True, "flags": flags, "network": rpc, "state": state}


def _positions_delta(
    previous: Dict[str, float] | None,
    current: Dict[str, Any],
    epsilon: float = 1e-9,
) -> Dict[str, float]:
    """Compute delta between two position maps."""
    if current is None:
        current = {}
    curr = {str(k): float(v) for k, v in dict(current).items()}
    if previous is None:
        return {}
    delta: Dict[str, float] = {}
    keys = set(previous.keys()) | set(curr.keys())
    for sym in keys:
        before = float(previous.get(sym, 0.0))
        after = float(curr.get(sym, 0.0))
        diff = after - before
        if abs(diff) > epsilon:
            delta[sym] = diff
    return delta


def _flat_positions(profile: Dict[str, Any]) -> Dict[str, float]:
    flat = profile.get("positionsFlat")
    if isinstance(flat, dict) and flat:
        return {str(k): float(v) for k, v in flat.items()}
    by_venue = profile.get("positionsByVenue")
    combined: Dict[str, float] = {}
    if isinstance(by_venue, dict) and by_venue:
        for venue, entries in by_venue.items():
            for sym, val in entries.items():
                combined[f"{venue}::{sym}"] = float(val)
        return combined
    positions = profile.get("positions", {})
    return {f"hyper::{sym}": float(val) for sym, val in dict(positions).items()}


@app.get("/api/v1/status")
def api_status(vault: str | None = None):
    return _collect_status_snapshot(vault)


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
    # Prefer stored snapshots if available
    series = snapshot_store.get(address, window=window)
    if series:
        nav = [round(v, 6) for (_, v) in series]
        _nav_cache.set(cache_key, nav)
        return {"address": address, "nav": nav}

    profile = get_profile(address)
    router = PriceRouter()
    positions_flat = _flat_positions(profile)
    syms = list(positions_flat.keys())
    try:
        prices = router.get_index_prices(syms) if syms else {}
    except Exception:
        prices = {s: 1000.0 + 100.0 * i for i, s in enumerate(syms)}
    nav_val = HyperExecClient.pnl_to_nav(
        cash=profile.get("cash", 1_000_000.0), positions=positions_flat, index_prices=prices
    )
    nav = [round(nav_val / profile.get("denom", 1_000_000.0), 6)] * max(1, window)
    _nav_cache.set(cache_key, nav)
    return {"address": address, "nav": nav}


@app.get("/api/v1/nav_series/{address}")
def api_nav_series(address: str, since: float | None = None, window: int | None = None):
    if since is not None:
        series = snapshot_store.get_since(address, since_ts=float(since))
    else:
        w = window if window is not None else 60
        series = snapshot_store.get(address, window=int(w))
    return {"address": address, "series": [{"ts": ts, "nav": round(nav, 6)} for (ts, nav) in series]}


@app.post("/api/v1/nav/snapshot/{address}")
def api_nav_snapshot(
    address: str,
    nav: float | None = None,
    ts: float | None = None,
    _token: str | None = Depends(require_deployment_key),
):
    """Create a NAV snapshot for a vault.

    If `nav` is omitted, compute from positions + prices at call time.
    """
    if nav is None:
        profile = get_profile(address)
        positions_flat = _flat_positions(profile)
        syms = list(positions_flat.keys())
        router = PriceRouter()
        try:
            prices = router.get_index_prices(syms) if syms else {}
        except Exception:
            prices = {s: 1000.0 + 100.0 * i for i, s in enumerate(syms)}
        nav_val = HyperExecClient.pnl_to_nav(
            cash=profile.get("cash", 1_000_000.0),
            positions=positions_flat,
            index_prices=prices,
        )
        nav = round(nav_val / profile.get("denom", 1_000_000.0), 6)
    snapshot_store.add(address, float(nav), ts)
    _nav_cache.clear()
    logger.info(
        "nav snapshot stored",
        extra={
            "event": "nav.snapshot",
            "vault": address,
            "nav": float(nav),
            "ts": ts,
        },
    )
    try:
        alert_manager.on_nav(address, float(nav))
    except Exception:
        pass
    return {"ok": True, "address": address, "nav": nav}


@app.get("/api/v1/events/{address}")
def api_events(address: str, limit: int | None = None, since: float | None = None, types: Optional[str] = None):
    ty = [t for t in (types.split(',') if types else []) if t]
    ev = event_store.list(address, limit=limit, since=since, types=ty if ty else None)
    return {"address": address, "events": ev}


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


def _deployments_path() -> Path:
    return REPO_ROOT / "deployments" / "hyper-testnet.json"


def _read_deployments_doc() -> Dict[str, Any]:
    f = _deployments_path()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text() or "{}")
    except Exception:
        return {}


def _write_deployments_doc(doc: Dict[str, Any]) -> None:
    f = _deployments_path()
    f.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False)
    f.write_text(text + "\n", encoding="utf-8")


def _ensure_deployments_container(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    deployments = doc.get("deployments")
    if isinstance(deployments, list):
        cleaned = [d for d in deployments if isinstance(d, dict)]
        doc["deployments"] = cleaned
        return cleaned
    cleaned: List[Dict[str, Any]] = []
    doc["deployments"] = cleaned
    legacy_vault = doc.get("vault")
    if isinstance(legacy_vault, str):
        entry: Dict[str, Any] = {"vault": legacy_vault}
        asset = doc.get("asset")
        if isinstance(asset, str) and asset:
            entry["asset"] = asset
        cleaned.append(entry)
    return cleaned


def _load_deployments_meta() -> List[Dict[str, object]]:
    data = _read_deployments_doc()
    deployments = data.get("deployments")
    if isinstance(deployments, list):
        return [d for d in deployments if isinstance(d, dict)]
    legacy = {}
    if isinstance(data.get("vault"), str):
        legacy["vault"] = data.get("vault")
    if data.get("asset"):
        legacy["asset"] = data.get("asset")
    return [legacy] if legacy.get("vault") else []


def _lookup_vault_meta(vault_id: str | None) -> Dict[str, object]:
    if not vault_id:
        return {}
    vid = vault_id.lower()
    for entry in _load_deployments_meta():
        val = entry.get("vault")
        if isinstance(val, str) and val.lower() == vid:
            return entry
    return {}


_RISK_FIELDS = {
    "allowedSymbols",
    "allowedVenues",
    "minLeverage",
    "maxLeverage",
    "minNotionalUsd",
    "maxNotionalUsd",
}


def _normalize_csv_field(value: Any, *, upper: bool = True) -> str:
    tokens: List[str] = []
    if isinstance(value, str):
        source = value.replace(";", ",")
        tokens = [t.strip() for t in source.split(",") if t.strip()]
    elif isinstance(value, list):
        tokens = [str(v).strip() for v in value if str(v).strip()]
    else:
        raise HTTPException(status_code=400, detail="expected string or list")
    if not tokens:
        return ""
    if upper:
        tokens = [t.upper() for t in tokens]
    else:
        tokens = [t.lower() for t in tokens]
    return ",".join(tokens)


def _sanitize_risk_payload(payload: Dict[str, Any]) -> tuple[Dict[str, Any], set[str]]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")
    cleaned: Dict[str, Any] = {}
    remove: set[str] = set()
    for key, value in payload.items():
        if key not in _RISK_FIELDS:
            raise HTTPException(status_code=400, detail=f"unknown field: {key}")
        if value is None:
            remove.add(key)
            continue
        if key == "allowedSymbols":
            normalized = _normalize_csv_field(value, upper=True)
            if normalized:
                cleaned[key] = normalized
            else:
                remove.add(key)
            continue
        if key == "allowedVenues":
            normalized = _normalize_csv_field(value, upper=False)
            if normalized:
                cleaned[key] = normalized
            else:
                remove.add(key)
            continue
        try:
            cleaned[key] = float(value)
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=400, detail=f"invalid value for {key}") from exc
    return cleaned, remove


def _persist_vault_risk_override(
    vault_id: str,
    to_set: Dict[str, Any],
    to_remove: set[str],
) -> Dict[str, Any]:
    doc = _read_deployments_doc()
    deployments = _ensure_deployments_container(doc)
    vid = vault_id.lower()
    target = None
    for entry in deployments:
        val = entry.get("vault")
        if isinstance(val, str) and val.lower() == vid:
            target = entry
            break
    if target is None:
        target = {"vault": vault_id}
        deployments.append(target)
    existing = dict(target.get("risk", {})) if isinstance(target.get("risk"), dict) else {}
    for field in to_remove:
        existing.pop(field, None)
    existing.update(to_set)
    cleaned = {k: v for k, v in existing.items() if v not in ("", None)}
    if cleaned:
        target["risk"] = cleaned
    else:
        target.pop("risk", None)
    _write_deployments_doc(doc)
    return cleaned


def _ensure_quant_orders_enabled() -> None:
    if not getattr(settings, "ENABLE_QUANT_ORDERS", False):
        raise HTTPException(status_code=503, detail="quant order api disabled")


class QuantOrderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    size: float
    side: str
    venue: str = "hyper"
    reduce_only: bool = False
    leverage: float | None = None
    order_type: str = "market"
    limit_price: float | None = None
    time_in_force: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    vault: str = "_global"

    def to_order(self) -> Order:
        return Order(
            symbol=self.symbol,
            size=self.size,
            side=self.side,
            venue=self.venue,
            reduce_only=self.reduce_only,
            leverage=self.leverage,
            order_type=self.order_type,
            limit_price=self.limit_price,
            time_in_force=self.time_in_force,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
        )


class QuantClosePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    size: float | None = None
    venue: str = "hyper"
    vault: str = "_global"


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


# --- Artifacts helper for FE Manager ---
@app.get("/api/v1/artifacts/vault")
def api_artifact_vault():
    """Serve Vault ABI and bytecode from Hardhat artifacts for FE deployment.

    This avoids bundling artifacts in the FE and keeps a single source of truth.
    """
    artifact = REPO_ROOT / "hardhat" / "artifacts" / "contracts" / "Vault.sol" / "Vault.json"
    if not artifact.exists():
        return {"error": "artifact not found", "path": str(artifact)}
    try:
        data = json.loads(artifact.read_text("utf-8"))
        return {"abi": data.get("abi", []), "bytecode": data.get("bytecode")}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/v1/artifacts/mockerc20")
def api_artifact_mockerc20():
    """Serve MockERC20 ABI and bytecode from Hardhat artifacts for FE dev helpers."""
    artifact = REPO_ROOT / "hardhat" / "artifacts" / "contracts" / "MockERC20.sol" / "MockERC20.json"
    if not artifact.exists():
        return {"error": "artifact not found", "path": str(artifact)}
    try:
        data = json.loads(artifact.read_text("utf-8"))
        return {"abi": data.get("abi", []), "bytecode": data.get("bytecode")}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/v1/quant/markets")
def api_quant_markets(
    _key: str | None = Depends(require_quant_key),
):
    return {"pairs": _load_pairs_from_deployments()}


@app.websocket("/ws/quant")
async def ws_quant(websocket: WebSocket):
    key = websocket.headers.get("x-quant-key")
    try:
        _validate_quant_key_value(key, str(websocket.url), increment=False)
    except HTTPException:
        await websocket.close(code=4403)
        return
    await websocket.accept()
    vault = websocket.query_params.get("vault") or "_global"
    try:
        interval = float(websocket.query_params.get("interval", "5"))
    except ValueError:
        interval = 5.0
    interval = max(1.0, min(interval, 30.0))
    last_positions: Dict[str, float] | None = None
    event_cursor: float | None = None
    EVENT_CURSOR_EPS = 1e-6
    MAX_BOOT_EVENTS = 20
    try:
        while True:
            payload = _collect_status_snapshot()
            try:
                profile = get_profile(vault)
            except Exception:
                profile = {}
            allowed_symbols = payload["flags"].get("allowed_symbols") or ""
            symbols = [s.strip().upper() for s in allowed_symbols.split(",") if s.strip()]
            prices: Dict[str, float] = {}
            if symbols:
                try:
                    prices = _price_provider.get_index_prices(symbols)
                except Exception:
                    prices = {}
            events: List[Dict[str, Any]]
            if event_cursor is None:
                events = event_store.list(vault, limit=MAX_BOOT_EVENTS)
            else:
                events = event_store.list(vault, since=event_cursor)
            if events:
                try:
                    latest = max(float(e.get("ts", 0.0)) for e in events)
                except Exception:
                    latest = time.time()
                event_cursor = latest + EVENT_CURSOR_EPS
            positions_map = _flat_positions(profile)
            deltas = _positions_delta(last_positions, positions_map)
            last_positions = dict(positions_map)
            message = {
                "type": "quant_snapshot",
                "ts": time.time(),
                "status": payload,
                "vault": vault,
                "positions": profile,
                "positionsFlat": positions_map,
                "positionsByVenue": profile.get("positionsByVenue", {}),
                "prices": prices,
                "events": events,
            }
            if deltas:
                message["deltas"] = {"positions": deltas}
            await websocket.send_json(message)
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return


@app.post("/api/v1/register_deployment")
def api_register_deployment(
    vault: str,
    asset: str | None = None,
    name: str | None = None,
    type: str | None = None,
    _token: str | None = Depends(require_deployment_key),
):
    """Record a deployment in deployments/hyper-testnet.json for discovery.

    This is a convenience for demo. In production this should be guarded.
    """
    f = REPO_ROOT / "deployments" / "hyper-testnet.json"
    try:
        meta = json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        meta = {}
    meta.setdefault("network", "hyperTestnet")
    deployments = meta.get("deployments")
    if not isinstance(deployments, list):
        deployments = []
        legacy = {}
        if isinstance(meta.get("vault"), str):
            legacy["vault"] = meta.get("vault")
        if meta.get("asset"):
            legacy["asset"] = meta.get("asset")
        if legacy.get("vault"):
            deployments.append(legacy)
    updated = False
    for item in deployments:
        if isinstance(item, dict) and item.get("vault") == vault:
            if asset:
                item["asset"] = asset
            if name:
                item["name"] = name
            if type:
                item["type"] = type
            updated = True
            break
    if not updated:
        entry = {"vault": vault, "type": type or "public"}
        if asset:
            entry["asset"] = asset
        if name:
            entry["name"] = name
        deployments.append(entry)
    meta["deployments"] = deployments
    # retain legacy keys for backward compatibility
    meta["vault"] = vault
    if asset:
        meta["asset"] = asset
    if name:
        meta["name"] = name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    logger.info(
        "deployment metadata updated",
        extra={
            "event": "deployment.register",
            "vault": vault,
            "asset": asset,
            "type": type or "public",
            "updated": updated,
            "path": str(f),
        },
    )
    return {"ok": True, "path": str(f), "deployments": deployments}


# --- Exec Service (dry-run env-controlled) ---
@app.post("/api/v1/exec/open")
def api_exec_open(
    symbol: str,
    size: float,
    side: str,
    venue: str = "hyper",
    reduce_only: bool = False,
    leverage: float | None = None,
    order_type: str = "market",
    limit_price: float | None = None,
    time_in_force: str | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    vault: str = "_global",
    _token: str | None = Depends(require_deployment_key),
):
    svc = ExecService()
    result = svc.open(
        vault,
        Order(
            symbol=symbol,
            size=size,
            side=side,
            venue=venue,
            reduce_only=reduce_only,
            leverage=leverage,
            order_type=order_type,
            limit_price=limit_price,
            time_in_force=time_in_force,
            stop_loss=stop_loss,
            take_profit=take_profit,
        ),
    )
    logger.info(
        "exec.open processed",
        extra={
            "event": "exec.open",
            "vault": vault,
            "symbol": symbol,
            "size": size,
            "side": side,
             "venue": venue,
            "reduce_only": reduce_only,
            "leverage": leverage,
            "order_type": order_type,
            "limit_price": limit_price,
            "time_in_force": time_in_force,
            "dry_run": bool(result.get("dry_run")),
            "status": result.get("status", "ok"),
        },
    )
    return result


@app.post("/api/v1/exec/close")
def api_exec_close(
    symbol: str,
    size: float | None = None,
    venue: str = "hyper",
    vault: str = "_global",
    _token: str | None = Depends(require_deployment_key),
):
    svc = ExecService()
    result = svc.close(vault, symbol=symbol, size=size, venue=venue)
    logger.info(
        "exec.close processed",
        extra={
            "event": "exec.close",
            "vault": vault,
            "symbol": symbol,
            "size": size,
            "venue": venue,
            "dry_run": bool(result.get("dry_run")),
            "status": result.get("status", "ok"),
        },
    )
    return result


@app.get("/api/v1/pretrade")
def api_pretrade(symbol: str, size: float, side: str, reduce_only: bool = False, leverage: float | None = None, venue: str = "hyper"):
    svc = ExecService()
    try:
        svc._validate(Order(symbol=symbol, size=size, side=side, reduce_only=reduce_only, leverage=leverage, venue=venue))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# --- Vaults registry (derive from deployments & positions) ---
def _vault_registry() -> List[Dict[str, object]]:
    out: Dict[str, Dict[str, object]] = {}
    # 1) positions.json keys → default private vaults
    try:
        pos_path = os.getenv("POSITIONS_FILE")
        if pos_path:
            path = Path(pos_path)
            if not path.is_absolute():
                path = REPO_ROOT / path
        else:
            path = REPO_ROOT / "deployments" / "positions.json"
        if path.exists():
            data = json.loads(path.read_text() or "{}")
            if isinstance(data, dict):
                for vid in data.keys():
                    if isinstance(vid, str):
                        out[vid] = {
                            "id": vid,
                            "name": f"Vault {vid}",
                            "type": "private",
                        }
    except Exception:
        pass
    # 2) deployments/hyper-testnet.json vault → prefer public entry if present
    try:
        d = REPO_ROOT / "deployments" / "hyper-testnet.json"
        if d.exists():
            meta = json.loads(d.read_text() or "{}")
            deployments = []
            if isinstance(meta.get("deployments"), list):
                deployments = meta["deployments"]
            elif meta.get("vault"):
                deployments = [{"vault": meta.get("vault"), "asset": meta.get("asset")}]
            for entry in deployments:
                vid = entry.get("vault")
                if isinstance(vid, str) and vid:
                    out[vid] = {
                        "id": vid,
                        "name": entry.get("name") or "VaultCraft (Hyper Testnet)",
                        "type": entry.get("type") or "public",
                        "asset": entry.get("asset"),
                    }
    except Exception:
        pass
    # fallback demo if empty
    if not out:
        return [
            {"id": "0x1234...5678", "name": "Alpha Momentum Strategy", "type": "public"},
            {"id": "0x8765...4321", "name": "Quant Arbitrage Fund", "type": "private"},
        ]
    return list(out.values())


# demo profiles were replaced by file-backed store (deployments/positions.json)


@app.get("/api/v1/vaults")
def api_vaults():
    return {"vaults": _vault_registry()}


@app.get("/api/v1/vaults/{vault_id}")
def api_vault_detail(vault_id: str):
    # basic info from registry
    info = next((v for v in _vault_registry() if v["id"] == vault_id), None)
    if info is None:
        info = {"id": vault_id, "name": "Vault", "type": "private"}
    # compute NAV + metrics
    profile = get_profile(vault_id)
    positions_flat = _flat_positions(profile)
    syms = list(positions_flat.keys())
    try:
        prices = _price_provider.get_index_prices(syms) if syms else {}
    except Exception:
        prices = {s: 1000.0 + 100.0 * i for i, s in enumerate(syms)}
    nav_val = HyperExecClient.pnl_to_nav(
        cash=profile.get("cash", 1_000_000.0), positions=positions_flat, index_prices=prices
    )
    unit_nav = round(nav_val / profile.get("denom", 1_000_000.0), 6)
    nav_series = [unit_nav] * 60
    m = compute_metrics(nav_series)
    # Attempt to enrich with deployment meta (asset address, if known)
    asset_addr = None
    try:
        d = REPO_ROOT / "deployments" / "hyper-testnet.json"
        if d.exists():
            meta = json.loads(d.read_text() or "{}")
            deployments = []
            if isinstance(meta.get("deployments"), list):
                deployments = meta["deployments"]
            elif meta.get("vault"):
                deployments = [{"vault": meta.get("vault"), "asset": meta.get("asset")}]
            for entry in deployments:
                if isinstance(entry, dict) and entry.get("vault") == vault_id:
                    a = entry.get("asset")
                    if isinstance(a, str) and a:
                        asset_addr = a
                        break
    except Exception:
        pass
    return {
        **info,
        "metrics": m,
        "unitNav": unit_nav,
        "lockDays": 1,
        "performanceFee": 10,
        "managementFee": 0,
        "aum": int(nav_val),
        "totalShares": int(profile.get("denom", 1_000_000.0)),
        **({"asset": asset_addr} if asset_addr else {}),
    }


@app.get("/api/v1/vaults/{vault_id}/risk")
def api_vault_risk(vault_id: str):
    base = _collect_status_snapshot().get("flags", {}).get("risk_template", {})
    effective = _collect_status_snapshot(vault_id).get("flags", {}).get("risk_template", {})
    meta = _lookup_vault_meta(vault_id)
    override = meta.get("risk") if isinstance(meta.get("risk"), dict) else {}
    return {"vault": vault_id, "base": base, "override": override or {}, "effective": effective}


@app.put("/api/v1/vaults/{vault_id}/risk")
def api_vault_risk_update(
    vault_id: str,
    payload: Dict[str, Any] | None = Body(default=None),
):
    if payload:
        to_set, to_remove = _sanitize_risk_payload(payload)
    else:
        to_set, to_remove = {}, set(_RISK_FIELDS)
    override = _persist_vault_risk_override(vault_id, to_set, to_remove)
    base = _collect_status_snapshot().get("flags", {}).get("risk_template", {})
    effective = _collect_status_snapshot(vault_id).get("flags", {}).get("risk_template", {})
    return {"vault": vault_id, "base": base, "override": override, "effective": effective}


# --- Positions admin (dev/demo) ---
@app.get("/api/v1/positions/{vault_id}")
def api_positions_get(vault_id: str):
    return get_profile(vault_id)


@app.post("/api/v1/positions/{vault_id}")
def api_positions_set(
    vault_id: str,
    profile: Dict[str, object],
    _token: str | None = Depends(require_deployment_key),
):
    from .positions import set_profile

    set_profile(vault_id, profile)
    try:
        fields = sorted(profile.keys())
    except Exception:
        fields = []
    logger.info(
        "positions profile updated",
        extra={
            "event": "positions.set",
            "vault": vault_id,
            "fields": fields,
        },
    )
    unit = HyperExecClient.pnl_to_nav(
        cash=float(profile.get("cash", 1_000_000.0)),
        positions={str(k): float(v) for k, v in dict(profile.get("positions", {})).items()},
        index_prices={s: 0.0 for s in dict(profile.get("positions", {})).keys()},
    )
    # only confirm set; nav is computed via dedicated endpoints with live prices
    return {"ok": True}


@app.get("/api/v1/quant/positions")
def api_quant_positions(
    vault: str = "_global",
    _key: str | None = Depends(require_quant_key),
):
    return get_profile(vault)


@app.get("/api/v1/quant/prices")
def api_quant_prices(
    symbols: str,
    _key: str | None = Depends(require_quant_key),
):
    syms = [s for s in symbols.split(",") if s]
    if not syms:
        raise HTTPException(status_code=400, detail="symbols required")
    try:
        prices = _price_provider.get_index_prices(syms)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="price feed unavailable") from exc
    return {"prices": prices}


@app.post("/api/v1/quant/orders/open")
def api_quant_order_open(
    payload: QuantOrderPayload,
    _key: str | None = Depends(require_quant_key),
):
    _ensure_quant_orders_enabled()
    svc = ExecService()
    result = svc.open(payload.vault, payload.to_order())
    return {"vault": payload.vault, "venue": payload.venue, "result": result}


@app.post("/api/v1/quant/orders/close")
def api_quant_order_close(
    payload: QuantClosePayload,
    _key: str | None = Depends(require_quant_key),
):
    _ensure_quant_orders_enabled()
    svc = ExecService()
    result = svc.close(payload.vault, payload.symbol, payload.size, venue=payload.venue)
    return {"vault": payload.vault, "venue": payload.venue, "result": result}

@app.on_event("startup")
def _startup():
    global _snapshot_daemon, _user_listener
    # Ensure request-scoped determinism for tests and fresh boot by clearing caches
    try:
        try:
            _price_provider.cache.clear()
        except Exception:
            pass
        try:
            _nav_cache.clear()
        except Exception:
            pass
    except Exception:
        pass
    if settings.ENABLE_SNAPSHOT_DAEMON:
        def list_ids() -> List[str]:
            return [v["id"] for v in _vault_registry()]
        _snapshot_daemon = SnapshotDaemon(list_vaults=list_ids, interval_sec=float(settings.SNAPSHOT_INTERVAL_SEC))
        _snapshot_daemon.start()
    if settings.ENABLE_LIVE_EXEC and settings.ENABLE_USER_WS_LISTENER:
        # Use ADDRESS as the logical vault id; for multi-vault setups, consider per-vault routing
        _user_listener = UserEventsListener(vault=settings.ADDRESS or "_global")
        _user_listener.start()


@app.on_event("shutdown")
def _shutdown():
    global _snapshot_daemon, _user_listener
    try:
        if _snapshot_daemon:
            _snapshot_daemon.stop()
    except Exception:
        pass
    try:
        if _user_listener:
            _user_listener.stop()
    except Exception:
        pass
