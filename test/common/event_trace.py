from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventEntry:
    """A single traced event where the message formatting is deferred until render()."""
    cycle: int
    category: str
    msg_fmt: str
    msg_args: tuple[Any, ...] = ()

    def render(self) -> str:
        try:
            return self.msg_fmt if not self.msg_args else (self.msg_fmt % self.msg_args)
        except Exception:
            return f"{self.msg_fmt!r} {self.msg_args!r}"


class EventTrace:
    """Keep the last N events (ring buffer) to attach context to test failures."""

    def __init__(self, keep_last: int = 16):
        self.keep_last = keep_last
        self.cycle: int = 0
        self._events: deque[EventEntry] = deque(maxlen=self.keep_last)
        self.stats: Counter = Counter()

    def tick(self, n: int = 1) -> None:
        self.cycle += n

    def __len__(self) -> int:
        return len(self._events)

    def add(self, category: str, msg_fmt: str, msg_args: tuple[Any, ...] = ()) -> None:
        self._events.append(EventEntry(
            self.cycle, category, msg_fmt, msg_args))
        self.stats[category] += 1

    def dump(self) -> str:
        if not self._events:
            return "<trace empty>"

        total = sum(self.stats.values())
        items = sorted(self.stats.items(), key=lambda kv: (-kv[1], kv[0]))

        lines = [f"Total events seen: {total}"]
        if items:
            lines.append("Counts: " + ", ".join(f"{k}={v}" for k, v in items))

        lines.extend(
            f"t={e.cycle:06d} {e.category:<8} {e.render()}" for e in self._events)
        return "\n".join(lines)
