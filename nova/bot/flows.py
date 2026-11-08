"""Per-user guided-flow state (in-memory; flows are short-lived)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Flow:
    kind: str                       # "alert_confirm" | "alert_price" | "pf_amount" | "pf_buy" | "watch_add" | "premium_code"
    data: dict[str, Any] = field(default_factory=dict)


class FlowStore:
    def __init__(self) -> None:
        self._by_user: dict[int, Flow] = {}

    def start(self, user_id: int, kind: str, **data: Any) -> Flow:
        flow = Flow(kind=kind, data=data)
        self._by_user[user_id] = flow
        return flow

    def get(self, user_id: int) -> Flow | None:
        return self._by_user.get(user_id)

    def pop(self, user_id: int) -> Flow | None:
        return self._by_user.pop(user_id, None)

    def peek(self, user_id: int) -> Flow | None:
        return self._by_user.get(user_id)
