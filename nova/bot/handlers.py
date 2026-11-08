"""Nova command & message handlers (aiogram v3).

Handlers receive `nb: NovaBot` through aiogram's workflow-data injection
(see run.py: `dp.start_polling(bot, nb=nb)`).
"""

from __future__ import annotations

import logging
import re
import contextlib

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from ..config import CONFIG
from ..db import Database, AlertRow
from ..market import MarketData
from ..models import PRICE_ABOVE, PRICE_BELOW, AlertDraft
from .. import parser as nl
from . import keyboards as kb
from .flows import Flow, FlowStore
from .texts import tr, coin_line, describe_draft

log = logging.getLogger("nova.bot")

router = Router()

_NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")
_WATCH_RE = re.compile(r"^(?:watch|واچ|وچ)\s+(.+)$", re.IGNORECASE)
_BUY_RE = re.compile(
    r"(?:buy|خرید)\s+(\d+(?:\.\d+)?)\s+(.+?)\s+(?:at|به قیمت|به)\s*(\d+(?:\.\d+)?|الان|now)"
)


class NovaBot:
    """Shared state container for all handlers."""

    def __init__(self, db: Database, market: MarketData) -> None:
        self.db = db
        self.market = market
        self.flows = FlowStore()
        self.bot = None  # bound via bind_bot() in run.py

    def bind_bot(self, bot) -> None:
        self.bot = bot

    async def user_lang(self, user_id: int) -> str:
        user = await self.db.ensure_user(user_id, CONFIG.default_lang)
        return user.lang

    # ------------------------------------------------ alert creation core

    async def confirm_flow(self, chat_id: int, draft: AlertDraft) -> None:
        lang = await self.user_lang(chat_id)
        text = (
            f"{tr(lang, 'confirm.title')}\n"
            + describe_draft(self.market, lang, draft.type, draft.symbol,
                             draft.direction, draft.target, draft.describe_params())
        )
        self.flows.start(chat_id, "alert_confirm", draft=draft)
        await self.bot.send_message(chat_id, text, reply_markup=kb.confirm_keyboard())

    async def create_alert_checked(self, chat_id: int, user_id: int, draft: AlertDraft) -> bool:
        lang = await self.user_lang(user_id)
        user = await self.db.get_user(user_id)
        if not user or not user.is_premium:
            n = await self.db.count_active(user_id)
            if n >= CONFIG.free_alert_limit:
                await self.bot.send_message(chat_id, tr(lang, "confirm.limit", limit=CONFIG.free_alert_limit))
                return False
        if draft.type in (PRICE_ABOVE, PRICE_BELOW):
            params: dict = {"target": draft.target, "direction": draft.direction}
        else:
            params = dict(draft.params)
        await self.db.create_alert(user_id, draft.type, draft.symbol, params, draft.raw_text)
        await self.bot.send_message(chat_id, tr(lang, "confirm.created"))
        return True


# --------------------------------------------------------------------------- #
# /start · /lang · /help
# --------------------------------------------------------------------------- #

@router.message(CommandStart())
async def cmd_start(message: Message, nb: NovaBot) -> None:
    user_id = message.from_user.id  # type: ignore[union-attr]
    existing = await nb.db.get_user(user_id)
    user = await nb.db.ensure_user(user_id, CONFIG.default_lang)
    if existing is None:  # first contact -> explicit language choice
        await message.answer(tr(user.lang, "lang.choose"), reply_markup=kb.lang_keyboard())
    await message.answer(tr(user.lang, "start.welcome"))


@router.message(Command("help"))
async def cmd_help(message: Message, nb: NovaBot) -> None:
    lang = await nb.user_lang(message.from_user.id)  # type: ignore[union-attr]
    await message.answer(tr(lang, "help.text"))


@router.message(Command("lang"))
async def cmd_lang(message: Message, nb: NovaBot) -> None:
    lang = await nb.user_lang(message.from_user.id)  # type: ignore[union-attr]
    await message.answer(tr(lang, "lang.choose"), reply_markup=kb.lang_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(cb: CallbackQuery, nb: NovaBot) -> None:
    lang = cb.data.split(":", 1)[1]  # type: ignore[union-attr]
    await nb.db.ensure_user(cb.from_user.id, lang)
    await nb.db.set_lang(cb.from_user.id, lang)
    with contextlib.suppress(Exception):
        await cb.message.edit_text(tr(lang, "lang.changed"))  # type: ignore[union-attr]
    await cb.answer()


# --------------------------------------------------------------------------- #
# guided alert builder (/newalert)
# --------------------------------------------------------------------------- #

@router.message(Command("newalert"))
async def cmd_newalert(message: Message, nb: NovaBot) -> None:
    await message.answer("🪙 Pick a coin / ارز را انتخاب کن:", reply_markup=kb.coin_grid("napick:"))


@router.callback_query(F.data.startswith("napick:"))
async def cb_napick(cb: CallbackQuery, nb: NovaBot) -> None:
    sym = cb.data.split(":", 1)[1]  # type: ignore[union-attr]
    with contextlib.suppress(Exception):
        await cb.message.edit_text(  # type: ignore[union-attr]
            f"🪙 {sym} — ⬆️ Above / بالاتر  یا  ⬇️ Below / پایین‌تر؟",
            reply_markup=kb.direction_keyboard(sym),
        )
    await cb.answer()


@router.callback_query(F.data.startswith("nadir:"))
async def cb_nadir(cb: CallbackQuery, nb: NovaBot) -> None:
    _, direction, sym = cb.data.split(":", 2)  # type: ignore[union-attr]
    nb.flows.start(cb.from_user.id, "alert_price", direction=direction, symbol=sym)
    lang = await nb.user_lang(cb.from_user.id)
    await cb.message.answer(tr(lang, "flow.hint_price", sym=sym))  # type: ignore[union-attr]
    await cb.answer()


@router.callback_query(F.data == "nacancel")
async def cb_nacancel(cb: CallbackQuery, nb: NovaBot) -> None:
    nb.flows.pop(cb.from_user.id)
    lang = await nb.user_lang(cb.from_user.id)
    with contextlib.suppress(Exception):
        await cb.message.edit_text(tr(lang, "flow.cancelled"))  # type: ignore[union-attr]
    await cb.answer()


@router.callback_query(F.data == "nacreate")
async def cb_nacreate(cb: CallbackQuery, nb: NovaBot) -> None:
    flow = nb.flows.pop(cb.from_user.id)
    if not flow or flow.kind != "alert_confirm":
        await cb.answer()
        return
    draft: AlertDraft = flow.data["draft"]
    lang = await nb.user_lang(cb.from_user.id)
    ok = await nb.create_alert_checked(cb.message.chat.id, cb.from_user.id, draft)  # type: ignore[union-attr]
    with contextlib.suppress(Exception):
        await cb.message.edit_text(  # type: ignore[union-attr]
            tr(lang, "confirm.created") if ok else tr(lang, "flow.cancelled"),
            reply_markup=None,
        )
    await cb.answer()


# --------------------------------------------------------------------------- #
# /alerts — list + per-alert delete buttons
# --------------------------------------------------------------------------- #

def _alerts_keyboard(active: list[AlertRow], has_history: bool) -> InlineKeyboardMarkup | None:
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for a in active[:10]:
        b.button(text=f"🗑 {a.symbol}", callback_data=f"al:del:{a.id}")
    b.adjust(3)
    if has_history:
        b.button(text="🧹 Clear history / پاک‌سازی", callback_data="al:clearhist")
        b.adjust(3, 1)
    return b.as_markup()


@router.message(Command("alerts"))
async def cmd_alerts(message: Message, nb: NovaBot) -> None:
    user_id = message.from_user.id  # type: ignore[union-attr]
    lang = await nb.user_lang(user_id)
    active = await nb.db.alerts_by_status("ACTIVE", user_id)
    history = await nb.db.alerts_by_status("TRIGGERED", user_id)

    lines: list[str] = [tr(lang, "alerts.title", n=len(active))]
    if not active:
        lines.append(tr(lang, "alerts.empty"))
    for a in active[:15]:
        lines.append("• " + _alert_line(nb.market, a))
    if history:
        lines.append(tr(lang, "alerts.history"))
        for a in history[-5:]:
            when = (a.triggered_at or "")[:16].replace("T", " ")
            lines.append(f"• ✅ <b>{a.symbol}</b> — {when}")

    await message.answer("\n".join(lines), reply_markup=_alerts_keyboard(active, bool(history)))


def _alert_line(market: MarketData, a: AlertRow) -> str:
    p = a.params()
    if a.type in (PRICE_ABOVE, PRICE_BELOW):
        arrow = "⬆️" if a.type == PRICE_ABOVE else "⬇️"
        target = float(p.get("target", 0))
        price = market.price(a.symbol)
        dist = f" ({(target - price) / price * 100:+.1f}%)" if price else ""
        return f"<b>{a.symbol}</b> {arrow} <code>{market.fmt_price(target)}</code>{dist}"
    return f"<b>{a.symbol}</b> · <code>{a.short_desc()}</code>"


@router.callback_query(F.data.startswith("al:del:"))
async def cb_alert_del(cb: CallbackQuery, nb: NovaBot) -> None:
    alert_id = cb.data.split(":", 2)[2]  # type: ignore[union-attr]
    await nb.db.delete_alert(alert_id, cb.from_user.id)
    lang = await nb.user_lang(cb.from_user.id)
    await cb.answer(tr(lang, "alerts.deleted"))
    with contextlib.suppress(Exception):
        await cb.message.delete()  # type: ignore[union-attr]


@router.callback_query(F.data == "al:clearhist")
async def cb_clearhist(cb: CallbackQuery, nb: NovaBot) -> None:
    await nb.db.clear_history(cb.from_user.id)
    lang = await nb.user_lang(cb.from_user.id)
    await cb.answer(tr(lang, "alerts.cleared"), show_alert=True)


# --------------------------------------------------------------------------- #
# watchlist
# --------------------------------------------------------------------------- #

@router.message(Command("watch"))
async def cmd_watch(message: Message, nb: NovaBot) -> None:
    user_id = message.from_user.id  # type: ignore[union-attr]
    lang = await nb.user_lang(user_id)
    symbols = await nb.db.watchlist(user_id)
    await _render_watch(message, nb, lang, symbols)


async def _render_watch(message: Message, nb: NovaBot, lang: str, symbols: list[str]) -> None:
    lines = [tr(lang, "watch.title")]
    if symbols:
        lines += ["  " + coin_line(nb.market, sym, lang) for sym in symbols]
    else:
        lines.append(tr(lang, "watch.empty"))
    await message.answer("\n".join(lines), reply_markup=kb.watch_keyboard(symbols))


async def _rerender_watch(cb: CallbackQuery, nb: NovaBot, lang: str) -> None:
    symbols = await nb.db.watchlist(cb.from_user.id)
    lines = [tr(lang, "watch.title")]
    lines += ["  " + coin_line(nb.market, s, lang) for s in symbols] or [tr(lang, "watch.empty")]
    with contextlib.suppress(Exception):
        await cb.message.edit_text("\n".join(lines), reply_markup=kb.watch_keyboard(symbols))  # type: ignore[union-attr]


@router.callback_query(F.data == "watch:add")
async def cb_watch_add(cb: CallbackQuery, nb: NovaBot) -> None:
    nb.flows.start(cb.from_user.id, "watch_add")
    await cb.message.answer("🪙 Pick a coin / ارز را انتخاب کن:", reply_markup=kb.coin_grid("watch:pick:"))  # type: ignore[union-attr]
    await cb.answer()


@router.callback_query(F.data.startswith("watch:pick:"))
async def cb_watch_pick(cb: CallbackQuery, nb: NovaBot) -> None:
    sym = cb.data.split(":", 2)[2]  # type: ignore[union-attr]
    lang = await nb.user_lang(cb.from_user.id)
    if not nb.market.ticker(sym):
        await cb.answer(tr(lang, "watch.bad_symbol"), show_alert=True)
        return
    user = await nb.db.get_user(cb.from_user.id)
    if not user or not user.is_premium:
        symbols = await nb.db.watchlist(cb.from_user.id)
        if len(symbols) >= CONFIG.free_watchlist_limit:
            await cb.answer(tr(lang, "watch.limit", limit=CONFIG.free_watchlist_limit), show_alert=True)
            return
    await nb.db.watch_add(cb.from_user.id, sym)
    await cb.answer(tr(lang, "watch.added", sym=sym))
    await _rerender_watch(cb, nb, lang)


@router.callback_query(F.data.startswith("watch:del:"))
async def cb_watch_del(cb: CallbackQuery, nb: NovaBot) -> None:
    sym = cb.data.split(":", 2)[2]  # type: ignore[union-attr]
    await nb.db.watch_remove(cb.from_user.id, sym)
    lang = await nb.user_lang(cb.from_user.id)
    await cb.answer(tr(lang, "watch.removed", sym=sym))
    await _rerender_watch(cb, nb, lang)


# --------------------------------------------------------------------------- #
# portfolio
# --------------------------------------------------------------------------- #

@router.message(Command("portfolio"))
async def cmd_portfolio(message: Message, nb: NovaBot) -> None:
    await _render_portfolio(message, nb)


def _pf_lines(nb: NovaBot, lang: str, rows) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    ids: list[str] = []
    total_now = total_buy = 0.0
    for h in rows:
        now = nb.market.price(h.symbol) or h.buy_price
        value, cost = now * h.amount, h.buy_price * h.amount
        pnl_pct = ((value - cost) / cost * 100) if cost else 0.0
        total_now += value
        total_buy += cost
        ids.append(h.id)
        lines.append(f"• <b>{h.symbol}</b> {h.amount:g} — {nb.market.fmt_price(value)}  ({nb.market.fmt_pct(pnl_pct)})")
    pnl = total_now - total_buy
    pct = (pnl / total_buy * 100) if total_buy else 0.0
    lines.insert(0, tr(lang, "pf.title", total=nb.market.fmt_price(total_now),
                       pnl_pct=nb.market.fmt_pct(pct)))
    return lines, ids


async def _render_portfolio(message: Message, nb: NovaBot) -> None:
    user_id = message.from_user.id  # type: ignore[union-attr]
    lang = await nb.user_lang(user_id)
    rows = await nb.db.holdings(user_id)
    if not rows:
        await message.answer(tr(lang, "pf.empty"), reply_markup=kb.portfolio_keyboard())
        return
    lines, ids = _pf_lines(nb, lang, rows)
    await message.answer("\n".join(lines), reply_markup=kb.portfolio_list_keyboard(ids))


@router.callback_query(F.data == "pf:add")
async def cb_pf_add(cb: CallbackQuery, nb: NovaBot) -> None:
    nb.flows.start(cb.from_user.id, "pf_amount")
    await cb.message.answer("🪙 Pick a coin / ارز را انتخاب کن:", reply_markup=kb.coin_grid("pf:sym:"))  # type: ignore[union-attr]
    await cb.answer()


@router.callback_query(F.data.startswith("pf:sym:"))
async def cb_pf_sym(cb: CallbackQuery, nb: NovaBot) -> None:
    sym = cb.data.split(":", 2)[2]  # type: ignore[union-attr]
    nb.flows.start(cb.from_user.id, "pf_amount", symbol=sym)
    lang = await nb.user_lang(cb.from_user.id)
    await cb.message.answer(tr(lang, "flow.hint_amount", sym=sym))  # type: ignore[union-attr]
    await cb.answer()


@router.callback_query(F.data.startswith("pf:del:"))
async def cb_pf_del(cb: CallbackQuery, nb: NovaBot) -> None:
    hid = cb.data.split(":", 2)[2]  # type: ignore[union-attr]
    await nb.db.delete_holding(hid, cb.from_user.id)
    lang = await nb.user_lang(cb.from_user.id)
    await cb.answer(tr(lang, "pf.deleted"))
    with contextlib.suppress(Exception):
        await cb.message.delete()  # type: ignore[union-attr]


@router.callback_query(F.data.startswith("pf:now:"))
async def cb_pf_now(cb: CallbackQuery, nb: NovaBot) -> None:
    flow = nb.flows.pop(cb.from_user.id)
    if not flow or flow.kind != "pf_buy":
        await cb.answer()
        return
    flow.data["buy"] = nb.market.price(flow.data["symbol"]) or 0.0
    await _finish_holding(cb.message.chat.id, nb, cb.from_user.id, flow)  # type: ignore[union-attr]
    await cb.answer()


async def _finish_holding(chat_id: int, nb: NovaBot, user_id: int, flow: Flow) -> None:
    lang = await nb.user_lang(user_id)
    user = await nb.db.get_user(user_id)
    if not user or not user.is_premium:
        if await nb.db.count_holdings(user_id) >= CONFIG.free_portfolio_limit:
            await nb.bot.send_message(chat_id, tr(lang, "pf.limit", limit=CONFIG.free_portfolio_limit))
            return
    if flow.data.get("buy", 0) <= 0:
        flow.data["buy"] = nb.market.price(flow.data["symbol"]) or 0.0
    await nb.db.add_holding(user_id, flow.data["symbol"], flow.data["amount"], flow.data["buy"])
    await nb.bot.send_message(
        chat_id,
        tr(lang, "pf.added", amount=flow.data["amount"], sym=flow.data["symbol"],
           price=nb.market.fmt_price(flow.data["buy"])),
    )


# --------------------------------------------------------------------------- #
# digest
# --------------------------------------------------------------------------- #

@router.message(Command("digest"))
async def cmd_digest(message: Message, nb: NovaBot) -> None:
    user = await nb.db.ensure_user(message.from_user.id, CONFIG.default_lang)  # type: ignore[union-attr]
    lang = user.lang
    hour = user.digest_hour if user.digest_hour is not None else 8
    await message.answer(
        tr(lang, "digest.title", status="✅" if user.digest_enabled else "💤", hour=hour),
        reply_markup=kb.digest_keyboard(bool(user.digest_enabled), user.digest_hour),
    )


async def _dig_update(cb: CallbackQuery, nb: NovaBot, enabled: bool, hour: int) -> None:
    lang = await nb.user_lang(cb.from_user.id)
    await nb.db.set_digest(cb.from_user.id, enabled, hour)
    with contextlib.suppress(Exception):
        await cb.message.edit_text(  # type: ignore[union-attr]
            tr(lang, "digest.title", status="✅" if enabled else "💤", hour=hour),
            reply_markup=kb.digest_keyboard(enabled, hour),
        )
    await cb.answer(tr(lang, "digest.on" if enabled else "digest.off", hour=hour))


@router.callback_query(F.data == "dig:toggle")
async def cb_dig_toggle(cb: CallbackQuery, nb: NovaBot) -> None:
    user = await nb.db.get_user(cb.from_user.id)
    enabled = not (user.digest_enabled if user else False)
    hour = user.digest_hour if (user and user.digest_hour is not None) else 8
    await _dig_update(cb, nb, enabled, hour)


@router.callback_query(F.data.startswith("dig:hour:"))
async def cb_dig_hour(cb: CallbackQuery, nb: NovaBot) -> None:
    hour = int(cb.data.split(":", 2)[2])  # type: ignore[union-attr]
    await _dig_update(cb, nb, True, hour)


# --------------------------------------------------------------------------- #
# premium & admin
# --------------------------------------------------------------------------- #

@router.message(Command("premium"))
async def cmd_premium(message: Message, nb: NovaBot) -> None:
    user = await nb.db.ensure_user(message.from_user.id, CONFIG.default_lang)  # type: ignore[union-attr]
    lang = user.lang
    until = f" — {user.premium_until[:10]}" if (user.is_premium and user.premium_until) else ""
    await message.answer(tr(lang, "premium.status", tier=user.tier, until=until))
    await message.answer(tr(lang, "premium.title", free_limit=CONFIG.free_alert_limit,
                            price="9", wallet=CONFIG.payment_wallet or "SET-PAYMENT-WALLET-IN-ENV"))
    nb.flows.start(message.chat.id, "premium_code")


@router.message(Command("admin"))
async def cmd_admin(message: Message, nb: NovaBot) -> None:
    user_id = message.from_user.id  # type: ignore[union-attr]
    lang = await nb.user_lang(user_id)
    if not CONFIG.is_admin(user_id):
        await message.answer(tr(lang, "admin.denied"))
        return
    await message.answer(tr(lang, "admin.title", **await nb.db.stats()))


@router.message(Command("gencode"))
async def cmd_gencode(message: Message, nb: NovaBot) -> None:
    user_id = message.from_user.id  # type: ignore[union-attr]
    lang = await nb.user_lang(user_id)
    if not CONFIG.is_admin(user_id):
        await message.answer(tr(lang, "admin.denied"))
        return
    parts = (message.text or "").split()
    n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
    days = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 30
    codes = await nb.db.gen_codes(min(n, 20), days)
    await message.answer(tr(lang, "admin.gen", days=days, codes="\n".join(codes)))


# --------------------------------------------------------------------------- #
# free text: guided flows → quick commands → NL alerts
# --------------------------------------------------------------------------- #

@router.message(F.text)
async def on_text(message: Message, nb: NovaBot) -> None:
    user_id = message.from_user.id  # type: ignore[union-attr]
    chat_id = message.chat.id
    lang = await nb.user_lang(user_id)
    text = (message.text or "").strip()

    # 1) guided flow in progress?
    flow = nb.flows.peek(user_id)
    if flow:
        num = text.replace(",", "")
        if flow.kind == "alert_price" and _NUM_RE.match(num):
            nb.flows.pop(user_id)
            draft = AlertDraft(
                PRICE_ABOVE if flow.data["direction"] == "ABOVE" else PRICE_BELOW,
                flow.data["symbol"], {}, direction=flow.data["direction"], target=float(num),
            )
            await nb.confirm_flow(chat_id, draft)
            return
        if flow.kind == "pf_amount" and _NUM_RE.match(num):
            nb.flows.start(user_id, "pf_buy", symbol=flow.data["symbol"], amount=float(num))
            await message.answer(tr(lang, "flow.hint_buy"), reply_markup=kb.now_keyboard("pf:now:"))
            return
        if flow.kind == "pf_buy" and _NUM_RE.match(num):
            flow.data["buy"] = float(num)
            nb.flows.pop(user_id)
            await _finish_holding(chat_id, nb, user_id, flow)
            return
        if flow.kind == "premium_code" and text.upper().startswith("NOVA-"):
            nb.flows.pop(user_id)
            days = await nb.db.redeem_code(text, user_id)  # atomically extends premium
            await message.answer(tr(lang, "premium.ok", days=days) if days else tr(lang, "premium.bad"))
            return

    # 2) "watch sol" / "واچ سول"
    m = _WATCH_RE.match(text)
    if m:
        sym = nl._find_symbol(nl.normalize(m.group(1)))
        if sym and nb.market.ticker(sym):
            user = await nb.db.get_user(user_id)
            symbols = await nb.db.watchlist(user_id)
            if not user or not user.is_premium:
                if len(symbols) >= CONFIG.free_watchlist_limit:
                    await message.answer(tr(lang, "watch.limit", limit=CONFIG.free_watchlist_limit))
                    return
            await nb.db.watch_add(user_id, sym)
            await message.answer(tr(lang, "watch.added", sym=sym))
            return
        await message.answer(tr(lang, "watch.bad_symbol"))
        return

    # 3) "buy 0.5 eth at 2200" / "خرید 0.5 اتریوم به قیمت 2200"
    holding = _parse_holding(text)
    if holding:
        sym, amount, buy = holding
        user = await nb.db.get_user(user_id)
        if not user or not user.is_premium:
            if await nb.db.count_holdings(user_id) >= CONFIG.free_portfolio_limit:
                await message.answer(tr(lang, "pf.limit", limit=CONFIG.free_portfolio_limit))
                return
        price = buy or (nb.market.price(sym) or 0.0)
        await nb.db.add_holding(user_id, sym, amount, price)
        await message.answer(tr(lang, "pf.added", amount=amount, sym=sym,
                                price=nb.market.fmt_price(price)))
        return

    # 4) natural-language alert
    draft = nl.parse_alert(text)
    if draft:
        await nb.confirm_flow(chat_id, draft)
        return

    # 5) fallback
    await message.answer(tr(lang, "err.parse"))


def _parse_holding(text: str) -> tuple[str, float, float] | None:
    t = nl.normalize(text)
    m = _BUY_RE.search(t)
    if not m:
        return None
    sym = nl._find_symbol(m.group(2))
    if sym is None:
        return None
    amount = float(m.group(1))
    price_raw = m.group(3)
    buy = 0.0 if price_raw in ("الان", "now") else float(price_raw)
    return sym, amount, buy
