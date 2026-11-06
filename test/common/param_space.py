from __future__ import annotations

import random
from itertools import combinations, cycle, product
from typing import Any, Iterator, Mapping, Optional, Sequence, Literal, Iterable

Mode = Literal["full", "diagonal", "pairwise", "random"]
Vals = tuple[Any, ...]


def _iter_pairwise(levels: tuple[tuple[Any, ...], ...]) -> Iterator[Vals]:
    """
    Greedy 2-wise (pairwise) selection:
    Covers all value pairs across all parameter pairs with few test points.
    """
    if len(levels) <= 1:
        yield from product(*levels)
        return
    idxs = [range(len(v)) for v in levels]
    candidates = list(product(*idxs))

    pair_ij = list(combinations(range(len(idxs)), 2))
    uncovered = {(i, ai, j, aj)
                 for i, j in pair_ij
                 for ai in idxs[i]
                 for aj in idxs[j]
                 }

    def score(c: tuple[int, ...]) -> int:
        s = 0
        for i, j in pair_ij:
            if (i, c[i], j, c[j]) in uncovered:
                s += 1
        return s

    yielded: set[Vals] = set()
    while uncovered:
        best = max(candidates, key=score)
        for i, j in pair_ij:
            uncovered.discard((i, best[i], j, best[j]))

        point = tuple(levels[i][best[i]] for i in range(len(levels)))
        if point not in yielded:   # optional de-dupe
            yielded.add(point)
            yield point


class ParamSpace:
    """
    Discrete parameter space for tests.
    space is a mapping like {"a": (1, 2), "b": ("x", "y")} describing allowed values per parameter.
    Depending on mode, this defines how the test space is explored (full grid, diagonal, pairwise, or random samples).
    Iterating yields value-tuples in stable parameter order.
    """

    def __init__(self,
                 space: Mapping[str, Sequence[Any]],
                 mode: Mode = "full",
                 limit: Optional[int] = None,
                 rng: Optional[random.Random] = None):
        names = tuple(space.keys())
        levels = tuple(tuple(space[n]) for n in names)
        for n, lv in zip(names, levels):
            if not lv:
                raise ValueError(f"Parameter {n!r} has no levels")

        if mode == "random" and rng is None:
            raise TypeError("mode='random' requires rng")
        if mode == "random" and limit is None:
            raise TypeError("random requires limit")

        self.names = names
        self.levels = levels
        self.mode = mode
        self.rng = rng
        self.limit = limit

    def __iter__(self) -> Iterator[Vals]:
        n = 0
        for vals in self._iter_mode():
            yield vals
            n += 1
            if self.limit is not None and n >= self.limit:
                return

    def _iter_mode(self) -> Iterator[Vals]:
        if self.mode == "full":
            yield from product(*self.levels)
            return

        if self.mode == "diagonal":
            L = max(len(v) for v in self.levels)
            iters = [cycle(v) for v in self.levels]
            for _ in range(L):
                yield tuple(next(it) for it in iters)
            return

        if self.mode == "pairwise":
            yield from _iter_pairwise(self.levels)
            return

        if self.mode == "random":
            while True:
                yield tuple(self.rng.choice(v) for v in self.levels)

        raise ValueError(f"Unknown mode: {self.mode!r}")

    def as_dict(self, vals: Vals) -> dict[str, Any]:
        """Map a yielded value-tuple back to {parameter_name: value}."""
        return dict(zip(self.names, vals))

    @staticmethod
    def iter_unique(spaces: Iterable[Iterable[Vals]], seed_seen: Optional[set[Vals]] = None) -> Iterator[Vals]:
        """Chain multiple point streams and yield each point at most once (stable order)."""
        seen: set[Vals] = set() if seed_seen is None else set(seed_seen)
        for space in spaces:
            for vals in space:
                if vals in seen:
                    continue
                seen.add(vals)
                yield vals
