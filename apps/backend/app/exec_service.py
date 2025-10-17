from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .hyper_exec import Order, HyperExecClient
from .settings import settings, Settings
from .events import store as event_store
from .positions import apply_fill, apply_close, get_profile
from .navcalc import snapshot_now
from .price_provider import PriceRouter
import json
from hyperliquid.exchange import Exchange  # type: ignore


def _payload_has_error(payload: dict | list | str | None) -> bool:
    try:
        if payload is None:
            return False
        if isinstance(payload, str):
            return "error" in payload.lower()
        if isinstance(payload, dict):
            if any(k.lower() == "error" for k in payload.keys()):
                return True
            return any(_payload_has_error(v) for v in payload.values())
        if isinstance(payload, list):
            return any(_payload_has_error(v) for v in payload)
        # Fallback: string form
        return "error" in str(payload).lower()
    except Exception:
        return False


class ExecDriver:
    def open(self, order: Order) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self, symbol: str, size: float | None = None) -> Dict[str, Any]:  # pragma: no cover
        raise NotImplementedError


class HyperSDKDriver(ExecDriver):
    def __init__(self, base_url: str | None = None, private_key: str | None = None):
        # Deferred import
        try:
            from eth_account import Account  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("hyperliquid SDK not available") from e
        env = Settings()
        pk = private_key or env.HYPER_TRADER_PRIVATE_KEY or env.PRIVATE_KEY
        if pk:
            t = str(pk).strip().strip('"').strip("'")
            if not t.startswith("0x") and len(t) == 64:
                t = "0x" + t
            pk = t
        if not pk:
            raise RuntimeError("missing HYPER_TRADER_PRIVATE_KEY for live exec")
        self._Exchange = Exchange
        self._wallet = Account.from_key(pk)
        self._base_url = base_url or env.HYPER_API_URL
        self._exch = Exchange(wallet=self._wallet, base_url=self._base_url)

    def open(self, order: Order) -> Dict[str, Any]:
        is_buy = True if order.side == "buy" else False
        if order.reduce_only:
            default_slippage = getattr(self._exch, "DEFAULT_SLIPPAGE", 0.05)
            slippage = min(default_slippage, 0.001)
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
            default_slippage = getattr(self._exch, "DEFAULT_SLIPPAGE", 0.05)
            slippage = min(default_slippage, 0.001)
            res = self._exch.market_open(name=order.symbol, is_buy=is_buy, sz=float(order.size), slippage=slippage)
        return {"ack": res}

    def close(self, symbol: str, size: float | None = None) -> Dict[str, Any]:
        slippage = min(getattr(self._exch, "DEFAULT_SLIPPAGE", 0.05), 0.001)
        res = self._exch.market_close(
            coin=symbol,
            sz=(float(size) if size is not None else None),
            slippage=slippage,
        )
        return {"ack": res}


@dataclass
class ExecService:
    driver: ExecDriver | None = None

    def _driver(self) -> ExecDriver:
        if self.driver is not None:
            return self.driver
        # construct default driver lazily
        return HyperSDKDriver()

    def _validate(self, order: Order) -> None:
        env = Settings()
        allowed = {s.strip().upper() for s in env.EXEC_ALLOWED_SYMBOLS.split(',') if s.strip()}
        sym = order.symbol.upper()
        if sym not in allowed:
            raise ValueError("symbol not allowed")
        if order.size <= 0:
            raise ValueError("size must be > 0")
        lev = order.leverage if order.leverage is not None else env.EXEC_MIN_LEVERAGE
        if lev < env.EXEC_MIN_LEVERAGE or lev > env.EXEC_MAX_LEVERAGE:
            raise ValueError("leverage out of range")
        # Notional check
        price = 0.0
        try:
            price = PriceRouter().get_index_prices([sym]).get(sym, 0.0)
        except Exception:
            price = 0.0
        notional = abs(order.size) * (price or 0.0)
        if price > 0.0 and notional > env.EXEC_MAX_NOTIONAL_USD:
            raise ValueError("notional exceeds limit")
        if price > 0.0 and notional < env.EXEC_MIN_NOTIONAL_USD:
            raise ValueError("notional below minimum")

    def open(self, vault: str, order: Order) -> Dict[str, Any]:
        # validate first
        try:
            self._validate(order)
        except Exception as e:
            event_store.add(vault, {"type": "exec_open", "status": "rejected", "error": str(e)})
            return {"ok": False, "error": str(e)}
        payload = HyperExecClient().build_open_order(order)
        if not Settings().ENABLE_LIVE_EXEC:
            event_store.add(vault, {"type": "exec_open", "status": "dry_run", "payload": payload})
            if settings.APPLY_DRY_RUN_TO_POSITIONS:
                apply_fill(vault, order.symbol, order.size, order.side)
                unit = snapshot_now(vault)
                event_store.add(vault, {"type": "fill", "status": "applied", "source": "ack", "symbol": order.symbol, "side": order.side, "size": order.size, "unitNav": unit})
            return {"ok": True, "dry_run": True, "payload": payload}
        try:
            ack = self._driver().open(order)
            # Basic success detection: treat presence of 'error' in ack tree as failure
            payload = ack.get("ack") if isinstance(ack, dict) else ack
            ok = not _payload_has_error(payload)
            event_store.add(vault, {"type": "exec_open", "status": ("ack" if ok else "error"), "payload": ack})
            if ok and settings.APPLY_LIVE_TO_POSITIONS:
                apply_fill(vault, order.symbol, order.size, order.side)
                unit = snapshot_now(vault)
                event_store.add(vault, {"type": "fill", "status": "applied", "source": "ack", "symbol": order.symbol, "side": order.side, "size": order.size, "unitNav": unit})
            return {"ok": ok, "payload": ack}
        except Exception as e:
            event_store.add(vault, {"type": "exec_open", "status": "error", "error": str(e)})
            return {"ok": False, "error": str(e)}

    def close(self, vault: str, symbol: str, size: float | None = None) -> Dict[str, Any]:
        payload = HyperExecClient().build_close_order(symbol=symbol, size=size)
        if not Settings().ENABLE_LIVE_EXEC:
            event_store.add(vault, {"type": "exec_close", "status": "dry_run", "payload": payload})
            if settings.APPLY_DRY_RUN_TO_POSITIONS:
                apply_close(vault, symbol, size)
                unit = snapshot_now(vault)
                event_store.add(vault, {"type": "fill", "status": "applied", "symbol": symbol, "side": "close", "size": size, "unitNav": unit})
            return {"ok": True, "dry_run": True, "payload": payload}
        try:
            ack = self._driver().close(symbol=symbol, size=size)
            payload_ack = ack.get("ack") if isinstance(ack, dict) else ack
            ok = not _payload_has_error(payload_ack)
            if ok:
                event_store.add(vault, {"type": "exec_close", "status": "ack", "payload": ack})
                if settings.APPLY_LIVE_TO_POSITIONS:
                    apply_close(vault, symbol, size)
                    unit = snapshot_now(vault)
                    event_store.add(vault, {"type": "fill", "status": "applied", "source": "ack", "symbol": symbol, "side": "close", "size": size, "unitNav": unit})
                return {"ok": True, "payload": ack}
            # Not ok: consider reduce-only fallback if enabled
            if Settings().ENABLE_CLOSE_FALLBACK_RO:
                prof = get_profile(vault)
                pos = float(prof.get("positions", {}).get(symbol, 0.0))
                if pos != 0.0:
                    side = "sell" if pos > 0 else "buy"
                    ro = Order(symbol=symbol, size=(abs(pos) if size is None else size), side=side, reduce_only=True)
                    try:
                        ack2 = self._driver().open(ro)
                        payload_ack2 = ack2.get("ack") if isinstance(ack2, dict) else ack2
                        ok2 = not _payload_has_error(payload_ack2)
                        event_store.add(vault, {"type": "exec_close", "status": ("ack" if ok2 else "error"), "payload": ack2})
                        if ok2 and settings.APPLY_LIVE_TO_POSITIONS:
                            apply_close(vault, symbol, size)
                            unit = snapshot_now(vault)
                            event_store.add(vault, {"type": "fill", "status": "applied", "source": "ack", "symbol": symbol, "side": "close", "size": size, "unitNav": unit})
                        return {"ok": ok2, "payload": ack2}
                    except Exception as e2:
                        event_store.add(vault, {"type": "exec_close", "status": "error", "error": str(e2)})
                        return {"ok": False, "error": str(e2)}
            # Otherwise log original error
            event_store.add(vault, {"type": "exec_close", "status": "error", "payload": ack})
            return {"ok": False, "payload": ack}
        except Exception as e:
            event_store.add(vault, {"type": "exec_close", "status": "error", "error": str(e)})
            return {"ok": False, "error": str(e)}
