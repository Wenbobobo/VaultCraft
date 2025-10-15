from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


DEFAULT_API = "https://api.hyperliquid-testnet.xyz"


@dataclass
class Order:
    symbol: str
    size: float
    side: str  # "buy" | "sell"
    reduce_only: bool = False
    leverage: float | None = None


class HyperExecClient:
    """Minimal client facade for Hyperliquid Exec Service usage.

    This does not perform network IO in tests; it shapes payloads to be sent by a higher-level service.
    """

    def __init__(self, base_url: str = DEFAULT_API, api_key: str | None = None, api_secret: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret

    def build_open_order(self, order: Order) -> Dict[str, Any]:
        assert order.side in ("buy", "sell"), "invalid side"
        assert order.size > 0, "size must be > 0"
        payload = {
            "type": "open",
            "symbol": order.symbol,
            "side": order.side,
            "size": order.size,
            "reduce_only": order.reduce_only,
        }
        if order.leverage is not None:
            payload["leverage"] = order.leverage
        return payload

    def build_close_order(self, symbol: str, size: float | None = None) -> Dict[str, Any]:
        assert symbol, "symbol required"
        payload = {"type": "close", "symbol": symbol}
        if size is not None:
            assert size > 0, "size must be > 0"
            payload["size"] = size
        return payload

    @staticmethod
    def pnl_to_nav(cash: float, positions: Dict[str, float], index_prices: Dict[str, float]) -> float:
        """Compute NAV from cash + positions (delta exposure) and index prices.

        positions: symbol -> delta (positive long, negative short)
        index_prices: symbol -> price
        """
        nav = cash
        for sym, delta in positions.items():
            price = index_prices.get(sym)
            if price is None:
                raise ValueError(f"missing price for {sym}")
            nav += delta * price
        return nav

