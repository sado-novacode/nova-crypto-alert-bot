"""Nova's natural-language alert parser — the signature feature.

Turns free text (Persian or English, Persian or Latin digits) into an
`AlertDraft`. Runs 100% offline with regexes — no external NLP API needed.

Examples it understands
-----------------------
  "بیت‌کوین بالای ۱۰۰ هزار دلار خبرم کن"
  "eth زیر 1800"
  "sui اگه ۵٪ تو یه ساعت افت کرد"
  "bitcoin +10% in 24h"
  "sol از سقف ۸ درصد پایین بیاد"
  "volume of pepe 3x"
  "pepe حجم ۳ برابر شد"
  "btc upper 100k"
"""

from __future__ import annotations

import re

from .models import (
    PCT_DOWN_1H, PCT_DOWN_24H, PCT_UP_1H, PCT_UP_24H,
    RAPID_DROP, RAPID_PUMP, TRAILING_DOWN, VOLUME_SPIKE,
    PRICE_ABOVE, PRICE_BELOW, AlertDraft,
)

# --------------------------------------------------------------------------- #
# Digits & numbers
# --------------------------------------------------------------------------- #

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# coin names -> Binance symbol (checked case-insensitively, spaces normalized)
COIN_ALIASES: dict[str, str] = {
    # English
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH", "ether": "ETH",
    "tether": "USDT", "usdt": "USDT",
    "binance coin": "BNB", "binancecoin": "BNB", "bnb": "BNB",
    "solana": "SOL", "sol": "SOL",
    "ripple": "XRP", "xrp": "XRP",
    "dogecoin": "DOGE", "doge": "DOGE",
    "cardano": "ADA", "ada": "ADA",
    "shiba": "SHIB", "shib": "SHIB",
    "tron": "TRX", "trx": "TRX",
    "chainlink": "LINK", "link": "LINK",
    "avalanche": "AVAX", "avax": "AVAX",
    "polkadot": "DOT", "dot": "DOT",
    "litecoin": "LTC", "ltc": "LTC",
    "polygon": "POL", "matic": "POL",
    "sui": "SUI", "pepe": "PEPE", "toncoin": "TON", "ton": "TON",
    "near protocol": "NEAR", "near": "NEAR",
    "arbitrum": "ARB", "arb": "ARB",
    "optimism": "OP", "uniswap": "UNI", "uni": "UNI",
    "aptos": "APT", "cosmos": "ATOM", "atom": "ATOM",
    "stellar": "XLM", "xlm": "XLM",
    "monero": "XMR", "xmr": "XMR",
    "filecoin": "FIL", "fil": "FIL",
    # Persian
    "بیت کوین": "BTC", "بیتکوین": "BTC", "بی تی سی": "BTC",
    "اتریوم": "ETH", "اتریوم کلاسیک": "ETC", "ای تی سی": "ETC",
    "تتر": "USDT", "تدر": "USDT",
    "بایننس کوین": "BNB", "بی ان بی": "BNB", "بایننس": "BNB",
    "سولانا": "SOL", "سول": "SOL",
    "ریپل": "XRP", "ریپل کوین": "XRP",
    "دوج": "DOGE", "دوج کوین": "DOGE", "دوجکوین": "DOGE",
    "کاردانو": "ADA", "شیبا": "SHIB", "شیبا اینو": "SHIB",
    "ترون": "TRX", "چین لینک": "LINK", "لینک": "LINK",
    "آوالانچ": "AVAX", "اوالانچ": "AVAX", "پولکادات": "DOT",
    "لایتکوین": "LTC", "پالیگان": "POL", "پولیگان": "POL", "ماتیک": "POL",
    "سویی": "SUI", "پپه": "PEPE", "پپی": "PEPE", "تون": "TON",
    "آربیتروم": "ARB", "اپتیمیزم": "OP", "یونی سواپ": "UNI",
    "کازموس": "ATOM", "استلار": "XLM", "مونرو": "XMR", "فایلکوین": "FIL",
}

_UNIT_MULT = {
    "هزار": 1_000, "میلیون": 1_000_000, "میلیارد": 1_000_000_000,
    "k": 1_000, "kh": 1_000, "m": 1_000_000, "mil": 1_000_000,
    "b": 1_000_000_000, "t": 1_000_000_000_000, "x": 1,
}

_ABOVE_WORDS = [
    "بالاتر", "بالای", "بیشتر از", "بیاتر", "باغای", "روبه بالا", "عبور کرد از", "بزنه بالا",
    "above", "over", "higher", "greater", "more than", "cross above", "reaches", "hits", "goes above",
]
_BELOW_WORDS = [
    "پایین", "زیر", "کمتر از", "پایین‌تر", "پایینتر", "بره زیر", "بیفته زیر", "ریزید",
    "below", "under", "lower", "less than", "cross below", "drops to", "falls to", "goes below",
]
_DROP_WORDS = ["افت کرد", "افتاد", "ریخت", "ریزی", "کاهش", "پایین اومد", "پایین بیاد", "drop", "fall", "falls", "dump", "lose", "lost", "down"]
_PUMP_WORDS = ["بالا رفت", "بالاتر رفت", "رشد کرد", "رشد", "پامپ", "جوش خورد", "rise", "rise up", "pump", "gain", "gains", "up"]
_TRAILING_WORDS = ["از سقف", "از بالاترین", "از سقفش", "from high", "from its high", "off the high", "from the top"]
_VOLUME_WORDS = ["حجم", "volume", "vol"]


def normalize(text: str) -> str:
    """Lowercase, unify Persian digits, collapse whitespace/zero-width chars."""
    text = text.translate(_DIGIT_MAP)
    text = text.replace("‌", " ").replace("‍", " ")  # ZWNJ -> space
    text = text.replace("٪", "%")                      # Arabic percent sign
    text = text.replace("−", "-").replace("–", "-")    # unicode minus
    text = re.sub(r"[٬,،]", "", text)                 # thousands separators
    text = text.replace("٫", ".")                      # Persian decimal point
    text = re.sub(r"\s+", " ", text.strip().lower())
    return text


def _find_symbol(text: str) -> str | None:
    # longest alias first so "binance coin" wins over "coin"
    best: tuple[int, str] | None = None
    for alias, sym in COIN_ALIASES.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text):
            if best is None or len(alias) > best[0]:
                best = (len(alias), sym)
    return best[1] if best else None


def _extract_number(text: str) -> float | None:
    """First number in the text, honoring k/m/b/x + هزار/میلیون/میلیارد suffixes."""
    m = re.search(r"(\d+(?:\.\d+)?)(?:\s*(هزار|میلیون|میلیارد|k|kh|m|mil|b|t|x)\b)?", text)
    if not m:
        return None
    value = float(m.group(1))
    mult = _UNIT_MULT.get(m.group(2) or "", 1)
    return value * mult


def _extract_percent(text: str) -> tuple[float, int] | None:
    """First percentage-looking number with its explicit sign.

    Returns (pct, sign) where sign is -1 / 0 / +1 (0 = no sign written).
    e.g.  5% -> (5, 0)   -5% -> (5, -1)   +10% -> (10, +1)
    """
    m = re.search(r"([+\-])?\s*(\d+(?:\.\d+)?)\s*(?:%|درصد|percent|pct)", text)
    if not m:
        return None
    sign = 0
    if m.group(1) == "-":
        sign = -1
    elif m.group(1) == "+":
        sign = 1
    return float(m.group(2)), sign


_FA_HOURS = (("نیم ساعت", 0.5), ("یه ساعت", 1), ("یک ساعت", 1),
             ("دو ساعت", 2), ("سه ساعت", 3), ("چهار ساعت", 4), ("پنج ساعت", 5))


def _extract_minutes(text: str) -> float | None:
    for phrase, hours in _FA_HOURS:
        if phrase in text:
            return hours * 60
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:دقیقه|minutes?|mins?|min|مینوت|m\b)", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:ساعت|hours?|hr|h\b)", text)
    if m:
        return float(m.group(1)) * 60
    return None


def _has_any(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def parse_alert(text: str) -> AlertDraft | None:
    """Parse free text into an AlertDraft; None when nothing sensible found."""
    raw = text.strip()
    text = normalize(raw)
    if not text or text.startswith("/"):
        return None

    symbol = _find_symbol(text)
    if not symbol:
        return None

    # ---------------------------------------------------- smart patterns

    # 1) trailing from high
    if _has_any(text, _TRAILING_WORDS):
        ps = _extract_percent(text)
        pct = ps[0] if ps else _extract_number(text)
        if pct and 0 < pct <= 90:
            return AlertDraft(TRAILING_DOWN, symbol, {"pct": pct}, raw_text=raw)

    # 2) volume spike
    if _has_any(text, _VOLUME_WORDS):
        mult = _extract_number(text)
        if mult and 1.1 <= mult <= 100:
            return AlertDraft(VOLUME_SPIKE, symbol, {"mult": mult}, raw_text=raw)

    # 3) rapid / windowed percent move
    pct_signed = _extract_percent(text)
    if pct_signed:
        pct, sign = pct_signed
        minutes = _extract_minutes(text)
        wants_pump = sign > 0 or (sign == 0 and _has_any(text, _PUMP_WORDS))
        wants_drop = sign < 0 or (sign == 0 and _has_any(text, _DROP_WORDS))
        if wants_pump or wants_drop:
            if minutes is not None and minutes < 24 * 60:
                a_type = RAPID_PUMP if wants_pump else RAPID_DROP
                return AlertDraft(a_type, symbol, {"pct": pct, "window_min": minutes}, raw_text=raw)
            if _looks_like_24h(text):
                a_type = PCT_UP_24H if wants_pump else PCT_DOWN_24H
                return AlertDraft(a_type, symbol, {"pct": pct}, raw_text=raw)
            a_type = PCT_UP_1H if wants_pump else PCT_DOWN_1H
            return AlertDraft(a_type, symbol, {"pct": pct}, raw_text=raw)

    # 4) classic price target
    number = _extract_number(text)
    if number and number > 0:
        is_below = _has_any(text, _BELOW_WORDS)
        a_type = PRICE_BELOW if is_below else PRICE_ABOVE
        return AlertDraft(a_type, symbol, {}, direction="BELOW" if is_below else "ABOVE",
                          target=number, raw_text=raw)

    return None


def _looks_like_24h(text: str) -> bool:
    return bool(re.search(r"24\s*(?:h|hour|ساعت)|روزانه|daily|در روز", text))


def valid_symbol(symbol: str) -> bool:
    """A sanity whitelist is NOT enforced — Binance simply has no such pair."""
    return bool(re.fullmatch(r"[A-Z0-9]{2,10}", symbol))
