from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional, Union

from .ref_models import MemoryReferenceModel


@dataclass(frozen=True)
class ReadOp:
    """
    Read at byte address `addr` `size_bytes` bytes.
    If `expected_data` is not None, the adapter must compare (got & mask) == (expected & mask).
    `expected_status` is adapter-defined. None means 'do not check status'.
    """

    addr: int
    size_bytes: int
    expected_data: Optional[int] = None
    data_mask: Optional[int] = None
    expected_status: Optional[int] = None
    tag: Optional[str] = None


@dataclass(frozen=True)
class WriteOp:
    """
    Write `size_bytes` at byte address `addr`.
    `byte_en` is a per-byte enable bitmask relative to the transfer (bit i enables byte i).
    `expected_status` is adapter-defined. None means 'do not check status'.
    """

    addr: int
    data: int
    size_bytes: int
    byte_en: int
    expected_status: Optional[int] = None
    tag: Optional[str] = None


@dataclass(frozen=True)
class SetTimingOp:
    """
    Control op: request switching to the given timing tuple once in-flight operations are drained.
    """

    timing: tuple[int, ...]
    tag: Optional[str] = None


Op = Union[ReadOp, WriteOp, SetTimingOp]


@dataclass(frozen=True)
class TransactionPolicy:
    base_addr: int
    size_bytes: int
    word_bytes: int
    max_outstanding_reads: int
    max_outstanding_writes: int
    aligned_only: bool = True
    allow_partial_writes: bool = True


class _PatternDone:
    pass


# Internal marker: indicates one pattern-chunk is complete (not forwarded to the bus)
PATTERN_DONE = _PatternDone()

PatternItem = Union[Op, _PatternDone]


class TransactionPatternGen:
    """
    For each timing tuple we run each pattern for N PATTERN_DONE chunks.
    """
    def __init__(self,
                 policy: TransactionPolicy,
                 rng: random.Random,
                 model: MemoryReferenceModel,
                 pattern_cycles_per_timing: int = 1):
        self.policy = policy
        self.rng = rng
        self.model = model

        self.pattern_cycles_per_timing = pattern_cycles_per_timing
        self._patterns: list[tuple[str, Iterator[PatternItem]]] = []

    def add_custom(self, name: str, it: Iterator[PatternItem]) -> None:
        """Add a custom pattern iterator (must yield PATTERN_DONE once per chunk)."""
        self._patterns.append((name, it))

    def _add_pattern(self, name: str, gen_factory) -> None:
        it = gen_factory()
        self._patterns.append((name, it))

    def stream(self, timings: Iterable[tuple[int, ...]]) -> Iterator[Op]:
        for t in timings:
            yield SetTimingOp(t)

            for pat_name, it in self._patterns:
                done_seen = 0
                ops_since_done = 0

                while done_seen < self.pattern_cycles_per_timing:
                    try:
                        op = next(it)
                    except StopIteration as e:
                        raise RuntimeError(
                            f"Pattern '{pat_name}' ended unexpectedly (must be infinite)."
                        ) from e

                    if op is PATTERN_DONE:
                        if ops_since_done == 0:
                            raise RuntimeError(
                                f"Pattern '{pat_name}' yield PATTERN_DONE without producing ops."
                            )
                        done_seen += 1
                        ops_since_done = 0
                        continue

                    ops_since_done += 1
                    yield op

    def _full_byte_en(self, nbytes: int) -> int:
        return (1 << nbytes) - 1

    def _rand_off(self, size_bytes: int) -> int:
        """Random offset within policy window. Honors aligned_only."""
        if size_bytes <= 0:
            raise ValueError("size_bytes must be > 0")

        p = self.policy
        if size_bytes > p.size_bytes:
            raise ValueError("access larger than window")

        if p.aligned_only:
            if (size_bytes & (size_bytes - 1)) != 0:
                raise ValueError(
                    "aligned_only expects power-of-two access sizes")
            align = size_bytes
            max_off = p.size_bytes - size_bytes
            return self.rng.randrange((max_off // align) + 1) * align

        return self.rng.randrange(0, p.size_bytes - size_bytes + 1)

    def _rand_data(self, size_bytes: int) -> int:
        return self.rng.getrandbits(8 * size_bytes)

    def add_scatter_word_write_then_readback(self, count: int = 8) -> None:
        """
        Example:
            W @10=ABCD ; W @04=1122 ; W @1C=DEAD ;
            R @10==ABCD ; R @04==1122 ; R @1C==DEAD
        """
        n = self.policy.word_bytes
        be_full = self._full_byte_en(n)
        mask_default = (1 << (8 * n)) - 1
        base = self.policy.base_addr
        name = "scatter_word_write_then_readback"

        def gen() -> Iterator[PatternItem]:
            while True:
                k = min(count, self.policy.size_bytes // n)
                offs = [self._rand_off(n) for _ in range(k)]

                for i, off in enumerate(offs):
                    data = self._rand_data(n)
                    st = self.model.expected_write(off, data, n, be_full)
                    yield WriteOp(
                        base + off,
                        data,
                        n,
                        be_full,
                        expected_status=st,
                        tag=f"{name}_wr[{i}]",
                    )

                for i, off in enumerate(offs):
                    st, exp, m = self.model.expected_read(off, n)
                    yield ReadOp(
                        base + off,
                        n,
                        expected_data=exp,
                        data_mask=(mask_default if m is None else m),
                        expected_status=st,
                        tag=f"{name}_rd[{i}]",
                    )

                yield PATTERN_DONE

        self._add_pattern(name, gen)

    def _partial_write_masks(self, allow_zero: bool) -> tuple[int, ...]:
        n = self.policy.word_bytes
        full = self._full_byte_en(n)
        masks: list[int] = [0] if allow_zero else []
        masks += [1 << i for i in range(n)]  # single-lane
        if n >= 2:
            masks += [3 << i for i in range(n - 1)]  # adjacent pairs
        if n >= 4 and (n % 2) == 0:
            half = (1 << (n // 2)) - 1
            masks += [half, half << (n // 2)]  # half-word-ish
        masks.append(full)  # baseline full write

        # Extra masks for wide buses (improves coverage for 64B+ lanes).
        if n >= 8:
            for bl in (4, 8, 16):
                if bl <= n:
                    for start in (0, (n - bl) // 2, n - bl):
                        masks += [((1 << bl) - 1) << start]
            masks += [sum(1 << i for i in range(0, n, 2))]  # every other byte
            masks += [sum(1 << i for i in range(0, n, 4))]  # every 4th byte
            # every 4th byte (shifted)
            masks += [sum(1 << i for i in range(1, n, 4))]

        masks = list(dict.fromkeys(masks))  # de-dupe, keep order
        return tuple(masks)

    def add_scatter_partial_writes_full_word_readback(
        self, count: int = 16, allow_zero_byte_en: bool = False
    ) -> None:
        """
        Example:
            W @08 BE=b01 data=00AA ; W @14 BE=b10 data=BB00 ; W @00 BE=b01 data=0033 ;
            R(word) @08==??AA ; R(word) @14==BB?? ; R(word) @00==??33
        """
        n = self.policy.word_bytes
        base = self.policy.base_addr
        name = "scatter_partial_writes_full_word_readback"
        mask_default = (1 << (8 * n)) - 1
        masks_t = self._partial_write_masks(allow_zero_byte_en)

        def gen() -> Iterator[PatternItem]:
            while True:
                k = min(count, self.policy.size_bytes // n)
                offs = [self._rand_off(n)
                        for _ in range(k)]  # word-aligned scatter

                for i, off in enumerate(offs):
                    be = self.rng.choice(masks_t)
                    # Occasionally pick a fully random (non-zero) mask.
                    if self.rng.randrange(6) == 0:
                        be = self.rng.randrange(
                            0 if allow_zero_byte_en else 1, 1 << n)

                    data = self._rand_data(n)
                    st = self.model.expected_write(off, data, n, be)
                    yield WriteOp(
                        base + off,
                        data,
                        n,
                        be,
                        expected_status=st,
                        tag=f"{name}_wr[{i}]",
                    )

                for i, off in enumerate(offs):
                    st, exp, m = self.model.expected_read(off, n)
                    yield ReadOp(
                        base + off,
                        n,
                        expected_data=exp,
                        data_mask=(mask_default if m is None else m),
                        expected_status=st,
                        tag=f"{name}_rd[{i}]",
                    )

                yield PATTERN_DONE

        self._add_pattern(name, gen)

    def add_sequential_write_block_then_read_block(
        self,
        block_len: int = 8,
        step_bytes: Optional[int] = None,
        wrap: bool = True,
    ) -> None:
        """
        Example (block_len=4, step=2):
            W @00=0001 ; W @02=0002 ; W @04=0003 ; W @06=0004 ;
            R @00==0001 ; R @02==0002 ; R @04==0003 ; R @06==0004
        """
        n = self.policy.word_bytes
        step = step_bytes if step_bytes is not None else n
        if self.policy.aligned_only:
            # keep addresses aligned for full-word accesses
            step = ((step + n - 1) // n) * n
        be_full = self._full_byte_en(n)
        mask_default = (1 << (8 * n)) - 1
        base = self.policy.base_addr
        name = "sequential_write_block_then_read_block"

        def gen() -> Iterator[PatternItem]:
            while True:
                start = self._rand_off(n)
                offs: list[int] = []
                for i in range(block_len):
                    off = start + i * step
                    if wrap:
                        off %= self.policy.size_bytes
                    else:
                        if off > self.policy.size_bytes - n:
                            break
                    offs.append(off)

                for i, off in enumerate(offs):
                    data = self._rand_data(n)
                    st = self.model.expected_write(off, data, n, be_full)
                    yield WriteOp(
                        base + off,
                        data,
                        n,
                        be_full,
                        expected_status=st,
                        tag=f"{name}_wr[{i}]",
                    )

                for i, off in enumerate(offs):
                    st, exp, m = self.model.expected_read(off, n)
                    yield ReadOp(
                        base + off,
                        n,
                        expected_data=exp,
                        data_mask=(mask_default if m is None else m),
                        expected_status=st,
                        tag=f"{name}_rd[{i}]",
                    )

                yield PATTERN_DONE

        self._add_pattern(name, gen)

    def add_sequential_write_then_immediate_readback(
        self,
        count: int = 32,
        step_bytes: Optional[int] = None,
        wrap: bool = True,
    ) -> None:
        """
        Example (count=3, step=2):
            W @10=CAFE ; R @10==CAFE ; W @12=0102 ; R @12==0102 ; W @14=0BAD ; R @14==0BAD
        """
        n = self.policy.word_bytes
        step = step_bytes if step_bytes is not None else n
        if self.policy.aligned_only:
            step = ((step + n - 1) // n) * n
        be_full = self._full_byte_en(n)
        mask_default = (1 << (8 * n)) - 1
        base = self.policy.base_addr
        name = "sequential_write_then_immediate_readback"

        def gen() -> Iterator[PatternItem]:
            while True:
                start = self._rand_off(n)

                for i in range(count):
                    off = start + i * step
                    if wrap:
                        off %= self.policy.size_bytes
                    else:
                        if off > self.policy.size_bytes - n:
                            break

                    data = self._rand_data(n)
                    st_w = self.model.expected_write(off, data, n, be_full)
                    yield WriteOp(
                        base + off,
                        data,
                        n,
                        be_full,
                        expected_status=st_w,
                        tag=f"{name}_wr[{i}]",
                    )

                    st_r, exp, m = self.model.expected_read(off, n)
                    yield ReadOp(
                        base + off,
                        n,
                        expected_data=exp,
                        data_mask=(mask_default if m is None else m),
                        expected_status=st_r,
                        tag=f"{name}_rd[{i}]",
                    )

                yield PATTERN_DONE

        self._add_pattern(name, gen)

    def add_same_word_partial_writes_then_full_word_readback(
        self,
        writes_per_word: int = 4,
        words: int = 8,
        allow_zero_byte_en: bool = False,
        random_lane_order: bool = True,
    ) -> None:
        """
        Example (writes_per_word=3):
            W @20 BE=b01 data=0011 ; W @20 BE=b10 data=2200 ; W @20 BE=b01 data=0033 ;
            R(word) @20==2233 (merge)
        """
        n = self.policy.word_bytes
        base = self.policy.base_addr
        name = "same_word_partial_writes_then_full_word_readback"
        mask_default = (1 << (8 * n)) - 1
        masks_t = self._partial_write_masks(allow_zero_byte_en)

        def gen() -> Iterator[PatternItem]:
            while True:
                k = min(words, self.policy.size_bytes // n)
                offs = [self._rand_off(n) for _ in range(k)]  # word-aligned

                zero_used = False

                for wi, off in enumerate(offs):
                    lanes = list(range(n))
                    if random_lane_order:
                        self.rng.shuffle(lanes)

                    for j in range(writes_per_word):
                        if allow_zero_byte_en and not zero_used:
                            be = 0
                            zero_used = True
                        elif j < n:
                            be = (
                                1 << lanes[j]
                            )  # prefer distinct single-byte updates first
                        else:
                            be = self.rng.choice(masks_t)

                        # Occasionally pick a fully random mask (including 0 if enabled).
                        if self.rng.randrange(8) == 0:
                            lo = 0 if allow_zero_byte_en else 1
                            be = self.rng.randrange(lo, 1 << n)

                        data = self._rand_data(n)
                        st = self.model.expected_write(off, data, n, be)
                        yield WriteOp(
                            base + off,
                            data,
                            n,
                            be,
                            expected_status=st,
                            tag=f"{name}_wr[w={wi}][{j}]",
                        )

                    st, exp, m = self.model.expected_read(off, n)
                    yield ReadOp(
                        base + off,
                        n,
                        expected_data=exp,
                        data_mask=(mask_default if m is None else m),
                        expected_status=st,
                        tag=f"{name}_rd[w={wi}]",
                    )

                yield PATTERN_DONE

        self._add_pattern(name, gen)

    def add_hazard_pingpong_raw_waw(self, iters: int = 4) -> None:
        """
        Example:
            W @20=1111 ; R @20==1111 ; W @24=2222 ; R @24==2222 ; W @20=3333 ; W @20=4444 ; R @20==4444
            W @00=00AA ; R @00==00AA ; W @02=00BB ; R @02==00BB ; W @00=00CC ; W @00=00DD ; R @00==00DD
        """
        n = self.policy.word_bytes
        be_full = self._full_byte_en(n)
        mask_default = (1 << (8 * n)) - 1
        base = self.policy.base_addr
        name = "hazard_pingpong_raw_waw"

        def gen() -> Iterator[PatternItem]:
            while True:
                a = self._rand_off(n)
                b = self._rand_off(n)
                if b == a:
                    b = (a + n) % self.policy.size_bytes

                for i in range(iters):
                    # RAW on A
                    d = self._rand_data(n)
                    st = self.model.expected_write(a, d, n, be_full)
                    yield WriteOp(
                        base + a,
                        d,
                        n,
                        be_full,
                        expected_status=st,
                        tag=f"{name}_wa[{i}]",
                    )
                    st, exp, m = self.model.expected_read(a, n)
                    yield ReadOp(
                        base + a,
                        n,
                        expected_data=exp,
                        data_mask=(mask_default if m is None else m),
                        expected_status=st,
                        tag=f"{name}_ra[{i}]",
                    )

                    # interleave B
                    d = self._rand_data(n)
                    st = self.model.expected_write(b, d, n, be_full)
                    yield WriteOp(
                        base + b,
                        d,
                        n,
                        be_full,
                        expected_status=st,
                        tag=f"{name}_wb[{i}]",
                    )
                    st, exp, m = self.model.expected_read(b, n)
                    yield ReadOp(
                        base + b,
                        n,
                        expected_data=exp,
                        data_mask=(mask_default if m is None else m),
                        expected_status=st,
                        tag=f"{name}_rb[{i}]",
                    )

                    # WAW on A (final value must win)
                    d1 = self._rand_data(n)
                    st = self.model.expected_write(a, d1, n, be_full)
                    yield WriteOp(
                        base + a,
                        d1,
                        n,
                        be_full,
                        expected_status=st,
                        tag=f"{name}_wa1[{i}]",
                    )
                    d2 = self._rand_data(n)
                    st = self.model.expected_write(a, d2, n, be_full)
                    yield WriteOp(
                        base + a,
                        d2,
                        n,
                        be_full,
                        expected_status=st,
                        tag=f"{name}_wa2[{i}]",
                    )
                    st, exp, m = self.model.expected_read(a, n)
                    yield ReadOp(
                        base + a,
                        n,
                        expected_data=exp,
                        data_mask=(mask_default if m is None else m),
                        expected_status=st,
                        tag=f"{name}_ra2[{i}]",
                    )

                yield PATTERN_DONE

        self._add_pattern(name, gen)

    def add_boundary_edge_accesses_with_invalid(
        self, reps: int = 2, include_invalid: bool = True
    ) -> None:
        """
        Example:
            W @00=0102 ; R @00==0102 ; W @FE=ABCD ; R @FE==ABCD ; R @100 status=DECODE_ERROR
            W @02=1122 ; R @02==1122 ; W @FC=3344 ; R @FC==3344 ; W @100 status=DECODE_ERROR ; R @102 status=DECODE_ERROR
        """
        n = self.policy.word_bytes
        be_full = self._full_byte_en(n)
        mask_default = (1 << (8 * n)) - 1
        base = self.policy.base_addr
        name = "boundary_edge_accesses_with_invalid"

        def gen() -> Iterator[PatternItem]:
            while True:
                size = self.policy.size_bytes

                edges = [0, n, 2 * n, size - n, size - 2 * n, size - 3 * n]
                edges = [off for off in edges if 0 <= off <= size - n]
                if not edges:
                    edges = [0]

                for r in range(reps):
                    for j, off in enumerate(edges):
                        d = self._rand_data(n)
                        st = self.model.expected_write(off, d, n, be_full)
                        yield WriteOp(
                            base + off,
                            d,
                            n,
                            be_full,
                            expected_status=st,
                            tag=f"{name}_wr[{r},{j}]",
                        )
                        st, exp, m = self.model.expected_read(off, n)
                        yield ReadOp(
                            base + off,
                            n,
                            expected_data=exp,
                            data_mask=(mask_default if m is None else m),
                            expected_status=st,
                            tag=f"{name}_rd[{r},{j}]",
                        )

                # "first invalid" aligned accesses past the window
                if include_invalid:
                    for j, off in enumerate([size, size + n]):
                        d = self._rand_data(n)
                        st = self.model.expected_write(off, d, n, be_full)
                        yield WriteOp(
                            base + off,
                            d,
                            n,
                            be_full,
                            expected_status=st,
                            tag=f"{name}_inv_wr[{j}]",
                        )
                        st, exp, m = self.model.expected_read(off, n)
                        yield ReadOp(
                            base + off,
                            n,
                            expected_data=exp,
                            data_mask=m,
                            expected_status=st,
                            tag=f"{name}_inv_rd[{j}]",
                        )

                yield PATTERN_DONE

        self._add_pattern(name, gen)
