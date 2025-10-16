from __future__ import annotations

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List


def _collect_env_files() -> List[str]:
    # Search repo root for a .env alongside local .env
    here = Path(__file__).resolve()
    candidates: List[str] = []
    # local .env (apps/backend/.env)
    candidates.append(str(here.parent.parent / ".env"))
    # repo root .env
    root = here
    for _ in range(6):  # climb up to 6 levels
        if (root / ".git").exists() or (root / "README.md").exists():
            break
        if root.parent == root:
            break
        root = root.parent
    candidates.append(str(root / ".env"))
    # keep order: root first, then local overrides
    # but pydantic-settings later ones override prior; reverse to prefer local
    return [candidates[-1], candidates[0]]


class Settings(BaseSettings):
    # Hyper endpoints
    HYPER_API_URL: str = "https://api.hyperliquid-testnet.xyz"
    HYPER_RPC_URL: str = "https://rpc.hyperliquid-testnet.xyz/evm"
    HYPER_WS_URL: str | None = None

    # Price source selection
    ENABLE_HYPER_SDK: bool = False
    PRICE_TIMEOUT: float = 5.0
    PRICE_CACHE_TTL: float = 2.0
    NAV_CACHE_TTL: float = 2.0
    PRICE_RETRIES: int = 2
    PRICE_RETRY_BACKOFF_SEC: float = 0.2
    ENABLE_LIVE_EXEC: bool = False
    APPLY_DRY_RUN_TO_POSITIONS: bool = True
    # Exec risk controls
    EXEC_ALLOWED_SYMBOLS: str = "BTC,ETH"
    EXEC_MAX_SIZE: float = 100.0
    EXEC_MIN_LEVERAGE: float = 1.0
    EXEC_MAX_LEVERAGE: float = 50.0
    EXEC_MAX_NOTIONAL_USD: float = 1e9
    # Live trading credentials (if SDK uses private key)
    HYPER_TRADER_PRIVATE_KEY: str | None = None
    # Apply fills to positions when live exec succeeds
    APPLY_LIVE_TO_POSITIONS: bool = True

    class Config:
        env_file = tuple(_collect_env_files())
        case_sensitive = False


settings = Settings()
