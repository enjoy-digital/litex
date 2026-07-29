from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Iterator, List, Optional

from ..common.event_trace import EventTrace
from .transactions import Op, ReadOp, SetTimingOp, WriteOp, TransactionPolicy


@dataclass(frozen=True)
class TimingParams:
    req_valid_delay: int = 0
    aw_w_skew: int = 0
    r_ready_delay: int = 0
    b_ready_delay: int = 0


@dataclass()
class _ReadTxn:
    op: ReadOp
    tp: TimingParams
    ar_delay: int
    ar_done: bool = False

    r_seen: bool = False
    r_delay_cnt: int = 0
    r_done: bool = False


@dataclass()
class _WriteTxn:
    op: WriteOp
    tp: TimingParams
    aw_delay: int
    w_delay: int
    aw_done: bool = False
    w_done: bool = False

    b_seen: bool = False
    b_delay_cnt: int = 0
    b_done: bool = False


class HazardPolicy(Enum):
    STALL = auto()
    DROP_EXPECT = auto()
    NO_GUARD = auto()


class AXILiteMasterStimulus:
    """
    AXI-Lite master stimulus consuming Op stream:
      - SetTimingOp(timing=(req_valid_delay, aw_w_skew, r_ready_delay, b_ready_delay))  [barrier]
      - ReadOp / WriteOp

    SetTimingOp is a barrier: it is applied only when in-flight is empty.
    """

    def __init__(
            self,
            bus,
            op_source: Iterator[Op],
            policy: TransactionPolicy,
            trace: EventTrace,
            hazard_policy: HazardPolicy = HazardPolicy.STALL,
            max_cycles: Optional[int] = None):
        self.bus = bus
        self.op_source = op_source
        self.policy = policy
        self.trace = trace
        self.hazard_policy = hazard_policy
        self.max_cycles = max_cycles

        self.max_outstanding_reads = policy.max_outstanding_reads
        self.max_outstanding_writes = policy.max_outstanding_writes

        self._rd: List[_ReadTxn] = []
        self._wr: List[_WriteTxn] = []

        self._ar_cur: Optional[_ReadTxn] = None
        self._aw_cur: Optional[_WriteTxn] = None
        self._w_cur: Optional[_WriteTxn] = None
        self._r_cur: Optional[_ReadTxn] = None
        self._b_cur: Optional[_WriteTxn] = None

        # timing starts at zero; SetTimingOp will update it
        self._tp = TimingParams()

        # R/B channel-hold tracking for protocol assertions:
        # If RVALID/BVALID was observed while RREADY/BREADY=0,
        # VALID must stay asserted and payload must stay stable until handshake.
        self._r_hold_active: bool = False
        self._r_hold_data: int = 0
        self._r_hold_resp: int = 0
        self._b_hold_active: bool = False
        self._b_hold_resp: int = 0

        self._buf: Optional[Op] = None
        self._done_source = False
        wb = policy.word_bytes
        if wb <= 0 or (wb & (wb - 1)) != 0:
            raise ValueError("policy.word_bytes must be a power of two")

    # -----------------------
    # sizing / hazards
    # -----------------------

    def _word_key(self, addr: int) -> int:
        return addr & ~(self.policy.word_bytes - 1)

    def _has_write_hazard(self, rd_op: ReadOp) -> bool:
        if rd_op.expected_data is None:
            return False
        k = self._word_key(rd_op.addr)
        return any((not wr.b_done) and (self._word_key(wr.op.addr) == k) for wr in self._wr)

    def _has_read_hazard_for_write(self, wr_op: WriteOp) -> bool:
        k = self._word_key(wr_op.addr)
        for rd in self._rd:
            if (not rd.r_done) and (rd.op.expected_data is not None) and (self._word_key(rd.op.addr) == k):
                return True
        return False

    def _has_pending_r(self) -> bool:
        """Any read that has completed AR but not yet completed R."""
        return any(t.ar_done and (not t.r_done) for t in self._rd)

    def _has_pending_b(self) -> bool:
        """Any write that has completed AW+W but not yet completed B."""
        return any(t.aw_done and t.w_done and (not t.b_done) for t in self._wr)

    # -----------------------
    # main loop
    # -----------------------

    def process(self):
        yield from self._drive_idle()

        cycles = 0
        while True:
            try:
                self._schedule_issue()
                yield from self._drive_outputs()
                yield
                yield from self._sample_and_update()

                self.trace.tick()
                cycles += 1

                if self.max_cycles is not None and cycles >= self.max_cycles:
                    raise TimeoutError(
                        f"Stimulus exceeded max_cycles={self.max_cycles}")

                if self._done_source and self._inflight_empty():
                    return

            except Exception as e:
                raise type(e)(
                    f"{e}\n\n--- AXI-Lite stimulus trace ---\n{self.trace.dump()}") from e

    # -----------------------
    # scheduling
    # -----------------------

    def _inflight_empty(self) -> bool:
        return (
            not self._rd and not self._wr
            and self._ar_cur is None and self._aw_cur is None and self._w_cur is None
            and self._r_cur is None and self._b_cur is None
        )

    def _count_rd_inflight(self) -> int:
        return sum(1 for t in self._rd if not t.r_done)

    def _count_wr_inflight(self) -> int:
        return sum(1 for t in self._wr if not t.b_done)

    def _can_issue_read(self) -> bool:
        return self.max_outstanding_reads > 0 and self._count_rd_inflight() < self.max_outstanding_reads

    def _can_issue_write(self) -> bool:
        return self.max_outstanding_writes > 0 and self._count_wr_inflight() < self.max_outstanding_writes

    def _apply_timing_if_idle(self, op: SetTimingOp) -> bool:
        if not self._inflight_empty():
            return False
        self._tp = TimingParams(*op.timing)
        self.trace.add("TIMING", "set %r tag=%s", (op.timing, op.tag))
        return True

    def _schedule_issue(self) -> None:
        add = self.trace.add

        while True:
            op = self._buf
            if op is None:
                if self._done_source:
                    return
                try:
                    op = next(self.op_source)
                except StopIteration:
                    self._done_source = True
                    return

            t = type(op)

            # Barrier: apply timing only when idle.
            if t is SetTimingOp:
                if self._apply_timing_if_idle(op):
                    self._buf = None
                    continue
                self._buf = op
                return

            # Read
            if t is ReadOp:
                if not self._can_issue_read():
                    self._buf = op
                    return

                if self.hazard_policy is not HazardPolicy.NO_GUARD and self._has_write_hazard(op):
                    if self.hazard_policy is HazardPolicy.STALL:
                        add("HAZARD", "stall READ addr=0x%x tag=%s",
                            (op.addr, op.tag))
                        self._buf = op
                        return

                    # DROP_EXPECT
                    op = ReadOp(
                        addr=op.addr,
                        size_bytes=op.size_bytes,
                        expected_data=None,
                        data_mask=op.data_mask,
                        expected_status=op.expected_status,
                        tag=(op.tag + "|haz") if op.tag else "haz",
                    )
                    add("HAZARD", "drop_expect READ addr=0x%x tag=%s",
                        (op.addr, op.tag))

                base = self._tp.req_valid_delay
                if base < 0:
                    base = 0
                self._rd.append(_ReadTxn(op=op, tp=self._tp, ar_delay=base))

                self._buf = None
                add("ISSUE", "READ addr=0x%x size=%d tag=%s",
                    (op.addr, op.size_bytes, op.tag))
                continue

            # Write
            if t is WriteOp:
                if not self._can_issue_write():
                    self._buf = op
                    return

                if self.hazard_policy is HazardPolicy.STALL and self._has_read_hazard_for_write(op):
                    add("HAZARD", "stall WRITE addr=0x%x tag=%s", (op.addr, op.tag))
                    self._buf = op
                    return

                base = self._tp.req_valid_delay
                if base < 0:
                    base = 0
                skew = self._tp.aw_w_skew
                aw_delay = base + (-skew if skew < 0 else 0)
                w_delay = base + (skew if skew > 0 else 0)

                self._wr.append(_WriteTxn(op=op, tp=self._tp,
                                aw_delay=aw_delay, w_delay=w_delay))

                self._buf = None
                add("ISSUE", "WRITE addr=0x%x size=%d be=0x%x tag=%s",
                    (op.addr, op.size_bytes, op.byte_en, op.tag))
                continue

            raise TypeError(f"Unknown op type: {t}")

    # -----------------------
    # drive
    # -----------------------

    def _drive_idle(self):
        b = self.bus
        yield b.aw.valid.eq(0)
        yield b.w.valid.eq(0)
        yield b.ar.valid.eq(0)
        yield b.r.ready.eq(0)
        yield b.b.ready.eq(0)

        yield b.aw.addr.eq(0)
        yield b.ar.addr.eq(0)
        yield b.w.data.eq(0)
        yield b.w.strb.eq(0)

        if hasattr(b.aw, "prot"):
            yield b.aw.prot.eq(0)
        if hasattr(b.ar, "prot"):
            yield b.ar.prot.eq(0)

    def _pick(self, seq, pred):
        for t in seq:
            if pred(t):
                return t
        return None

    def _drive_outputs(self):
        b = self.bus
        yield b.aw.valid.eq(0)
        yield b.w.valid.eq(0)
        yield b.ar.valid.eq(0)

        # tick delays for txns not currently locked
        for rd in self._rd:
            if not rd.ar_done and rd is not self._ar_cur and rd.ar_delay > 0:
                rd.ar_delay -= 1
        for wr in self._wr:
            if not wr.aw_done and wr is not self._aw_cur and wr.aw_delay > 0:
                wr.aw_delay -= 1
            if not wr.w_done and wr is not self._w_cur and wr.w_delay > 0:
                wr.w_delay -= 1

        # AR
        if self._ar_cur is None:
            self._ar_cur = self._pick(self._rd, lambda t: (
                not t.ar_done) and t.ar_delay <= 0)
        if self._ar_cur is not None:
            rd = self._ar_cur
            if not rd.ar_done and rd.ar_delay <= 0:
                yield b.ar.addr.eq(rd.op.addr)
                if hasattr(b.ar, "prot"):
                    yield b.ar.prot.eq(0)
                yield b.ar.valid.eq(1)

        # AW
        if self._aw_cur is None:
            self._aw_cur = self._pick(self._wr, lambda t: (
                not t.aw_done) and t.aw_delay <= 0)
        if self._aw_cur is not None:
            wr = self._aw_cur
            if not wr.aw_done and wr.aw_delay <= 0:
                # self.trace.add("AW_VALID", "aw is now valid", ())
                yield b.aw.addr.eq(wr.op.addr)
                if hasattr(b.aw, "prot"):
                    yield b.aw.prot.eq(0)
                yield b.aw.valid.eq(1)

        # W
        if self._w_cur is None:
            self._w_cur = self._pick(self._wr, lambda t: (
                not t.w_done) and t.w_delay <= 0)
        if self._w_cur is not None:
            wr = self._w_cur
            if not wr.w_done and wr.w_delay <= 0:
                word_bits = len(b.w.data)
                strb_w = len(b.w.strb)
                yield b.w.data.eq(wr.op.data & ((1 << word_bits) - 1))
                yield b.w.strb.eq(wr.op.byte_en & ((1 << strb_w) - 1))
                yield b.w.valid.eq(1)

        yield from self._drive_r_ready()
        yield from self._drive_b_ready()

    def _drive_r_ready(self):
        b = self.bus
        if self._r_cur is None:
            self._r_cur = self._pick(
                self._rd, lambda t: t.ar_done and (not t.r_done))

        yield b.r.ready.eq(0)
        if self._r_cur is None:
            return

        rd = self._r_cur
        if rd.r_done:
            self._r_cur = None
            return

        if not rd.r_seen and (yield b.r.valid):
            rd.r_seen = True
            rd.r_delay_cnt = max(0, rd.tp.r_ready_delay)

        if rd.r_seen:
            if rd.r_delay_cnt > 0:
                rd.r_delay_cnt -= 1
            else:
                yield b.r.ready.eq(1)

    def _drive_b_ready(self):
        b = self.bus
        if self._b_cur is None:
            self._b_cur = self._pick(
                self._wr, lambda t: t.aw_done and t.w_done and (not t.b_done))

        yield b.b.ready.eq(0)
        if self._b_cur is None:
            return

        wr = self._b_cur

        if wr.b_done:
            self._b_cur = None
            return

        if not wr.b_seen and (yield b.b.valid):
            wr.b_seen = True
            wr.b_delay_cnt = max(0, wr.tp.b_ready_delay)

        if wr.b_seen:
            if wr.b_delay_cnt > 0:
                wr.b_delay_cnt -= 1
            else:
                yield b.b.ready.eq(1)

    # -----------------------
    # sample/update + checks
    # -----------------------

    def _status_to_resp(self, st: Any) -> Optional[int]:
        if st is None:
            return None
        # allow int passthrough
        if isinstance(st, int):
            return st
        # allow Status enum from bus_reference_models
        name = st.name
        if name == "OK":
            return 0
        if name == "SLAVE_ERROR":
            return 2
        if name == "DECODE_ERROR":
            return 3
        raise TypeError(f"Unknown status type/value: {st!r}")

    def _sample_and_update(self):
        b = self.bus
        add = self.trace.add

        # ---------------------------------------------------------------------
        # Snapshot all relevant channel signals once per cycle.
        #   1) account for AR/AW/W handshakes
        #   2) protocol assertions (spurious/hold/stability) using updated state
        #   3) account for R/B handshakes + functional checks
        # ---------------------------------------------------------------------

        ar_valid = (yield b.ar.valid)
        ar_ready = (yield b.ar.ready)
        aw_valid = (yield b.aw.valid)
        aw_ready = (yield b.aw.ready)
        w_valid = (yield b.w.valid)
        w_ready = (yield b.w.ready)

        r_valid = (yield b.r.valid)
        r_ready = (yield b.r.ready)
        b_valid = (yield b.b.valid)
        b_ready = (yield b.b.ready)

        # Payload snapshots (safe even if VALID=0)
        r_data = (yield b.r.data)
        r_resp = (yield b.r.resp)
        b_resp = (yield b.b.resp)

        # ---------------------------------------------------------------------
        # 1) First: account for request-side handshakes (AR/AW/W).
        # ---------------------------------------------------------------------

        # AR handshake
        rd = self._ar_cur
        if rd is not None and ar_valid and ar_ready:
            rd.ar_done = True
            self._ar_cur = None
            add("AR_HS", "addr=0x%x tag=%s", (rd.op.addr, rd.op.tag))

        # AW handshake
        wr = self._aw_cur
        if wr is not None and aw_valid and aw_ready:
            wr.aw_done = True
            self._aw_cur = None
            add("AW_HS", "addr=0x%x tag=%s", (wr.op.addr, wr.op.tag))

        # W handshake
        wr = self._w_cur
        if wr is not None and w_valid and w_ready:
            wr.w_done = True
            self._w_cur = None
            add("W_HS", "data=0x%x be=0x%x tag=%s",
                (wr.op.data, wr.op.byte_en, wr.op.tag))

        # ---------------------------------------------------------------------
        # 2) Protocol assertions (separate from drive):
        #   - No spurious responses: R/B must not appear without outstanding txn
        #   - No VALID-drop while READY=0
        #   - Payload stability while VALID=1 & READY=0
        # ---------------------------------------------------------------------

        # --- R channel checks
        if r_valid:
            if not self._has_pending_r():
                add("BUG", "spurious RVALID (no read outstanding)", ())
                raise AssertionError(
                    "RVALID asserted with no read outstanding")

            # Stability while stalled
            if self._r_hold_active:
                if r_data != self._r_hold_data or r_resp != self._r_hold_resp:
                    add(
                        "BUG",
                        "R payload changed while stalled old=(data=0x%x,resp=%d) new=(data=0x%x,resp=%d)",
                        (self._r_hold_data, self._r_hold_resp, r_data, r_resp),
                    )
                    raise AssertionError(
                        "RDATA/RRESP changed while RVALID=1 & RREADY=0 (AXI-Lite violation)"
                    )

            # Hold tracking
            if not r_ready:
                if not self._r_hold_active:
                    self._r_hold_active = True
                    self._r_hold_data = r_data
                    self._r_hold_resp = r_resp
            else:
                # handshake possible -> end hold
                self._r_hold_active = False
        else:
            if self._r_hold_active:
                add("BUG", "RVALID dropped before handshake (RREADY stayed low earlier)", ())
                raise AssertionError(
                    "RVALID dropped while RREADY=0 (AXI-Lite violation)")
            self._r_hold_active = False

        # --- B channel checks
        if b_valid:
            if not self._has_pending_b():
                add("BUG", "spurious BVALID (no write outstanding)", ())
                raise AssertionError(
                    "BVALID asserted with no write outstanding")

            # Stability while stalled
            if self._b_hold_active:
                if b_resp != self._b_hold_resp:
                    add("BUG", "BRESP changed while stalled old=%d new=%d",
                        (self._b_hold_resp, b_resp))
                    raise AssertionError(
                        "BRESP changed while BVALID=1 & BREADY=0 (AXI-Lite violation)"
                    )

            # Hold tracking
            if not b_ready:
                if not self._b_hold_active:
                    self._b_hold_active = True
                    self._b_hold_resp = b_resp
            else:
                self._b_hold_active = False
        else:
            if self._b_hold_active:
                add("BUG", "BVALID dropped before handshake (BREADY stayed low earlier)", ())
                raise AssertionError(
                    "BVALID dropped while BREADY=0 (AXI-Lite violation)")
            self._b_hold_active = False

        # ---------------------------------------------------------------------
        # 3) Now: account for response handshakes + functional checks.
        # ---------------------------------------------------------------------

        # R handshake + checks
        rd = self._r_cur
        if rd is not None and r_valid and r_ready:
            add("R_HS", "data=0x%x resp=%d tag=%s", (r_data, r_resp, rd.op.tag))
            self._check_read(rd.op, r_data, r_resp)
            rd.r_done = True
            self._r_cur = None

        # B handshake + checks
        wr = self._b_cur
        if wr is not None and b_valid and b_ready:
            add("B_HS", "resp=%d tag=%s", (b_resp, wr.op.tag))
            self._check_write(wr.op, b_resp)
            wr.b_done = True
            self._b_cur = None

        # retire completed
        self._rd = [t for t in self._rd if not t.r_done]
        self._wr = [t for t in self._wr if not t.b_done]

    def _check_read(self, op: ReadOp, data: int, resp: int) -> None:
        exp_resp = self._status_to_resp(op.expected_status)
        if exp_resp is not None and resp != exp_resp:
            tag = f" ({op.tag})" if op.tag else ""
            raise AssertionError(
                f"Read resp mismatch{tag}: got {resp}, expected {exp_resp}")

        if op.expected_data is None:
            return

        mask = op.data_mask
        if mask is None:
            wb = self.policy.word_bytes
            lane = op.addr % wb
            sz = op.size_bytes
            if 1 <= sz <= wb and lane + sz <= wb:
                mask = ((1 << (8 * sz)) - 1) << (8 * lane)
            else:
                mask = (1 << len(self.bus.r.data)) - 1

        got = data & mask
        exp = op.expected_data & mask
        if got != exp:
            tag = f" ({op.tag})" if op.tag else ""
            raise AssertionError(
                f"Read data mismatch{tag}: got 0x{data:x}, expected 0x{op.expected_data:x}, mask 0x{mask:x}"
            )

    def _check_write(self, op: WriteOp, resp: int) -> None:
        exp_resp = self._status_to_resp(op.expected_status)
        if exp_resp is not None and resp != exp_resp:
            tag = f" ({op.tag})" if op.tag else ""
            raise AssertionError(
                f"Write resp mismatch{tag}: got {resp}, expected {exp_resp}")
