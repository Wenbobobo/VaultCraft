from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Hyper endpoints
    HYPER_API_URL: str = "https://api.hyperliquid-testnet.xyz"
    HYPER_RPC_URL: str = "https://rpc.hyperliquid-testnet.xyz/evm"
    HYPER_WS_URL: str | None = None

    # Price source selection
    ENABLE_HYPER_SDK: bool = False
    PRICE_TIMEOUT: float = 5.0

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

