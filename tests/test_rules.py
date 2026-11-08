"""Rule engine tests — pure functions, no IO.  Run: python -m tests.test_rules"""

import sys
sys.path.insert(0, ".")

from nova.models import Ticker, PRICE_ABOVE, PRICE_BELOW, PCT_UP_24H, PCT_DOWN_24H  # noqa: E402
from nova.rules import (  # noqa: E402
    eval_price, eval_pct_change, eval_pct_change_history,
    eval_rapid_move, eval_trailing, eval_volume_spike,
)
from nova.models import RAPID_DROP, RAPID_PUMP  # noqa: E402


def ticker(price: float, open_24h: float = 100.0) -> Ticker:
    return Ticker(symbol="TEST", price=price, open_24h=open_24h,
                  high_24h=max(price, open_24h), low_24h=min(price, open_24h),
                  quote_vol_24h=1e9, updated=0.0)


def run() -> int:
    failures = 0

    def check(name: str, got: bool, want: bool) -> None:
        nonlocal failures
        mark = "✓" if got == want else "✗"
        if got != want:
            failures += 1
        print(f"{mark} {name}: got {got}, want {want}")

    t = ticker(100_050, 100_000)
    check("price above fires", eval_price(PRICE_ABOVE, 100_000, t), True)
    check("price above not yet", eval_price(PRICE_ABOVE, 100_100, t), False)
    check("price below fires", eval_price(PRICE_BELOW, 100_100, t), True)

    up = ticker(112, 100)
    check("24h +12% up alert", eval_pct_change(PCT_UP_24H, 10, up), True)
    check("24h +12% down alert", eval_pct_change(PCT_DOWN_24H, 10, up), False)

    check("1h history drop", eval_pct_change_history("PCT_DOWN_1H", 5, 94, 100), True)
    check("rapid drop 5% in 15m", eval_rapid_move(RAPID_DROP, 5, 15, 94.9, 100), True)
    check("rapid pump", eval_rapid_move(RAPID_PUMP, 5, 15, 105.1, 100), True)
    check("rapid no move", eval_rapid_move(RAPID_DROP, 5, 15, 99, 100), False)

    check("trailing from high", eval_trailing(8, 100, 91.9), True)
    check("trailing not yet", eval_trailing(8, 100, 95), False)

    check("volume spike 3x", eval_volume_spike(3, 300_000, 90_000), True)
    check("volume no spike", eval_volume_spike(3, 100_000, 90_000), False)
    check("volume illiquid ignored", eval_volume_spike(3, 5_000, 1_000), False)

    print(f"\n{'ALL PASS ✅' if failures == 0 else f'{failures} FAILURES ❌'}")
    return failures


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
