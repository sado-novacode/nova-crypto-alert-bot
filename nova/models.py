"""Typed models shared across Nova."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

# Alert rule types
PRICE_ABOVE = "PRICE_ABOVE"
PRICE_BELOW = "PRICE_BELOW"
PCT_UP_24H = "PCT_UP_24H"          # +X% in 24h
PCT_DOWN_24H = "PCT_DOWN_24H"      # -X% in 24h
PCT_UP_1H = "PCT_UP_1H"            # +X% in 1h
PCT_DOWN_1H = "PCT_DOWN_1H"        # -X% in 1h
VOLUME_SPIKE = "VOLUME_SPIKE"      # quote volume > mult x 30-min baseline
RAPID_DROP = "RAPID_DROP"          # -pct% within window_min minutes
RAPID_PUMP = "RAPID_PUMP"          # +pct% within window_min minutes
TRAILING_DOWN = "TRAILING_DOWN"    # price <= rolling_high * (1 - pct/100)

ALL_TYPES = {
    PRICE_ABOVE, PRICE_BELOW,
    PCT_UP_24H, PCT_DOWN_24H, PCT_UP_1H, PCT_DOWN_1H,
    VOLUME_SPIKE, RAPID_DROP, RAPID_PUMP, TRAILING_DOWN,
}

SMART_TYPES = ALL_TYPES - {PRICE_ABOVE, PRICE_BELOW}


@dataclass
class AlertDraft:
    """Result of parsing a user sentence — pending confirmation."""

    type: str
    symbol: str
    params: dict[str, Any] = field(default_factory=dict)
    direction: str = ""       # ABOVE | BELOW (price alerts only)
    target: float = 0.0       # price target (price alerts only)
    raw_text: str = ""

    def describe_params(self) -> str:
        """Human-readable short description of the rule parameters."""
        t = self.type
        if t in (PRICE_ABOVE, PRICE_BELOW):
            return f"{'≥' if t == PRICE_ABOVE else '≤'} {self.target:,.2f} USD"
        if t in (PCT_UP_24H, PCT_UP_1H):
            win = "24h" if t == PCT_UP_24H else "1h"
            return f"+{self.params.get('pct', 0):g}% / {win}"
        if t in (PCT_DOWN_24H, PCT_DOWN_1H):
            win = "24h" if t == PCT_DOWN_24H else "1h"
            return f"-{self.params.get('pct', 0):g}% / {win}"
        if t == VOLUME_SPIKE:
            return f"vol > {self.params.get('mult', 0):g}× avg"
        if t == RAPID_DROP:
            return f"-{self.params.get('pct', 0):g}% in {self.params.get('window_min', 0):g}min"
        if t == RAPID_PUMP:
            return f"+{self.params.get('pct', 0):g}% in {self.params.get('window_min', 0):g}min"
        if t == TRAILING_DOWN:
            return f"-{self.params.get('pct', 0):g}% from high"
        return json.dumps(self.params)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(raw: str) -> "AlertDraft":
        d = json.loads(raw)
        return AlertDraft(
            type=d["type"], symbol=d["symbol"], params=d.get("params") or {},
            direction=d.get("direction", ""), target=float(d.get("target") or 0),
            raw_text=d.get("raw_text", ""),
        )


@dataclass
class Ticker:
    """Live market snapshot for one symbol."""

    symbol: str
    price: float = 0.0
    open_24h: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    quote_vol_24h: float = 0.0
    updated: float = 0.0     # unix ts of last update

    @property
    def change_24h_pct(self) -> float:
        if self.open_24h > 0:
            return (self.price - self.open_24h) / self.open_24h * 100
        return 0.0
