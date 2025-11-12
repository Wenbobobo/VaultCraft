from __future__ import annotations

from typing import Dict, List
import time

from .hyper_client import HyperHTTP
from .settings import Settings, settings
from .cache import TTLCache


class PriceProvider:
    def get_index_prices(self, symbols: List[str]) -> Dict[str, float]:
        raise NotImplementedError


class RestPriceProvider(PriceProvider):
    def __init__(self, api_base: str | None = None, timeout: float | None = None):
        self.http = HyperHTTP(
            api_base=api_base or settings.HYPER_API_URL,
            rpc_url=settings.HYPER_RPC_URL,
            timeout=timeout or settings.PRICE_TIMEOUT,
        )

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

            self._info = Info(base_url=self.api_base, skip_ws=True, timeout=self.timeout)
        return self._info

    def get_index_prices(self, symbols: List[str]) -> Dict[str, float]:
        info = self._get_info()
        mids = info.all_mids()
        out: Dict[str, float] = {}
        if isinstance(mids, list):
            for item in mids:
                name = item.get("name") or item.get("symbol")
                mid = item.get("mid") or item.get("price")
                if name in symbols and mid is not None:
                    out[name] = float(mid)
        elif isinstance(mids, dict):
            for k, v in mids.items():
                if k in symbols:
                    out[k] = float(v)
        return out


class PriceRouter(PriceProvider):
    def __init__(self):
        env = Settings()
        self.sdk_enabled = bool(env.ENABLE_HYPER_SDK)
        self.sdk = SDKPriceProvider()
        self.rest = RestPriceProvider()
        self.mock_gold_price = float(getattr(env, "MOCK_GOLD_PRICE", 2350.0))

    def _split_symbol(self, token: str) -> tuple[str, str]:
        if "::" in token:
            venue, sym = token.split("::", 1)
            return venue.lower(), sym.upper()
        return "hyper", token.upper()

    def _fetch_hyper_prices(self, assets: List[str]) -> Dict[str, float]:
        symbols = [s for s in assets if s]
        if not symbols:
            return {}
        if self.sdk_enabled and self.sdk.available():
            try:
                try:
                    from .hyper_client import HyperHTTP as _H  # local import

                    patched = getattr(_H.get_index_prices, "__module__", "") != "app.hyper_client"
                except Exception:
                    patched = False
                if not patched:
                    data = self.sdk.get_index_prices(symbols)
                else:
                    raise RuntimeError("prefer_rest_due_to_patched_hyperhttp")
                if data:
                    return data
            except Exception:
                pass
        return self.rest.get_index_prices(symbols)

    def get_index_prices(self, symbols: List[str]) -> Dict[str, float]:
        grouped: Dict[str, List[tuple[str, str]]] = {}
        for token in symbols:
            if not token:
                continue
            venue, asset = self._split_symbol(token)
            grouped.setdefault(venue, []).append((token, asset))
        if not grouped:
            return {}
        result: Dict[str, float] = {}
        for venue, entries in grouped.items():
            if venue == "hyper":
                unique = sorted({asset for (_, asset) in entries})
                prices = self._fetch_hyper_prices(unique)
                for original, asset in entries:
                    value = prices.get(asset)
                    if value is not None:
                        result[original] = value
            elif venue == "mock_gold":
                for original, _ in entries:
                    result[original] = self.mock_gold_price
            else:
                raise RuntimeError(f"unsupported venue: {venue}")
        return result


class CachedPriceRouter(PriceProvider):
    def __init__(self, router: PriceRouter | None = None, ttl_seconds: float | None = None):
        self.router = router or PriceRouter()
        ttl = ttl_seconds if ttl_seconds is not None else float(getattr(settings, "PRICE_CACHE_TTL", 5.0))
        self.cache = TTLCache[str, Dict[str, float]](ttl_seconds=ttl)
        self.last_good: Dict[str, Dict[str, float]] = {}

    def get_index_prices(self, symbols: List[str]) -> Dict[str, float]:
        key = ",".join(sorted([s for s in symbols if s]))
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        attempts = int(getattr(settings, "PRICE_RETRIES", 1)) + 1
        backoff = float(getattr(settings, "PRICE_RETRY_BACKOFF_SEC", 0.2))
        last_err: Exception | None = None
        data: Dict[str, float] | None = None
        for i in range(attempts):
            try:
                data = self.router.get_index_prices(symbols)
                break
            except Exception as e:
                last_err = e
                if i < attempts - 1:
                    try:
                        time.sleep(backoff * (2 ** i))
                    except Exception:
                        pass
        if data is None or not data:
            lg = self.last_good.get(key)
            if lg:
                return lg
            if last_err:
                raise last_err
            return {}
        self.cache.set(key, data)
        self.last_good[key] = data
        return data
