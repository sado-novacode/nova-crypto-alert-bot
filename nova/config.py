"""Environment configuration for Nova."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

FA = "fa"
EN = "en"


def _admin_ids(raw: str) -> list[int]:
    out: list[int] = []
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


@dataclass(frozen=True)
class Config:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", "").strip())
    admin_ids: list[int] = field(default_factory=lambda: _admin_ids(os.getenv("ADMIN_IDS", "")))
    default_lang: str = field(default_factory=lambda: (os.getenv("DEFAULT_LANG") or "fa").strip().lower())
    payment_wallet: str = field(default_factory=lambda: os.getenv("PAYMENT_WALLET", "").strip())
    database_path: str = field(default_factory=lambda: os.getenv("DATABASE_PATH", "nova.db").strip())

    # alert engine tick (seconds)
    engine_interval: int = 10
    # market data
    ws_url: str = "wss://stream.binance.com:9443/ws/!miniTicker@arr"
    rest_base: str = "https://api.binance.com/api/v3"
    stale_after: int = 30          # seconds after which WS data is stale -> REST fallback
    rest_poll_interval: int = 45   # fallback polling period (seconds)

    # free tier limits
    free_alert_limit: int = 5
    free_watchlist_limit: int = 10
    free_portfolio_limit: int = 10

    # smart-alert guardrails
    volume_baseline_min_usd: float = 50_000.0   # ignore spikes on illiquid pairs
    trailing_update_interval: int = 30          # seconds between rolling-high persistence

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids

    def validate(self) -> None:
        if not self.bot_token or "YOUR_TOKEN" in self.bot_token:
            raise SystemExit(
                "[!] BOT_TOKEN is missing.\n"
                "    1) Message @BotFather on Telegram -> /newbot\n"
                "    2) Copy .env.example to .env and paste the token\n"
                "    3) Run again:  python run.py"
            )


CONFIG = Config()
