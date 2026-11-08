"""Live market data for Nova.

Primary feed : Binance WebSocket `!miniTicker@arr` (all symbols, ~1s batches).
Fallback     : REST `/api/v3/ticker/24hr` polling when WS is stale.

Also maintains per-symbol ring buffers used by the smart alerts:
  * price snapshots (for RAPID_DROP / RAPID_PUMP windows)
  * per-minute quote-volume buckets (for VOLUME_SPIKE baseline)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import time
from collections import deque
from datetime import datetime, timezone

import aiohttp
import websockets

from .config import CONFIG
from .models import Ticker

log = logging.getLogger("nova.market")

TOP_COINS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "USDC", "DOGE", "TRX", "ADA", "LINK",
    "AVAX", "SHIB", "DOT", "LTC", "BCH", "UNI", "NEAR", "APT", "ICP", "ETC",
    "XLM", "FIL", "ATOM", "HBAR", "ARB", "OP", "VET", "INJ", "SUI", "PEPE",
    "TIA", "POL", "ALGO", "AAVE", "RENDER", "JUP", "STX", "SEI", "RUNE",
]

HISTORY_MAX = 1500  # ~25 min of 10s snapshots


class MarketData:
    """Async singleton holding live tickers + short history buffers."""

    def __init__(self) -> None:
        self.tickers: dict[str, Ticker] = {}
        self.price_history: dict[str, deque[tuple[float, float]]] = {}     # (ts, price)
        self.minute_vols: dict[str, deque[tuple[int, float]]] = {}         # (minute_ts, quote_vol)
        self._last_qvol: dict[str, float] = {}
        self._last_minute: dict[str, int] = {}
        self.ws_connected: bool = False
        self.last_tick: float = 0.0
        self._tasks: list[asyncio.Task[None]] = []
        self._session: aiohttp.ClientSession | None = None
        self._stop = asyncio.Event()

    # ------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12))
        self._tasks = [
            asyncio.create_task(self._ws_loop(), name="ws"),
            asyncio.create_task(self._rest_fallback_loop(), name="rest"),
        ]
        # seed immediately so the bot is usable before the first WS tick
        with contextlib.suppress(Exception):
            await self._rest_poll()

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        if self._session:
            await self._session.close()

    # ------------------------------------------------------------ accessors

    def price(self, symbol: str) -> float | None:
        t = self.tickers.get(symbol.upper())
        return t.price if t else None

    def ticker(self, symbol: str) -> Ticker | None:
        return self.tickers.get(symbol.upper())

    def is_live(self) -> bool:
        return (time.time() - self.last_tick) < CONFIG.stale_after

    def history(self, symbol: str) -> list[tuple[float, float]]:
        return list(self.price_history.get(symbol.upper(), ()))

    def price_minutes_ago(self, symbol: str, minutes: float) -> float | None:
        hist = self.price_history.get(symbol.upper())
        if not hist:
            return None
        cutoff = time.time() - minutes * 60
        older = [p for ts, p in hist if ts <= cutoff]
        return older[-1] if older else (hist[0][1] if hist else None)

    def minute_volume_baseline(self, symbol: str, minutes: int = 30) -> float | None:
        buckets = self.minute_vols.get(symbol.upper())
        if not buckets or len(buckets) < 5:
            return None
        recent = [v for _, v in list(buckets)[-minutes:]]
        vals = [v for v in recent if v > 0]
        return (sum(vals) / len(vals)) if vals else None

    def last_minute_volume(self, symbol: str) -> float | None:
        buckets = self.minute_vols.get(symbol.upper())
        return buckets[-1][1] if buckets else None

    def top_movers(self, universe: list[str] | None = None, n: int = 5) -> tuple[list[Ticker], list[Ticker]]:
        pool = [self.tickers[s] for s in (universe or TOP_COINS) if s in self.tickers]
        ranked = sorted((t for t in pool if t.quote_vol_24h > 1_000_000),
                        key=lambda t: t.change_24h_pct, reverse=True)
        return ranked[:n], ranked[-n:][::-1]

    # ------------------------------------------------------------ ingestion

    def _ingest(self, symbol: str, price: float, open_24h: float,
                high_24h: float, low_24h: float, quote_vol: float, ts: float | None = None) -> None:
        symbol = symbol.upper()
        now = ts or time.time()
        self.tickers[symbol] = Ticker(
            symbol=symbol, price=price, open_24h=open_24h, high_24h=high_24h,
            low_24h=low_24h, quote_vol_24h=quote_vol, updated=now,
        )
        self.last_tick = now

        # price ring buffer (sampled ~ every 10s)
        hist = self.price_history.setdefault(symbol, deque(maxlen=HISTORY_MAX))
        if not hist or now - hist[-1][0] >= 9:
            hist.append((now, price))

        # per-minute quote volume buckets from the cumulative 24h counter
        last = self._last_qvol.get(symbol)
        minute = int(now // 60)
        if last is not None and quote_vol >= last:
            delta = quote_vol - last
            buckets = self.minute_vols.setdefault(symbol, deque(maxlen=120))
            if minute != self._last_minute.get(symbol):
                buckets.append((minute, delta))
                self._last_minute[symbol] = minute
            else:
                if buckets:
                    prev_minute, prev_vol = buckets[-1]
                    buckets[-1] = (prev_minute, prev_vol + delta)
        self._last_qvol[symbol] = quote_vol

    # ------------------------------------------------------------ WS loop

    async def _ws_loop(self) -> None:
        backoff = 2
        while not self._stop.is_set():
            try:
                async with websockets.connect(CONFIG.ws_url, ping_interval=20, close_timeout=5) as ws:
                    log.info("Binance WS connected")
                    self.ws_connected = True
                    backoff = 2
                    async for raw in ws:
                        if self._stop.is_set():
                            return
                        try:
                            batch = json.loads(raw)
                            for t in batch:
                                try:
                                    self._ingest(
                                        symbol=t["s"][:-4] if t["s"].endswith("USDT") else t["s"],
                                        price=float(t["c"]), open_24h=float(t["o"]),
                                        high_24h=float(t["h"]), low_24h=float(t["l"]),
                                        quote_vol=float(t["q"]),
                                    )
                                except (KeyError, ValueError):
                                    continue
                        except json.JSONDecodeError:
                            continue
            except asyncio.CancelledError:
                return
            except Exception as exc:  # noqa: BLE001
                self.ws_connected = False
                log.warning("WS error (%s) — retrying in %ss", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    # ------------------------------------------------------------ REST fallback

    async def _rest_fallback_loop(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(10)
            if not self.is_live():
                log.info("WS data stale — using REST fallback")
                with contextlib.suppress(Exception):
                    await self._rest_poll()

    async def _rest_poll(self) -> None:
        """Poll REST in chunks so one stale/delisted symbol can't kill the batch."""
        assert self._session
        now = time.time()
        for i in range(0, len(TOP_COINS), 10):
            chunk = TOP_COINS[i:i + 10]
            symbols = json.dumps([f"{s}USDT" for s in chunk], separators=(",", ":"))
            try:
                async with self._session.get(
                    f"{CONFIG.rest_base}/ticker/24hr", params={"symbols": symbols}
                ) as resp:
                    if resp.status != 200:
                        log.warning("REST chunk failed: HTTP %s", resp.status)
                        continue
                    data = await resp.json()
            except Exception:  # noqa: BLE001
                log.warning("REST chunk network error", exc_info=True)
                continue
            for t in data:
                try:
                    self._ingest(
                        symbol=t["symbol"][:-4], price=float(t["lastPrice"]),
                        open_24h=float(t["openPrice"]), high_24h=float(t["highPrice"]),
                        low_24h=float(t["lowPrice"]), quote_vol=float(t["quoteVolume"]), ts=now,
                    )
                except (KeyError, ValueError):
                    continue

    # ------------------------------------------------------------ helpers

    async def fetch_price_rest(self, symbol: str) -> float | None:
        assert self._session
        try:
            async with self._session.get(f"{CONFIG.rest_base}/ticker/price",
                                         params={"symbol": f"{symbol.upper()}USDT"}) as resp:
                if resp.status != 200:
                    return None
                return float((await resp.json())["price"])
        except Exception:  # noqa: BLE001
            return None

    def fmt_price(self, price: float) -> str:
        if price >= 1000:
            return f"${price:,.0f}"
        if price >= 1:
            return f"${price:,.2f}"
        if price >= 0.01:
            return f"${price:.4f}"
        return f"${price:.8f}".rstrip("0").rstrip("0") + "0"

    def fmt_pct(self, pct: float) -> str:
        arrow = "▲" if pct >= 0 else "▼"
        return f"{arrow} {abs(pct):,.2f}%"

    def utc_day(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def sane_number(self, value: float) -> bool:
        return math.isfinite(value) and value > 0
