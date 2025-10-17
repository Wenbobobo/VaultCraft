from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .hyper_exec import Order, HyperExecClient
from .settings import settings, Settings
from .events import store as event_store
from .positions import apply_fill, apply_close
from .navcalc import snapshot_now
from .price_provider import PriceRouter


class ExecDriver:
    def open(self, order: Order) -> Dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self, symbol: str, size: float | None = None) -> Dict[str, Any]:  # pragma: no cover
        raise NotImplementedError


class HyperSDKDriver(ExecDriver):
    def __init__(self, base_url: str | None = None, private_key: str | None = None):
        # Deferred import
        try:
            from hyperliquid.exchange import Exchange, OrderType  # type: ignore
            from eth_account import Account  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("hyperliquid SDK not available") from e
        env = Settings()
        pk = private_key or env.HYPER_TRADER_PRIVATE_KEY or env.PRIVATE_KEY
        if not pk:
            raise RuntimeError("missing HYPER_TRADER_PRIVATE_KEY for live exec")
        self._Exchange = Exchange
        self._OrderType = OrderType
        self._wallet = Account.from_key(pk)
        self._base_url = base_url or env.HYPER_API_URL
        self._exch = Exchange(wallet=self._wallet, base_url=self._base_url)

    def open(self, order: Order) -> Dict[str, Any]:
        is_buy = True if order.side == "buy" else False
        if order.reduce_only:
            res = self._exch.order(name=order.symbol, is_buy=is_buy, sz=float(order.size), limit_px=0.0, order_type=self._OrderType.Market, reduce_only=True)
        else:
            res = self._exch.market_open(name=order.symbol, is_buy=is_buy, sz=float(order.size))
        return {"ack": res}

    def close(self, symbol: str, size: float | None = None) -> Dict[str, Any]:
        res = self._exch.market_close(name=symbol, sz=(float(size) if size is not None else None))
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
            event_store.add(vault, {"type": "exec_open", "status": "ack", "payload": ack})
            if settings.APPLY_LIVE_TO_POSITIONS:
                apply_fill(vault, order.symbol, order.size, order.side)
                unit = snapshot_now(vault)
                event_store.add(vault, {"type": "fill", "status": "applied", "source": "ack", "symbol": order.symbol, "side": order.side, "size": order.size, "unitNav": unit})
            return {"ok": True, "payload": ack}
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
            event_store.add(vault, {"type": "exec_close", "status": "ack", "payload": ack})
            if settings.APPLY_LIVE_TO_POSITIONS:
                apply_close(vault, symbol, size)
                unit = snapshot_now(vault)
                event_store.add(vault, {"type": "fill", "status": "applied", "symbol": symbol, "side": "close", "size": size, "unitNav": unit})
            return {"ok": True, "payload": ack}
        except Exception as e:
            event_store.add(vault, {"type": "exec_close", "status": "error", "error": str(e)})
            return {"ok": False, "error": str(e)}
