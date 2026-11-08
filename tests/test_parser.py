"""Parser tests — run with:  python -m tests.test_parser  (or pytest)"""

import sys
sys.path.insert(0, ".")

from nova.models import (  # noqa: E402
    PRICE_ABOVE, PRICE_BELOW, PCT_DOWN_1H, PCT_UP_24H,
    RAPID_DROP, TRAILING_DOWN, VOLUME_SPIKE,
)
from nova.parser import parse_alert, normalize  # noqa: E402

CASES = [
    # (input, expected_type, expected_symbol, extra checks)
    ("btc above 100000", PRICE_ABOVE, "BTC", {"target": 100000}),
    ("BTC Upper 100,000", PRICE_ABOVE, "BTC", {"target": 100000}),
    ("eth below 1800", PRICE_BELOW, "ETH", {"target": 1800}),
    ("بیت‌کوین بالای ۱۰۰ هزار دلار خبرم کن", PRICE_ABOVE, "BTC", {"target": 100000}),
    ("اتریوم زیر 1800", PRICE_BELOW, "ETH", {"target": 1800}),
    ("سولانا اگر زیر 90 رفت خبرم کن", PRICE_BELOW, "SOL", {"target": 90}),
    ("btc above 100k", PRICE_ABOVE, "BTC", {"target": 100000}),
    ("eth below 1.5m", PRICE_BELOW, "ETH", {"target": 1500000}),
    ("solana -5% in 15 minutes", RAPID_DROP, "SOL", {"pct": 5, "window_min": 15}),
    ("سولانا ۵٪ تو یه ساعت افت کرد", RAPID_DROP, "SOL", {"pct": 5, "window_min": 60}),
    ("bitcoin +10% in 24h", PCT_UP_24H, "BTC", {"pct": 10}),
    ("btc -8% from high", TRAILING_DOWN, "BTC", {"pct": 8}),
    ("بیت‌کوین ۸ درصد از سقف", TRAILING_DOWN, "BTC", {"pct": 8}),
    ("pepe volume 3x", VOLUME_SPIKE, "PEPE", {"mult": 3}),
    ("پپه حجم ۳ برابر شد", VOLUME_SPIKE, "PEPE", {"mult": 3}),
    ("doge 5% drop in 30 minutes", RAPID_DROP, "DOGE", {"pct": 5, "window_min": 30}),
]

NEGATIVE = ["", "/start", "hello there", "سلام خوبی؟", "چه خبر"]


def run() -> int:
    failures = 0
    for text, etype, esym, extra in CASES:
        draft = parse_alert(text)
        if draft is None:
            print(f"✗ parse failed: {text!r}")
            failures += 1
            continue
        ok = draft.type == etype and draft.symbol == esym
        for k, v in extra.items():
            got = draft.target if k == "target" else draft.params.get(k)
            if got != v:
                ok = False
                print(f"   field {k}: expected {v}, got {got}")
        if ok:
            print(f"✓ {text!r} -> {draft.type} {draft.symbol} {draft.describe_params()}")
        else:
            print(f"✗ {text!r} -> got {draft.type} {draft.symbol} {draft.describe_params()}")
            failures += 1

    for text in NEGATIVE:
        if parse_alert(text) is not None:
            print(f"✗ should NOT parse: {text!r}")
            failures += 1
        else:
            print(f"✓ correctly rejected: {text!r}")

    # normalize sanity
    assert normalize("۱٬۰۰۰٫۵") == "1000.5", normalize("۱٬۰۰۰٫۵")
    print("✓ Persian digits/separators normalize")
    print(f"\n{'ALL PASS ✅' if failures == 0 else f'{failures} FAILURES ❌'}")
    return failures


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
