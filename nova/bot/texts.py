"""Bilingual strings (FA/EN) + message builders for Nova."""

from __future__ import annotations

from ..db import AlertRow
from ..models import Ticker
from ..market import MarketData
from ..config import CONFIG

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "app.name": "⚡ Nova",
        "start.welcome": (
            "<b>⚡ Nova — your crypto co-pilot</b>\n\n"
            "Just write what you want in plain words. For example:\n"
            "• <code>btc above 100000</code>\n"
            "• <code>eth below 1800</code>\n"
            "• <code>solana -5% in one hour</code>\n"
            "• <code>pepe volume 3x</code>\n\n"
            "Commands:\n"
            "/newalert — guided alert builder\n"
            "/alerts — my alerts\n"
            "/watch — watchlist\n"
            "/portfolio — portfolio P&amp;L\n"
            "/digest — morning digest settings\n"
            "/premium — upgrade\n"
            "/lang — language  |  /help — full guide"
        ),
        "lang.changed": "✅ Language: English",
        "lang.choose": "Choose your language / زبان را انتخاب کن:",
        "err.parse": (
            "🤔 I couldn't find an alert in that.\n\n"
            "Try one of these:\n"
            "• <code>btc above 100000</code>\n"
            "• <code>eth below 1800</code>\n"
            "• <code>solana -5% in 1 hour</code>\n"
            "• <code>pepe volume 3x</code>\n"
            "• <code>btc -8% from high</code>"
        ),
        "confirm.title": "🧠 I understood it as:",
        "confirm.created": "✅ Alert created — I'm watching. I'll message you the moment it fires.",
        "confirm.limit": (
            "⚠️ Free plan holds {limit} active alerts. You're at the limit — "
            "delete one in /alerts or upgrade in /premium."
        ),
        "alerts.title": "🔔 <b>Your alerts</b> ({n} active)",
        "alerts.empty": "No active alerts yet.\nSend me a sentence like <code>btc above 100000</code> ✍️",
        "alerts.history": "\n<b>🕘 Recently fired</b>",
        "alerts.deleted": "🗑 Deleted.",
        "alerts.cleared": "✅ History cleared.",
        "watch.title": "⭐ <b>Watchlist</b>",
        "watch.empty": "Empty. Add coins from the button below or send e.g. <code>watch sol</code>.",
        "watch.added": "⭐ {sym} added to watchlist.",
        "watch.removed": "✖ {sym} removed.",
        "watch.limit": "⚠️ Watchlist limit is {limit} coins on the free plan.",
        "watch.bad_symbol": "❓ Unknown symbol. Try BTC, ETH, SOL…",
        "pf.title": "💼 <b>Portfolio</b> — total {total} ({pnl_pct})",
        "pf.empty": "No holdings yet.\nAdd one: <code>/addholding</code> or send <code>buy 0.5 eth at 60000</code>.",
        "pf.added": "✅ {amount:g} {sym} @ {price} added.",
        "pf.deleted": "🗑 Holding removed.",
        "pf.limit": "⚠️ Portfolio limit is {limit} holdings on the free plan.",
        "pf.bad_format": (
            "Format: <code>buy 0.5 btc at 60000</code>\n"
            "(amount, symbol, buy price — or say <code>now</code> for the current price)"
        ),
        "digest.title": "🌅 <b>Morning digest</b>\nStatus: {status}  ·  Hour: {hour}:00 UTC",
        "digest.on": "✅ Digest is ON — I'll send it every day at {hour}:00 UTC.",
        "digest.off": "💤 Digest is off.",
        "digest.header": "🌅 <b>Good morning! {date}</b>\n",
        "premium.title": (
            "💎 <b>Nova Premium</b>\n\n"
            "Free: {free_limit} active alerts\n"
            "Premium: <b>unlimited</b> alerts + smart signals + priority delivery\n\n"
            "1) Send {price} USDT (TRC20) to:\n<code>{wallet}</code>\n"
            "2) Admin sends you a code\n"
            "3) Paste it here like: <code>NOVA-AB12CD34</code>"
        ),
        "premium.status": "💎 Your plan: <b>{tier}</b>{until}",
        "premium.ok": "🎉 Premium activated for <b>{days} days</b>. Enjoy!",
        "premium.bad": "❌ Invalid or already-used code.",
        "admin.title": "🛠 <b>Admin</b>\nUsers: {users} (💎 {premium})\nAlerts: {alerts_active} active / {alerts_fired} fired\nHoldings: {holdings}",
        "admin.gen": "🎫 New codes ({days} days):\n{codes}",
        "admin.denied": "⛔ Admin only.",
        "help.text": (
            "<b>⚡ Nova guide</b>\n\n"
            "<b>Write naturally:</b>\n"
            "<code>btc above 100000</code> — price alert\n"
            "<code>eth below 1800</code> — price alert\n"
            "<code>solana -5% in 15 minutes</code> — rapid drop\n"
            "<code>bitcoin +10% in 24h</code> — daily move\n"
            "<code>pepe volume 3x</code> — volume spike\n"
            "<code>btc -8% from high</code> — trailing\n"
            "<code>buy 0.5 eth at 2200</code> — add to portfolio\n"
            "<code>watch sol</code> — add to watchlist\n\n"
            "<b>Commands:</b>\n"
            "/newalert /alerts /watch /portfolio /digest /premium /lang /admin\n\n"
            "All alerts are one-shot: they fire once, then move to history. "
            "Prices: Binance live feed (USDT pairs)."
        ),
        "flow.hint_price": "🔢 Send the target price for {sym} (e.g. <code>65000</code>):",
        "flow.hint_amount": "🔢 How many {sym}? (e.g. <code>0.5</code>)",
        "flow.hint_buy": "🔢 Your buy price in USD (or tap <code>Now</code>):",
        "flow.cancelled": "❎ Cancelled.",
        "btn.above": "⬆️ Rises above",
        "btn.below": "⬇️ Falls below",
    },
    "fa": {
        "app.name": "⚡ نوا",
        "start.welcome": (
            "<b>⚡ نوا — دستیار رمزارز تو</b>\n\n"
            "فقط به زبان خودت بگو چی می‌خوای. مثلاً:\n"
            "• <code>بیت‌کوین بالای ۱۰۰ هزار دلار</code>\n"
            "• <code>اتریوم زیر 1800</code>\n"
            "• <code>سولانا ۵٪ تو یه ساعت افت کرد</code>\n"
            "• <code>پپه حجم ۳ برابر</code>\n\n"
            "دستورها:\n"
            "/newalert — ساخت هشدار با منو\n"
            "/alerts — هشدارهای من\n"
            "/watch — واچ‌لیست\n"
            "/portfolio — پورتفوی و سود/زیان\n"
            "/digest — گزارش صبحگاهی\n"
            "/premium — ارتقا\n"
            "/lang — زبان  |  /help — راهنمای کامل"
        ),
        "lang.changed": "✅ زبان: فارسی",
        "lang.choose": "زبان را انتخاب کن / Choose your language:",
        "err.parse": (
            "🤔 متوجه هشداری نشدم.\n\n"
            "یکی از این‌ها را امتحان کن:\n"
            "• <code>بیت‌کوین بالای ۱۰۰ هزار دلار</code>\n"
            "• <code>اتریوم زیر 1800</code>\n"
            "• <code>سولانا ۵٪ تو ۱۵ دقیقه افت کرد</code>\n"
            "• <code>پپه حجم ۳ برابر</code>\n"
            "• <code>بیت‌کوین ۸٪ از سقف</code>"
        ),
        "confirm.title": "🧠 این‌طوری فهمیدم:",
        "confirm.created": "✅ هشدار ساخته شد — دارم می‌پرسم. به محض فعال شدن خبرت می‌کنم.",
        "confirm.limit": (
            "⚠️ طرح رایگان {limit} هشدار فعال دارد. الان به سقف رسیدی — "
            "یکی را در /alerts حذف کن یا در /premium ارتقا بده."
        ),
        "alerts.title": "🔔 <b>هشدارهای تو</b> ({n} فعال)",
        "alerts.empty": "هنوز هشداری نداری.\nیک جمله بنویس مثل <code>بیت‌کوین بالای ۱۰۰ هزار دلار</code> ✍️",
        "alerts.history": "\n<b>🕘 اخیراً فعال‌شده</b>",
        "alerts.deleted": "🗑 حذف شد.",
        "alerts.cleared": "✅ تاریخچه پاک شد.",
        "watch.title": "⭐ <b>واچ‌لیست</b>",
        "watch.empty": "خالی است. از دکمه زیر اضافه کن یا بنویس <code>واچ سول</code>.",
        "watch.added": "⭐ {sym} به واچ‌لیست اضافه شد.",
        "watch.removed": "✖ {sym} حذف شد.",
        "watch.limit": "⚠️ سقف واچ‌لیست در طرح رایگان {limit} ارز است.",
        "watch.bad_symbol": "❓ نماد نامعتبر. مثلاً BTC، ETH، SOL…",
        "pf.title": "💼 <b>پورتفوی</b> — مجموع {total} ({pnl_pct})",
        "pf.empty": "دارایی ثبت نشده.\nاضافه کن: <code>/addholding</code> یا بنویس <code>خرید 0.5 اتریوم به قیمت 2200</code>.",
        "pf.added": "✅ {amount:g} {sym} با قیمت {price} ثبت شد.",
        "pf.deleted": "🗑 حذف شد.",
        "pf.limit": "⚠️ سقف پورتفوی در طرح رایگان {limit} قلم است.",
        "pf.bad_format": (
            "قالب: <code>خرید 0.5 بیت‌کوین به قیمت 60000</code>\n"
            "(مقدار، نماد، قیمت خرید — یا به‌جای قیمت بنویس <code>الان</code>)"
        ),
        "digest.title": "🌅 <b>گزارش صبحگاهی</b>\nوضعیت: {status}  ·  ساعت: {hour}:00 UTC",
        "digest.on": "✅ گزارش روشن شد — هر روز ساعت {hour}:00 UTC می‌فرستم.",
        "digest.off": "💤 گزارش خاموش است.",
        "digest.header": "🌅 <b>صبح بخیر! {date}</b>\n",
        "premium.title": (
            "💎 <b>نوا پریمیوم</b>\n\n"
            "رایگان: {free_limit} هشدار فعال\n"
            "پریمیوم: هشدار <b>نامحدود</b> + سیگنال‌های هوشمند + ارسال اولویت‌دار\n\n"
            "۱) مبلغ {price} USDT (شبکه TRC20) به این آدرس واریز کن:\n<code>{wallet}</code>\n"
            "۲) ادمین برایت کد می‌فرستد\n"
            "۳) همین‌جا بفرست: <code>NOVA-AB12CD34</code>"
        ),
        "premium.status": "💎 طرح تو: <b>{tier}</b>{until}",
        "premium.ok": "🎉 پریمیوم برای <b>{days} روز</b> فعال شد. خوش بگذره!",
        "premium.bad": "❌ کد نامعتبر است یا قبلاً استفاده شده.",
        "admin.title": "🛠 <b>ادمین</b>\nکاربران: {users} (💎 {premium})\nهشدارها: {alerts_active} فعال / {alerts_fired} فعال‌شده\nدارایی‌ها: {holdings}",
        "admin.gen": "🎫 کدهای جدید ({days} روزه):\n{codes}",
        "admin.denied": "⛔ فقط ادمین.",
        "help.text": (
            "<b>⚡ راهنمای نوا</b>\n\n"
            "<b>طبیعی بنویس:</b>\n"
            "<code>بیت‌کوین بالای ۱۰۰ هزار دلار</code> — هشدار قیمت\n"
            "<code>اتریوم زیر 1800</code> — هشدار قیمت\n"
            "<code>سولانا ۵٪ تو ۱۵ دقیقه افت کرد</code> — ریزش سریع\n"
            "<code>بیت‌کوین ۱۰٪ تو ۲۴ ساعت بالا رفت</code> — حرکت روزانه\n"
            "<code>پپه حجم ۳ برابر</code> — جهش حجم\n"
            "<code>بیت‌کوین ۸٪ از سقف</code> — تریلینگ\n"
            "<code>خرید 0.5 اتریوم به قیمت 2200</code> — ثبت دارایی\n"
            "<code>واچ سول</code> — افزودن به واچ‌لیست\n\n"
            "<b>دستورها:</b>\n"
            "/newalert /alerts /watch /portfolio /digest /premium /lang /admin\n\n"
            "هر هشدار یک‌بار مصرف است: یک بار فعال می‌شود و به تاریخچه می‌رود. "
            "قیمت‌ها: فید زنده بایننس (جفت‌های USDT)."
        ),
        "flow.hint_price": "🔢 قیمت هدف {sym} را بفرست (مثلاً <code>65000</code>):",
        "flow.hint_amount": "🔢 چند تا {sym}؟ (مثلاً <code>0.5</code>)",
        "flow.hint_buy": "🔢 قیمت خرید به دلار (یا دکمه <code>الان</code>):",
        "flow.cancelled": "❎ لغو شد.",
        "btn.above": "⬆️ بالاتر رفت از",
        "btn.below": "⬇️ پایین‌تر آمد از",
    },
}


def t_for(lang: str) -> dict[str, str]:
    return _STRINGS.get(lang, _STRINGS[CONFIG.default_lang])


def tr(lang: str, key: str, **kw) -> str:
    """Translate with {placeholders}."""
    tpl = t_for(lang).get(key, key)
    try:
        return tpl.format(**kw) if kw else tpl
    except (KeyError, IndexError):
        return tpl


def coin_line(market: MarketData, symbol: str, lang: str = "en") -> str:
    """One compact list line:  BTC  $97,432  ▲ 1.24%"""
    t = market.ticker(symbol)
    if t is None:
        return f"<b>{symbol}</b>  —"
    return f"<b>{symbol}</b>  <code>{market.fmt_price(t.price)}</code>  {market.fmt_pct(t.change_24h_pct)}"


def describe_draft(market: MarketData, lang: str, type_: str, symbol: str,
                   direction: str = "", target: float = 0.0, params_str: str = "") -> str:
    """Human description of a rule, e.g. 'BTC ⬆️ rises above $100,000'."""
    t = market.ticker(symbol)
    arrow = tr(lang, "btn.above") if direction == "ABOVE" else tr(lang, "btn.below") if direction else ""
    if type_ in ("PRICE_ABOVE", "PRICE_BELOW"):
        body = f"<b>{symbol}</b> {arrow} <code>{market.fmt_price(target)}</code>"
    else:
        body = f"<b>{symbol}</b> · <code>{params_str}</code>"
    extra = f"\n💵 Now: {market.fmt_price(t.price)}" if t else ""
    return f"{body}{extra}"


def fmt_alert_fired(alert: AlertRow, t: Ticker, reason: str, market: MarketData, lang: str) -> str:
    """The notification message when an alert triggers."""
    if lang == "fa":
        head = "🚨 <b>هشدار نوا</b>"
        line1 = f"<b>{alert.symbol}</b> الان <b>{market.fmt_price(t.price)}</b> است"
        stats = f"\n📊 ۲۴س: {market.fmt_pct(t.change_24h_pct)}   📈 سقف ۲۴س: {market.fmt_price(t.high_24h)}"
        why = f"\n🎯 دلیل: <i>{reason}</i>"
        tail = "\n\n<i>این هشدار یک‌بار مصرف بود و به تاریخچه رفت.</i>"
    else:
        head = "🚨 <b>Nova Alert</b>"
        line1 = f"<b>{alert.symbol}</b> is now <b>{market.fmt_price(t.price)}</b>"
        stats = f"\n📊 24h: {market.fmt_pct(t.change_24h_pct)}   📈 24h High: {market.fmt_price(t.high_24h)}"
        why = f"\n🎯 Rule: <i>{reason}</i>"
        tail = "\n\n<i>This one-shot alert moved to your history.</i>"
    return f"{head}\n{line1}{stats}{why}{tail}"


def fmt_digest(market: MarketData, lang: str, watch: list[str],
               pf_rows: list[tuple[str, float, float, float]],  # (sym, amount, buy, now)
               ) -> str:
    """Morning digest message."""
    date = market.utc_day()
    parts: list[str] = [tr(lang, "digest.header", date=date)]

    if watch:
        parts.append("⭐ <b>واچ‌لیست</b>" if lang == "fa" else "⭐ <b>Watchlist</b>")
        for sym in watch[:10]:
            parts.append("  " + coin_line(market, sym, lang))

    if pf_rows:
        total_now = sum(a * n for _, a, _, n in pf_rows)
        total_buy = sum(a * b for _, a, b, _ in pf_rows)
        pnl = total_now - total_buy
        pnl_pct = (pnl / total_buy * 100) if total_buy else 0.0
        if lang == "fa":
            parts.append(f"\n💼 <b>پورتفوی:</b> {market.fmt_price(total_now)} ({market.fmt_pct(pnl_pct)})")
        else:
            parts.append(f"\n💼 <b>Portfolio:</b> {market.fmt_price(total_now)} ({market.fmt_pct(pnl_pct)})")

    gainers, losers = market.top_movers(n=3)
    if gainers and losers:
        parts.append("\n🔥 <b>داغ‌ترین‌های ۲۴ ساعت</b>" if lang == "fa" else "\n🔥 <b>Top movers (24h)</b>")
        for t in gainers:
            parts.append("  " + coin_line(market, t.symbol, lang))
        parts.append("🧊 <b>سردترین‌ها</b>" if lang == "fa" else "🧊 <b>Bottom movers</b>")
        for t in losers:
            parts.append("  " + coin_line(market, t.symbol, lang))

    return "\n".join(parts)
