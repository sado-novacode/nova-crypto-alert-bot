"""Rule evaluation for every alert type against live market data.

Pure functions (market snapshot in -> bool out) so they are unit-testable
without Telegram or a database.
"""

from __future__ import annotations

from .models import (
    PCT_DOWN_1H, PCT_DOWN_24H, PCT_UP_1H, PCT_UP_24H,
    RAPID_DROP, RAPID_PUMP, TRAILING_DOWN, VOLUME_SPIKE,
    PRICE_ABOVE, PRICE_BELOW, Ticker,
)
from .config import CONFIG


def eval_price(alert_type: str, target: float, t: Ticker) -> bool:
    if alert_type == PRICE_ABOVE:
        return t.price >= target
    if alert_type == PRICE_BELOW:
        return t.price <= target
    return False


def eval_pct_change(alert_type: str, pct: float, t: Ticker) -> bool:
    change = t.change_24h_pct
    if alert_type == PCT_UP_24H:
        return change >= pct
    if alert_type == PCT_DOWN_24H:
        return change <= -pct
    # 1h variants use the market price history
    return False


def eval_pct_change_history(alert_type: str, pct: float, price_now: float, price_then: float | None) -> bool:
    if price_then is None or price_then <= 0:
        return False
    change = (price_now - price_then) / price_then * 100
    if alert_type == PCT_UP_1H:
        return change >= pct
    if alert_type == PCT_DOWN_1H:
        return change <= -pct
    return False


def eval_volume_spike(mult: float, last_minute_vol: float | None, baseline: float | None) -> bool:
    if last_minute_vol is None or baseline is None:
        return False
    if baseline < CONFIG.volume_baseline_min_usd:
        return False  # illiquid pair — ignore noise
    return last_minute_vol >= mult * baseline


def eval_rapid_move(alert_type: str, pct: float, window_min: float,
                    price_now: float, price_then: float | None) -> bool:
    if price_then is None or price_then <= 0:
        return False
    change = (price_now - price_then) / price_then * 100
    if alert_type == RAPID_DROP:
        return change <= -pct
    if alert_type == RAPID_PUMP:
        return change >= pct
    return False


def eval_trailing(pct: float, rolling_high: float, price_now: float) -> bool:
    if rolling_high <= 0:
        return False
    return price_now <= rolling_high * (1 - pct / 100)
