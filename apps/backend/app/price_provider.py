from __future__ import annotations

from typing import Dict, List

from .hyper_client import HyperHTTP
from .settings import Settings, settings


class PriceProvider:
    def get_index_prices(self, symbols: List[str]) -> Dict[str, float]:
        raise NotImplementedError


class RestPriceProvider(PriceProvider):
    def __init__(self, api_base: str | None = None, timeout: float | None = None):
        self.http = HyperHTTP(api_base=api_base or settings.HYPER_API_URL, rpc_url=settings.HYPER_RPC_URL, timeout=timeout or settings.PRICE_TIMEOUT)

    def get_index_prices(self, symbols: List[str]) -> Dict[str, float]:
        return self.http.get_index_prices(symbols)


class SDKPriceProvider(PriceProvider):
    def __init__(self, api_base: str | None = None, timeout: float | None = None):
        self.api_base = api_base or settings.HYPER_API_URL
        self.timeout = timeout or settings.PRICE_TIMEOUT
        self._info = None

    @staticmethod
    def available() -> bool:
        try:
            import hyperliquid  # noqa: F401
            return True
        except Exception:
            return False

    def _get_info(self):
        if self._info is None:
            from hyperliquid.info import Info  # type: ignore
            # Avoid opening WS in SDK to keep it lightweight in API calls
            self._info = Info(base_url=self.api_base, skip_ws=True, timeout=self.timeout)
        return self._info

    def get_index_prices(self, symbols: List[str]) -> Dict[str, float]:
        info = self._get_info()
        mids = info.all_mids()
        # SDK returns list of {"name": sym, "mid": price} or similar; accept common shapes
        out: Dict[str, float] = {}
        if isinstance(mids, list):
            for item in mids:
                name = item.get("name") or item.get("symbol")
                mid = item.get("mid") or item.get("price")
                if name in symbols and mid is not None:
                    out[name] = float(mid)
        elif isinstance(mids, dict):
            # sometimes as {sym: price}
            for k, v in mids.items():
                if k in symbols:
                    out[k] = float(v)
        return out


class PriceRouter(PriceProvider):
    def __init__(self):
        # Rebuild settings to reflect current env at instantiation (useful in tests)
        env = Settings()
        self.sdk_enabled = bool(env.ENABLE_HYPER_SDK)
        self.sdk = SDKPriceProvider()
        self.rest = RestPriceProvider()

    def get_index_prices(self, symbols: List[str]) -> Dict[str, float]:
        symbols = [s for s in symbols if s]
        if not symbols:
            return {}
        if self.sdk_enabled and self.sdk.available():
            try:
                data = self.sdk.get_index_prices(symbols)
                if data:
                    return data
            except Exception:
                pass
        # fallback to REST; outer layer may fallback to deterministic
        return self.rest.get_index_prices(symbols)
