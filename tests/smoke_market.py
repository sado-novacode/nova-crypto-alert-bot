#!/usr/bin/env python3
"""Live smoke test for MarketData (no Telegram needed).

    python tests/smoke_market.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nova.market import MarketData  # noqa: E402


async def main() -> int:
    md = MarketData()
    await md.start()
    print("Waiting 8s for the live feed (WS first tick)…")
    await asyncio.sleep(8)

    ok = True
    btc = md.ticker("BTC")
    if btc and btc.price > 0:
        print(f"✓ BTC  {md.fmt_price(btc.price)}  24h {md.fmt_pct(btc.change_24h_pct)}  vol {btc.quote_vol_24h/1e9:.2f}B")
    else:
        print("✗ BTC price missing")
        ok = False

    eth = md.price("ETH")
    sol = md.price("SOL")
    print(f"✓ ETH {md.fmt_price(eth or 0)}   SOL {md.fmt_price(sol or 0)}" if eth and sol else "✗ ETH/SOL missing")
    ok = ok and bool(eth and sol)

    n = len(md.tickers)
    print(f"✓ {n} symbols cached" if n > 10 else f"✗ only {n} symbols cached")
    ok = ok and n > 10

    gainers, losers = md.top_movers(n=3)
    if gainers and losers:
        print("✓ top movers:",
              ", ".join(f"{t.symbol} {t.change_24h_pct:+.1f}%" for t in gainers),
              "| bottom:",
              ", ".join(f"{t.symbol} {t.change_24h_pct:+.1f}%" for t in losers))
    else:
        print("✗ movers unavailable")

    # simulate rapid-move lookups
    hist = md.price_minutes_ago("BTC", 0.2)
    print(f"✓ price history lookup (~12s ago): {hist}")

    await md.stop()
    print("\nMARKET SMOKE " + ("PASS ✅" if ok else "FAIL ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
