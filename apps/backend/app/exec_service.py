from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict

from .ack_tracker import record as record_ack
from .events import store as event_store
from .hyper_exec import HyperExecClient, Order
from .listener_registry import register as register_listener_vault
from .navcalc import snapshot_now
from .positions import apply_close, apply_fill, get_profile
from .price_provider import PriceRouter
from .settings import Settings, settings

try:  # pragma: no cover - optional dependency
    from hyperliquid.exchange import Exchange  # type: ignore
except Exception:  # pragma: no cover
    Exchange = None  # type: ignore[assignment]


RETRYABLE_ERROR_SNIPPETS = (
    "price too far from oracle",
    "could not immediately match against any resting orders",
    "could not immediately match",
)


def _payload_has_error(payload: dict | list | str | None) -> bool:
    try:
        if payload is None:
            return False
        if isinstance(payload, str):
            return "error" in payload.lower()
        if isinstance(payload, dict):
            if any(k.lower() == "error" for k in payload):
                return True
            return any(_payload_has_error(v) for v in payload.values())
        if isinstance(payload, list):
            return any(_payload_has_error(v) for v in payload)
        return "error" in str(payload).lower()
    except Exception:
        return False


def _should_retry(payload: Any) -> bool:
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except Exception:
        text = str(payload)
    lower = text.lower()
    return any(snippet in lower for snippet in RETRYABLE_ERROR_SNIPPETS)


class ExecDriver:
    def open(self, order: Order) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self, symbol: str, size: float | None = None) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


class HyperSDKDriver(ExecDriver):
    def __init__(self, base_url: str | None = None, private_key: str | None = None):
        try:
            from eth_account import Account  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("hyperliquid SDK not available") from exc
        if Exchange is None:
            raise RuntimeError("hyperliquid SDK not available")
        env = Settings()
        pk = private_key or env.HYPER_TRADER_PRIVATE_KEY or env.PRIVATE_KEY
        if pk:
            pk = str(pk).strip().strip('"').strip("'")
            if not pk.startswith("0x") and len(pk) == 64:
                pk = "0x" + pk
        if not pk:
            raise RuntimeError("missing HYPER_TRADER_PRIVATE_KEY for live exec")
        self._Exchange = Exchange
        self._wallet = Account.from_key(pk)
        self._base_url = base_url or env.HYPER_API_URL
        self._exch = Exchange(wallet=self._wallet, base_url=self._base_url)
        self._market_slippage = self._compute_slippage(getattr(env, "EXEC_MARKET_SLIPPAGE_BPS", 10.0))
        ro_source = getattr(env, "EXEC_RO_SLIPPAGE_BPS", None)
        if ro_source is None:
            ro_source = getattr(env, "EXEC_MARKET_SLIPPAGE_BPS", 10.0)
        self._reduce_slippage = self._compute_slippage(ro_source)

    def _compute_slippage(self, bps: float | None) -> float:
        default = getattr(self._exch, "DEFAULT_SLIPPAGE", 0.05)
        if bps is None:
            return default
        try:
            desired = float(bps) / 10_000.0
        except Exception:
            return default
        if desired <= 0:
            return default
        return min(desired, 1.0)

    def open(self, order: Order) -> Dict[str, Any]:
        is_buy = order.side == "buy"
        kind = (order.order_type or "market").lower()
        if kind == "limit":
            px = float(order.limit_price)
            tif = (order.time_in_force or "Gtc").title()
            res = self._exch.order(
                name=order.symbol,
                is_buy=is_buy,
                sz=float(order.size),
                limit_px=px,
                order_type={"limit": {"tif": tif}},
                reduce_only=order.reduce_only,
            )
        elif order.reduce_only:
            slippage = self._reduce_slippage
            px = float(self._exch._slippage_price(order.symbol, is_buy, slippage, None))  # type: ignore[attr-defined]
            res = self._exch.order(
                name=order.symbol,
                is_buy=is_buy,
                sz=float(order.size),
                limit_px=px,
                order_type={"limit": {"tif": "Ioc"}},
                reduce_only=True,
            )
        else:
            res = self._exch.market_open(
                name=order.symbol,
                is_buy=is_buy,
                sz=float(order.size),
                slippage=self._market_slippage,
            )
        return {"ack": res}

    def close(self, symbol: str, size: float | None = None) -> Dict[str, Any]:
        res = self._exch.market_close(
            coin=symbol,
            sz=(float(size) if size is not None else None),
            slippage=self._reduce_slippage,
        )
        return {"ack": res}


class MockGoldDriver(ExecDriver):
    """Deterministic mock venue to showcase XAU/黄金市场。"""

    def __init__(self, venue: str = "mock_gold"):
        self.venue = venue

    def _ack(self, symbol: str, size: float | None, side: str) -> Dict[str, Any]:
        return {
            "venue": self.venue,
            "symbol": symbol,
            "side": side,
            "size": size,
            "ts": time.time(),
        }

    def open(self, order: Order) -> Dict[str, Any]:
        sym = order.symbol.upper()
        if sym not in {"XAU", "XAUUSD", "GOLD"}:
            raise ValueError("mock_gold only supports XAU")
        if (order.order_type or "market").lower() != "market":
            raise ValueError("mock_gold only supports market orders")
        return {"ack": self._ack(order.symbol, order.size, order.side)}

    def close(self, symbol: str, size: float | None = None) -> Dict[str, Any]:
        return {"ack": self._ack(symbol, size, "close")}


class ExecService:
    def __init__(self, driver: ExecDriver | None = None):
        self._driver_override = driver
        self._hyper_driver: ExecDriver | None = None
        self._mock_gold_driver: ExecDriver | None = None

    def _hyper_driver(self) -> ExecDriver:
        if self._driver_override:
            return self._driver_override
        if self._hyper_driver is None:
            self._hyper_driver = HyperSDKDriver()
        return self._hyper_driver

    def _resolve_driver(self, venue: str) -> ExecDriver:
        venue_key = (venue or "hyper").lower()
        if self._driver_override:
            return self._driver_override
        if venue_key == "hyper":
            return self._hyper_driver()
        if venue_key == "mock_gold":
            if self._mock_gold_driver is None:
                self._mock_gold_driver = MockGoldDriver()
            return self._mock_gold_driver
        raise ValueError(f"unsupported venue: {venue}")

    def _run_with_retry(self, func: Callable[..., Dict[str, Any]], *args: Any, **kwargs: Any) -> tuple[Dict[str, Any], bool, int]:
        env = Settings()
        max_extra = max(0, int(getattr(env, "EXEC_RETRY_ATTEMPTS", 0)))
        backoff = max(0.0, float(getattr(env, "EXEC_RETRY_BACKOFF_SEC", 0.0)))
        attempts = 0
        total_allowed = 1 + max_extra
        last: Dict[str, Any] | None = None
        while True:
            attempts += 1
            last = func(*args, **kwargs)
            payload = last.get("ack") if isinstance(last, dict) else last
            ok = not _payload_has_error(payload)
            if ok or attempts >= total_allowed or not _should_retry(payload):
                return last, ok, attempts
            if backoff > 0:
                time.sleep(backoff)

    def _allowed_venues(self) -> set[str]:
        env = Settings()
        return {v.strip().lower() for v in str(getattr(env, "EXEC_ALLOWED_VENUES", "hyper")).split(",") if v.strip()}

    def _validate(self, order: Order) -> None:
        env = Settings()
        venue = (order.venue or "hyper").lower()
        if venue not in self._allowed_venues():
            raise ValueError("venue not allowed")
        allowed = {s.strip().upper() for s in env.EXEC_ALLOWED_SYMBOLS.split(",") if s.strip()}
        sym = order.symbol.upper()
        if sym not in allowed:
            raise ValueError("symbol not allowed")
        if order.size <= 0:
            raise ValueError("size must be > 0")
        lev = order.leverage if order.leverage is not None else env.EXEC_MIN_LEVERAGE
        if lev < env.EXEC_MIN_LEVERAGE or lev > env.EXEC_MAX_LEVERAGE:
            raise ValueError("leverage out of range")
        kind = (order.order_type or "market").lower()
        if kind not in {"market", "limit"}:
            raise ValueError("unsupported order_type")
        if kind == "limit" and (order.limit_price is None or order.limit_price <= 0):
            raise ValueError("limit_price required for limit order")
        if order.stop_loss is not None and order.stop_loss <= 0:
            raise ValueError("stop_loss must be positive")
        if order.take_profit is not None and order.take_profit <= 0:
            raise ValueError("take_profit must be positive")
        price_key = f"{venue}::{sym}"
        price = 0.0
        try:
            price = PriceRouter().get_index_prices([price_key]).get(price_key, 0.0)
        except Exception:
            price = 0.0
        notional = abs(order.size) * (price or 0.0)
        if price > 0.0 and notional > env.EXEC_MAX_NOTIONAL_USD:
            raise ValueError("notional exceeds limit")
        if price > 0.0 and notional < env.EXEC_MIN_NOTIONAL_USD:
            raise ValueError("notional below minimum")

    def _apply_position_open(self, vault: str, order: Order, venue: str, live: bool) -> None:
        if live and not settings.APPLY_LIVE_TO_POSITIONS:
            return
        if not live and not settings.APPLY_DRY_RUN_TO_POSITIONS:
            return
        apply_fill(vault, order.symbol, order.size, order.side, venue=venue)
        unit = snapshot_now(vault)
        event_store.add(
            vault,
            {
                "type": "fill",
                "status": "applied",
                "source": "ack" if live else "dry_run",
                "symbol": order.symbol,
                "side": order.side,
                "size": order.size,
                "unitNav": unit,
                "venue": venue,
            },
        )

    def _apply_position_close(self, vault: str, symbol: str, size: float | None, venue: str, live: bool) -> None:
        if live and not settings.APPLY_LIVE_TO_POSITIONS:
            return
        if not live and not settings.APPLY_DRY_RUN_TO_POSITIONS:
            return
        apply_close(vault, symbol, size, venue=venue)
        unit = snapshot_now(vault)
        event_store.add(
            vault,
            {
                "type": "fill",
                "status": "applied",
                "source": "ack" if live else "dry_run",
                "symbol": symbol,
                "side": "close",
                "size": size,
                "unitNav": unit,
                "venue": venue,
            },
        )

    def open(self, vault: str, order: Order) -> Dict[str, Any]:
        try:
            self._validate(order)
        except Exception as exc:
            event_store.add(vault, {"type": "exec_open", "status": "rejected", "error": str(exc)})
            return {"ok": False, "error": str(exc)}
        venue = (order.venue or "hyper").lower()
        register_listener_vault(vault)
        env = Settings()
        if venue == "hyper" and not env.ENABLE_LIVE_EXEC:
            payload = HyperExecClient().build_open_order(order)
            event_store.add(vault, {"type": "exec_open", "status": "dry_run", "payload": payload, "venue": venue})
            self._apply_position_open(vault, order, venue, live=False)
            return {"ok": True, "dry_run": True, "payload": payload}
        driver = self._resolve_driver(venue)
        try:
            ack, ok, attempts = self._run_with_retry(driver.open, order)
            event_store.add(
                vault,
                {"type": "exec_open", "status": ("ack" if ok else "error"), "payload": ack, "attempts": attempts, "venue": venue},
            )
            dry_run = venue != "hyper" or not env.ENABLE_LIVE_EXEC
            if ok:
                if venue == "hyper" and env.ENABLE_LIVE_EXEC:
                    record_ack(vault)
                self._apply_position_open(vault, order, venue, live=(venue == "hyper" and env.ENABLE_LIVE_EXEC))
            return {"ok": ok, "payload": ack, "attempts": attempts, "venue": venue, "dry_run": dry_run and ok}
        except Exception as exc:
            event_store.add(vault, {"type": "exec_open", "status": "error", "error": str(exc), "venue": venue})
            return {"ok": False, "error": str(exc)}

    def close(self, vault: str, symbol: str, size: float | None = None, venue: str = "hyper") -> Dict[str, Any]:
        venue_key = (venue or "hyper").lower()
        register_listener_vault(vault)
        env = Settings()
        if venue_key == "hyper" and not env.ENABLE_LIVE_EXEC:
            payload = HyperExecClient().build_close_order(symbol=symbol, size=size)
            event_store.add(vault, {"type": "exec_close", "status": "dry_run", "payload": payload, "venue": venue_key})
            self._apply_position_close(vault, symbol, size, venue_key, live=False)
            return {"ok": True, "dry_run": True, "payload": payload}
        if venue_key != "hyper":
            driver = self._resolve_driver(venue_key)
            try:
                ack, ok, attempts = self._run_with_retry(driver.close, symbol, size)
                event_store.add(
                    vault,
                    {"type": "exec_close", "status": ("ack" if ok else "error"), "payload": ack, "attempts": attempts, "venue": venue_key},
                )
                if ok:
                    self._apply_position_close(vault, symbol, size, venue_key, live=False)
                return {"ok": ok, "payload": ack, "attempts": attempts, "venue": venue_key, "dry_run": True}
            except Exception as exc:
                event_store.add(vault, {"type": "exec_close", "status": "error", "error": str(exc), "venue": venue_key})
                return {"ok": False, "error": str(exc)}
        driver = self._resolve_driver("hyper")
        payload = HyperExecClient().build_close_order(symbol=symbol, size=size)
        try:
            ack, ok, attempts = self._run_with_retry(driver.close, symbol, size)
            if ok:
                event_store.add(
                    vault, {"type": "exec_close", "status": "ack", "payload": ack, "attempts": attempts, "venue": venue_key}
                )
                record_ack(vault)
                self._apply_position_close(vault, symbol, size, venue_key, live=True)
                return {"ok": True, "payload": ack, "attempts": attempts}
            if Settings().ENABLE_CLOSE_FALLBACK_RO:
                prof = get_profile(vault)
                per_venue = prof.get("positionsByVenue", {}) or {}
                pos = float(per_venue.get(venue_key, {}).get(symbol, 0.0))
                if pos != 0.0:
                    side = "sell" if pos > 0 else "buy"
                    ro = Order(symbol=symbol, size=(abs(pos) if size is None else size), side=side, reduce_only=True, venue="hyper")
                    try:
                        ack2, ok2, attempts2 = self._run_with_retry(driver.open, ro)
                        event_store.add(
                            vault,
                            {
                                "type": "exec_close",
                                "status": ("ack" if ok2 else "error"),
                                "payload": ack2,
                                "attempts": attempts2,
                                "mode": "reduce_only",
                                "venue": venue_key,
                            },
                        )
                        if ok2:
                            record_ack(vault)
                            self._apply_position_close(vault, symbol, size, venue_key, live=True)
                        return {"ok": ok2, "payload": ack2, "attempts": attempts2, "mode": "reduce_only"}
                    except Exception as exc:
                        event_store.add(vault, {"type": "exec_close", "status": "error", "error": str(exc), "venue": venue_key})
                        return {"ok": False, "error": str(exc)}
            event_store.add(vault, {"type": "exec_close", "status": "error", "payload": ack, "attempts": attempts, "venue": venue_key})
            return {"ok": False, "payload": ack, "attempts": attempts}
        except Exception as exc:
            event_store.add(vault, {"type": "exec_close", "status": "error", "error": str(exc), "venue": venue_key})
            return {"ok": False, "error": str(exc)}
