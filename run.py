#!/usr/bin/env python3
"""Nova — Crypto Alert Bot. Entry point.

    python run.py
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from nova.config import CONFIG
from nova.db import Database
from nova.market import MarketData
from nova.engine import AlertEngine
from nova.digest import DigestScheduler
from nova.bot.handlers import NovaBot, router


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    CONFIG.validate()

    db = Database(CONFIG.database_path)
    await db.connect()

    market = MarketData()

    bot = Bot(CONFIG.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    nb = NovaBot(db, market)
    nb.bind_bot(bot)

    engine = AlertEngine(db, market, lambda: nb.bot)
    digest = DigestScheduler(db, market, lambda: nb.bot)

    dp.include_router(router)

    await bot.set_my_commands([
        BotCommand(command="newalert", description="🔔 New alert / هشدار جدید"),
        BotCommand(command="alerts", description="🔔 My alerts / هشدارهای من"),
        BotCommand(command="watch", description="⭐ Watchlist / واچ‌لیست"),
        BotCommand(command="portfolio", description="💼 Portfolio / پورتفوی"),
        BotCommand(command="digest", description="🌅 Morning digest / گزارش صبح"),
        BotCommand(command="premium", description="💎 Premium / ارتقا"),
        BotCommand(command="lang", description="🌐 Language / زبان"),
        BotCommand(command="help", description="❓ Guide / راهنما"),
    ])

    market_task = asyncio.create_task(market.start(), name="market")
    engine_task = asyncio.create_task(engine.run_forever(), name="engine")
    digest_task = asyncio.create_task(digest.run_forever(), name="digest")

    print(
        "⚡ Nova is starting...\n"
        f"   db: {CONFIG.database_path}\n"
        f"   admins: {CONFIG.admin_ids or '-'}\n"
        "   Press Ctrl+C to stop."
    )
    try:
        await dp.start_polling(bot, nb=nb, handle_signals=True)
    finally:
        for task in (market_task, engine_task, digest_task):
            task.cancel()
        await market.stop()
        await db.close()
        print("Nova stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, SystemExit) and "BOT_TOKEN" in str(exc):
            sys.exit(str(exc))
