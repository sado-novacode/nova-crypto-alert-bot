"""Inline keyboards for Nova."""

from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from ..market import TOP_COINS


def lang_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🇮🇷 فارسی", callback_data="lang:fa")
    kb.button(text="🇬🇧 English", callback_data="lang:en")
    kb.adjust(2)
    return kb.as_markup()


def coin_grid(prefix: str, rows: int = 4) -> InlineKeyboardMarkup:
    """Grid of popular coins with a callback prefix, e.g. 'napick:BTC'."""
    kb = InlineKeyboardBuilder()
    for sym in TOP_COINS[:20]:
        kb.button(text=sym, callback_data=f"{prefix}{sym}")
    kb.adjust(4)
    return kb.as_markup()


def direction_keyboard(sym: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬆️ بالاتر / Above", callback_data=f"nadir:ABOVE:{sym}")
    kb.button(text="⬇️ پایین‌تر / Below", callback_data=f"nadir:BELOW:{sym}")
    kb.button(text="✖ Cancel / انصراف", callback_data="nacancel")
    kb.adjust(2, 1)
    return kb.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Create / ثبت", callback_data="nacreate")
    kb.button(text="✖ Cancel / انصراف", callback_data="nacancel")
    kb.adjust(2)
    return kb.as_markup()


def watch_keyboard(symbols: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for sym in symbols:
        kb.button(text=f"✖ {sym}", callback_data=f"watch:del:{sym}")
    kb.button(text="➕ Add / افزودن", callback_data="watch:add")
    kb.adjust(4)
    return kb.as_markup()


def portfolio_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Add holding / افزودن دارایی", callback_data="pf:add")
    kb.adjust(1)
    return kb.as_markup()


def portfolio_list_keyboard(ids: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for hid in ids:
        kb.button(text="🗑", callback_data=f"pf:del:{hid}")
    kb.adjust(6)
    return kb.as_markup()


def digest_keyboard(enabled: bool, hour: int | None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=("💤 Turn off / خاموش" if enabled else "🌅 Turn on / روشن"),
              callback_data="dig:toggle")
    if enabled:
        for h in (6, 7, 8, 9):
            mark = "✔️" if hour == h else str(h)
            kb.button(text=mark, callback_data=f"dig:hour:{h}")
    kb.adjust(2, 4)
    return kb.as_markup()


def now_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """A single 'use current price' button for buy-price flows."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📍 Now / الان", callback_data=prefix)
    kb.button(text="✖ Cancel / انصراف", callback_data="nacancel")
    kb.adjust(2)
    return kb.as_markup()
