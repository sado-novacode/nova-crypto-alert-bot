"""The alert engine — evaluates ACTIVE alerts on a 10-second tick.

Design notes
------------
* one-shot semantics: every alert fires at most once (ACTIVE -> TRIGGERED),
  so users are never spammed and state survives restarts.
* the rolling high of TRAILING alerts is persisted into the alert params,
  so a restart does not lose progress.
* notifications are sent concurrently and never block the tick loop.
"""

from __future__ import annotations

import asyncio
import logging
import time

from .config import CONFIG
from .db import Database, AlertRow
from .market import MarketData
from .models import (
    PCT_DOWN_1H, PCT_DOWN_24H, PCT_UP_1H, PCT_UP_24H,
    RAPID_DROP, RAPID_PUMP, TRAILING_DOWN, VOLUME_SPIKE,
    PRICE_ABOVE, PRICE_BELOW, Ticker,
)
from .rules import (
    eval_price, eval_pct_change, eval_pct_change_history,
    eval_rapid_move, eval_trailing, eval_volume_spike,
)
from .bot.texts import fmt_alert_fired

log = logging.getLogger("nova.engine")


class AlertEngine:
    def __init__(self, db: Database, market: MarketData, bot_getter) -> None:
        self.db = db
        self.market = market
        self._bot_getter = bot_getter          # zero-arg callable -> aiogram Bot
        self._rolling_high: dict[str, float] = {}
        self._last_high_persist = 0.0

    async def run_forever(self) -> None:
        log.info("Engine started (interval=%ss)", CONFIG.engine_interval)
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                log.exception("engine tick failed")
            await asyncio.sleep(CONFIG.engine_interval)

    async def tick(self) -> None:
        alerts = await self.db.alerts_by_status("ACTIVE")
        if not alerts:
            return

        # seed trailing highs after a restart
        for alert in alerts:
            if alert.type == TRAILING_DOWN and alert.id not in self._rolling_high:
                self._rolling_high[alert.id] = float(alert.params().get("high", 0.0))

        fired: dict[int, list[tuple[AlertRow, Ticker, str]]] = {}

        for alert in alerts:
            t = self.market.ticker(alert.symbol)
            if t is None or not self.market.sane_number(t.price):
                continue
            reason = self._evaluate(alert, t)
            if reason:
                await self.db.trigger_alert(alert.id)
                fired.setdefault(alert.user_id, []).append((alert, t, reason))

        if fired:
            await asyncio.gather(
                *(self._notify(uid, items) for uid, items in fired.items()),
                return_exceptions=True,
            )

        # persist trailing highs periodically (restart safety)
        if time.time() - self._last_high_persist > CONFIG.trailing_update_interval:
            self._last_high_persist = time.time()
            for alert in alerts:
                if alert.type == TRAILING_DOWN and alert.id in self._rolling_high:
                    params = alert.params()
                    params["high"] = self._rolling_high[alert.id]
                    await self.db.update_alert_params(alert.id, params)

    # ------------------------------------------------------------- rules

    def _evaluate(self, alert: AlertRow, t: Ticker) -> str | None:
        p = alert.params()
        symbol, a_type = alert.symbol, alert.type

        if a_type in (PRICE_ABOVE, PRICE_BELOW):
            target = float(p.get("target", 0))
            if target > 0 and eval_price(a_type, target, t):
                return f"price {'crossed above' if a_type == PRICE_ABOVE else 'dropped below'} {target:,.0f}"

        elif a_type in (PCT_UP_1H, PCT_DOWN_1H):
            then = self.market.price_minutes_ago(symbol, 60)
            if eval_pct_change_history(a_type, float(p.get("pct", 0)), t.price, then):
                return f"1h move crossed ±{p.get('pct'):g}%"

        elif a_type in (PCT_UP_24H, PCT_DOWN_24H):
            if eval_pct_change(a_type, float(p.get("pct", 0)), t):
                return f"24h move crossed ±{p.get('pct'):g}%"

        elif a_type in (RAPID_DROP, RAPID_PUMP):
            window = float(p.get("window_min", 15))
            then = self.market.price_minutes_ago(symbol, window)
            if eval_rapid_move(a_type, float(p.get("pct", 0)), window, t.price, then):
                verb = "dropped" if a_type == RAPID_DROP else "pumped"
                return f"{verb} {p.get('pct'):g}% within {window:g} min"

        elif a_type == VOLUME_SPIKE:
            baseline = self.market.minute_volume_baseline(symbol)
            last_vol = self.market.last_minute_volume(symbol)
            if eval_volume_spike(float(p.get("mult", 0)), last_vol, baseline):
                return f"volume exceeded {p.get('mult'):g}× the 30-min baseline"

        elif a_type == TRAILING_DOWN:
            high = max(self._rolling_high.get(alert.id, 0.0), t.price)
            self._rolling_high[alert.id] = high
            if eval_trailing(float(p.get("pct", 0)), high, t.price):
                return f"{p.get('pct'):g}% off the recent high {high:,.0f}"

        return None

    # ----------------------------------------------------------- delivery

    async def _notify(self, user_id: int, items: list[tuple[AlertRow, Ticker, str]]) -> None:
        user = await self.db.get_user(user_id)
        lang = user.lang if user else CONFIG.default_lang
        bot = self._bot_getter()
        for alert, t, reason in items:
            try:
                await bot.send_message(user_id, fmt_alert_fired(alert, t, reason, self.market, lang))
            except Exception:  # noqa: BLE001
                log.warning("notify failed for user %s", user_id)
