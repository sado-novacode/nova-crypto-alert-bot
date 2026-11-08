"""Async SQLite data layer for Nova (aiosqlite).

Tables
------
users      : language, tier, premium expiry, digest hour
alerts     : one-shot alert rules (ACTIVE -> TRIGGERED)
holdings   : portfolio entries (amount + buy price)
codes      : premium activation codes
watchlist  : per-user symbol watchlist
"""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite

from .config import CONFIG

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id         INTEGER PRIMARY KEY,
    lang            TEXT NOT NULL DEFAULT 'fa',
    tier            TEXT NOT NULL DEFAULT 'FREE',
    premium_until   TEXT,
    digest_hour     INTEGER,
    digest_enabled  INTEGER NOT NULL DEFAULT 0,
    last_digest_on  TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id           TEXT PRIMARY KEY,
    user_id      INTEGER NOT NULL,
    type         TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    params_json  TEXT NOT NULL DEFAULT '{}',
    status       TEXT NOT NULL DEFAULT 'ACTIVE',
    source_text  TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    triggered_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_user  ON alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_state ON alerts(status);

CREATE TABLE IF NOT EXISTS holdings (
    id         TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    symbol     TEXT NOT NULL,
    amount     REAL NOT NULL,
    buy_price  REAL NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_holdings_user ON holdings(user_id);

CREATE TABLE IF NOT EXISTS codes (
    code      TEXT PRIMARY KEY,
    days      INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    used_by   INTEGER,
    used_at   TEXT
);

CREATE TABLE IF NOT EXISTS watchlist (
    user_id INTEGER NOT NULL,
    symbol  TEXT NOT NULL,
    PRIMARY KEY (user_id, symbol)
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


@dataclass
class UserRow:
    user_id: int
    lang: str
    tier: str
    premium_until: str | None
    digest_hour: int | None
    digest_enabled: int
    last_digest_on: str | None
    created_at: str = ""

    @property
    def is_premium(self) -> bool:
        if self.tier != "PREMIUM":
            return False
        if not self.premium_until:
            return True  # lifetime
        try:
            return datetime.fromisoformat(self.premium_until) > datetime.now(timezone.utc)
        except ValueError:
            return False


@dataclass
class AlertRow:
    id: str
    user_id: int
    type: str
    symbol: str
    params_json: str
    status: str
    source_text: str
    created_at: str
    triggered_at: str | None

    def params(self) -> dict[str, Any]:
        import json
        try:
            return json.loads(self.params_json or "{}")
        except json.JSONDecodeError:
            return {}

    def short_desc(self) -> str:
        """Compact description for non-price alert types."""
        p = self.params()
        t = self.type
        if t in ("PCT_UP_24H", "PCT_DOWN_24H"):
            sign = "+" if t == "PCT_UP_24H" else "-"
            return f"{sign}{p.get('pct', 0):g}% / 24h"
        if t in ("PCT_UP_1H", "PCT_DOWN_1H"):
            sign = "+" if t == "PCT_UP_1H" else "-"
            return f"{sign}{p.get('pct', 0):g}% / 1h"
        if t == "VOLUME_SPIKE":
            return f"vol > {p.get('mult', 0):g}× avg"
        if t == "RAPID_DROP":
            return f"-{p.get('pct', 0):g}% in {p.get('window_min', 0):g}min"
        if t == "RAPID_PUMP":
            return f"+{p.get('pct', 0):g}% in {p.get('window_min', 0):g}min"
        if t == "TRAILING_DOWN":
            return f"-{p.get('pct', 0):g}% from high"
        return t


@dataclass
class HoldingRow:
    id: str
    user_id: int
    symbol: str
    amount: float
    buy_price: float
    created_at: str


class Database:
    def __init__(self, path: str = CONFIG.database_path) -> None:
        self.path = path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    # ------------------------------------------------------------- users

    async def get_user(self, user_id: int) -> UserRow | None:
        assert self._db
        cur = await self._db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return UserRow(**dict(row)) if row else None

    async def ensure_user(self, user_id: int, lang: str) -> UserRow:
        """Create the user on first contact; return the row."""
        assert self._db
        user = await self.get_user(user_id)
        if user:
            return user
        await self._db.execute(
            "INSERT OR IGNORE INTO users(user_id, lang, created_at) VALUES(?,?,?)",
            (user_id, lang, now_iso()),
        )
        await self._db.commit()
        return (await self.get_user(user_id))  # type: ignore[return-value]

    async def set_lang(self, user_id: int, lang: str) -> None:
        assert self._db
        await self._db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
        await self._db.commit()

    async def set_premium(self, user_id: int, until: str | None) -> None:
        assert self._db
        tier = "PREMIUM" if until is not None else "FREE"
        await self._db.execute(
            "UPDATE users SET tier=?, premium_until=? WHERE user_id=?", (tier, until, user_id)
        )
        await self._db.commit()

    async def set_digest(self, user_id: int, enabled: bool, hour: int | None = None) -> None:
        assert self._db
        await self._db.execute(
            "UPDATE users SET digest_enabled=?, digest_hour=COALESCE(?, digest_hour) WHERE user_id=?",
            (1 if enabled else 0, hour, user_id),
        )
        await self._db.commit()

    async def mark_digest_sent(self, user_id: int, day: str) -> None:
        assert self._db
        await self._db.execute("UPDATE users SET last_digest_on=? WHERE user_id=?", (day, user_id))
        await self._db.commit()

    async def digest_users(self) -> list[UserRow]:
        assert self._db
        cur = await self._db.execute("SELECT * FROM users WHERE digest_enabled=1")
        return [UserRow(**dict(r)) for r in await cur.fetchall()]

    # ------------------------------------------------------------ alerts

    async def create_alert(
        self, user_id: int, a_type: str, symbol: str, params: dict[str, Any], source: str = ""
    ) -> AlertRow:
        assert self._db
        row = AlertRow(
            id=new_id("al"), user_id=user_id, type=a_type, symbol=symbol.upper(),
            params_json=_dumps(params), status="ACTIVE", source_text=source[:200],
            created_at=now_iso(), triggered_at=None,
        )
        await self._db.execute(
            "INSERT INTO alerts(id,user_id,type,symbol,params_json,status,source_text,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (row.id, row.user_id, row.type, row.symbol, row.params_json, row.status,
             row.source_text, row.created_at),
        )
        await self._db.commit()
        return row

    async def alerts_by_status(self, status: str = "ACTIVE", user_id: int | None = None) -> list[AlertRow]:
        assert self._db
        if user_id is None:
            cur = await self._db.execute("SELECT * FROM alerts WHERE status=? ORDER BY created_at", (status,))
        else:
            cur = await self._db.execute(
                "SELECT * FROM alerts WHERE status=? AND user_id=? ORDER BY created_at DESC",
                (status, user_id),
            )
        return [AlertRow(**dict(r)) for r in await cur.fetchall()]

    async def count_active(self, user_id: int) -> int:
        assert self._db
        cur = await self._db.execute(
            "SELECT COUNT(*) AS c FROM alerts WHERE user_id=? AND status='ACTIVE'", (user_id,)
        )
        return int((await cur.fetchone())["c"])  # type: ignore[index]

    async def trigger_alert(self, alert_id: str) -> None:
        assert self._db
        await self._db.execute(
            "UPDATE alerts SET status='TRIGGERED', triggered_at=? WHERE id=?", (now_iso(), alert_id)
        )
        await self._db.commit()

    async def update_alert_params(self, alert_id: str, params: dict[str, Any]) -> None:
        assert self._db
        await self._db.execute(
            "UPDATE alerts SET params_json=? WHERE id=?", (_dumps(params), alert_id)
        )
        await self._db.commit()

    async def delete_alert(self, alert_id: str, user_id: int | None = None) -> bool:
        assert self._db
        if user_id is None:
            cur = await self._db.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
        else:
            cur = await self._db.execute("DELETE FROM alerts WHERE id=? AND user_id=?", (alert_id, user_id))
        await self._db.commit()
        return cur.rowcount > 0

    async def clear_history(self, user_id: int) -> int:
        assert self._db
        cur = await self._db.execute("DELETE FROM alerts WHERE user_id=? AND status='TRIGGERED'", (user_id,))
        await self._db.commit()
        return cur.rowcount

    # ---------------------------------------------------------- holdings

    async def add_holding(self, user_id: int, symbol: str, amount: float, buy_price: float) -> HoldingRow:
        assert self._db
        row = HoldingRow(
            id=new_id("hf"), user_id=user_id, symbol=symbol.upper(),
            amount=amount, buy_price=buy_price, created_at=now_iso(),
        )
        await self._db.execute(
            "INSERT INTO holdings(id,user_id,symbol,amount,buy_price,created_at) VALUES(?,?,?,?,?,?)",
            (row.id, row.user_id, row.symbol, row.amount, row.buy_price, row.created_at),
        )
        await self._db.commit()
        return row

    async def holdings(self, user_id: int) -> list[HoldingRow]:
        assert self._db
        cur = await self._db.execute(
            "SELECT * FROM holdings WHERE user_id=? ORDER BY created_at", (user_id,)
        )
        return [HoldingRow(**dict(r)) for r in await cur.fetchall()]

    async def delete_holding(self, holding_id: str, user_id: int) -> bool:
        assert self._db
        cur = await self._db.execute("DELETE FROM holdings WHERE id=? AND user_id=?", (holding_id, user_id))
        await self._db.commit()
        return cur.rowcount > 0

    async def count_holdings(self, user_id: int) -> int:
        assert self._db
        cur = await self._db.execute("SELECT COUNT(*) AS c FROM holdings WHERE user_id=?", (user_id,))
        return int((await cur.fetchone())["c"])  # type: ignore[index]

    # ------------------------------------------------------------- codes

    async def gen_codes(self, n: int, days: int) -> list[str]:
        assert self._db
        codes: list[str] = []
        for _ in range(n):
            code = f"NOVA-{secrets.token_hex(4).upper()}"
            await self._db.execute(
                "INSERT INTO codes(code,days,created_at) VALUES(?,?,?)", (code, days, now_iso())
            )
            codes.append(code)
        await self._db.commit()
        return codes

    async def redeem_code(self, code: str, user_id: int) -> int | None:
        """Atomically: mark code used + extend the user's premium. Returns days or None."""
        assert self._db
        cur = await self._db.execute(
            "SELECT * FROM codes WHERE code=? AND used_by IS NULL", (code.strip().upper(),)
        )
        row = await cur.fetchone()
        if not row:
            return None
        days = int(row["days"])

        user = await self.get_user(user_id)
        base = datetime.now(timezone.utc)
        if user and user.premium_until:
            try:
                prev = datetime.fromisoformat(user.premium_until)
                if prev > base:
                    base = prev
            except ValueError:
                pass
        until = (base + timedelta(days=days)).isoformat(timespec="seconds")

        await self._db.execute(
            "UPDATE codes SET used_by=?, used_at=? WHERE code=?", (user_id, now_iso(), row["code"])
        )
        await self._db.execute(
            "UPDATE users SET tier='PREMIUM', premium_until=? WHERE user_id=?", (until, user_id)
        )
        await self._db.commit()
        return days

    # --------------------------------------------------------- watchlist

    async def watchlist(self, user_id: int) -> list[str]:
        assert self._db
        cur = await self._db.execute(
            "SELECT symbol FROM watchlist WHERE user_id=? ORDER BY symbol", (user_id,)
        )
        return [r["symbol"] for r in await cur.fetchall()]

    async def watch_add(self, user_id: int, symbol: str) -> bool:
        assert self._db
        try:
            await self._db.execute(
                "INSERT INTO watchlist(user_id,symbol) VALUES(?,?)", (user_id, symbol.upper())
            )
            await self._db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    async def watch_remove(self, user_id: int, symbol: str) -> bool:
        assert self._db
        cur = await self._db.execute(
            "DELETE FROM watchlist WHERE user_id=? AND symbol=?", (user_id, symbol.upper())
        )
        await self._db.commit()
        return cur.rowcount > 0

    # -------------------------------------------------------------- stats

    async def stats(self) -> dict[str, int]:
        assert self._db
        out: dict[str, int] = {}
        for label, sql in (
            ("users", "SELECT COUNT(*) c FROM users"),
            ("premium", "SELECT COUNT(*) c FROM users WHERE tier='PREMIUM'"),
            ("alerts_active", "SELECT COUNT(*) c FROM alerts WHERE status='ACTIVE'"),
            ("alerts_fired", "SELECT COUNT(*) c FROM alerts WHERE status='TRIGGERED'"),
            ("holdings", "SELECT COUNT(*) c FROM holdings"),
        ):
            cur = await self._db.execute(sql)
            out[label] = int((await cur.fetchone())["c"])  # type: ignore[index]
        return out


def _dumps(d: dict[str, Any]) -> str:
    import json
    return json.dumps(d, ensure_ascii=False)
