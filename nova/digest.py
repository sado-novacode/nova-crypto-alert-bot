"""Daily morning digest scheduler.

Checks once a minute; sends each opted-in user their digest at their
chosen UTC hour, exactly once per UTC day.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from .db import Database
from .market import MarketData
from .bot.texts import fmt_digest

log = logging.getLogger("nova.digest")


class DigestScheduler:
    def __init__(self, db: Database, market: MarketData, bot_getter) -> None:
        self.db = db
        self.market = market
        self._bot_getter = bot_getter

    async def run_forever(self) -> None:
        log.info("Digest scheduler started")
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                log.exception("digest tick failed")
            await asyncio.sleep(60)

    async def tick(self) -> None:
        now = datetime.now(timezone.utc)
        users = await self.db.digest_users()
        if not users:
            return
        today = now.strftime("%Y-%m-%d")
        for user in users:
            hour = user.digest_hour if user.digest_hour is not None else 8
            if now.hour != hour or user.last_digest_on == today:
                continue
            try:
                await self._send(user.user_id, user.lang)
                await self.db.mark_digest_sent(user.user_id, today)
            except Exception:  # noqa: BLE001
                log.warning("digest delivery failed for %s", user.user_id)

    async def _send(self, user_id: int, lang: str) -> None:
        watch = await self.db.watchlist(user_id)
        pf_rows = []
        for h in await self.db.holdings(user_id):
            now_price = self.market.price(h.symbol) or h.buy_price
            pf_rows.append((h.symbol, h.amount, h.buy_price, now_price))
        text = fmt_digest(self.market, lang, watch, pf_rows)
        await self._bot_getter().send_message(user_id, text)
