#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""
USB 2.0 High-Speed PHY digital logic (vendor independent).

The line is handled 4 bits at a time (480 Mbps line, 120 MHz "usb_hs" domain), the transceiver
serializes/deserializes the 4 bits with 4x oversampling (1.92 Gbps SerDes, 16 samples per cycle).

Implements (USB 2.0, 7.1.x):
- TX: SYNC (32 bits), NRZI encoding, bit stuffing, EOP (01111111, not stuffed); OpMode 10 (chirp):
  raw bits (0: K, 1: J), no SYNC/EOP.
- RX: data recovery (4x oversampling, sampling phase tracking), NRZI decoding, SYNC detection, bit
  unstuffing, EOP (bit stuffing violation) detection; own transmissions not received (echo).
- UTMI (8-bit, 60 MHz) <-> line (120 MHz) clock domain crossings.
"""

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *

from litex.soc.interconnect import stream

# Constants ----------------------------------------------------------------------------------------

BITS_PER_CYCLE = 4


# USB HS TX Encoder --------------------------------------------------------------------------------

class USBHSTXEncoder(LiteXModule):
    """
    High-Speed TX encoder ("sys" = 120 MHz, 4 line bits per cycle).

    ``sink``: bytes (``data``) with ``eop`` markers (``eop`` = 1: end of packet, ``data`` ignored).
    ``raw``: OpMode 10 (bit stuffing/NRZI disabled, no SYNC/EOP).

    Outputs ``line`` (4 line states, bit 0 first; 1: J (D+ > D-), 0: K) and ``oe`` (driving).

    Pipeline: nibble source (SYNC/data/EOP, 1 nibble per cycle) -> bit stuffing (4 bits -> 4/5 bits)
    -> NRZI -> gearbox (4 line bits per cycle).
    """
    def __init__(self):
        self.sink_valid = Signal()
        self.sink_ready = Signal()
        self.sink_data  = Signal(8)
        self.sink_eop   = Signal()
        self.raw        = Signal()

        self.line       = Signal(BITS_PER_CYCLE)
        self.oe         = Signal()

        # # #

        buf_depth = 48 # Feed threshold (24) + 4 chunks in flight (feed -> gearbox: 3 cycles).
        feed      = Signal() # Gearbox has room for a new nibble.

        # Nibble source ----------------------------------------------------------------------------
        nib         = Signal(4)
        nib_valid   = Signal()
        nib_nostuff = Signal()
        nib_last    = Signal()
        index       = Signal(3)
        high        = Signal()
        byte        = Signal(8)
        self.sync += [nib_valid.eq(0), nib_last.eq(0)] # Pulses (FSM NextValues take precedence).
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(self.sink_valid & self.sink_eop,
                # EOP without data: dropped.
                self.sink_ready.eq(1),
            ).Elif(self.sink_valid,
                NextValue(index, 0),
                If(self.raw,
                    NextState("DATA"),
                ).Else(
                    NextState("SYNC"),
                )
            )
        )
        fsm.act("SYNC",
            # SYNC: 31 0s then a 1 (LSB first): nibbles 0 x 7, 8.
            If(feed,
                NextValue(nib_valid, 1),
                NextValue(nib, Mux(index == 7, 0x8, 0x0)),
                NextValue(nib_nostuff, 0),
                NextValue(index, index + 1),
                If(index == 7,
                    NextValue(high, 0),
                    NextState("DATA"),
                )
            )
        )
        fsm.act("DATA",
            If(feed,
                If(high,
                    NextValue(nib_valid, 1),
                    NextValue(nib, byte[4:8]),
                    NextValue(nib_nostuff, self.raw),
                    NextValue(high, 0),
                ).Elif(self.sink_valid,
                    self.sink_ready.eq(1),
                    If(self.sink_eop,
                        NextValue(high, 0),
                        If(self.raw,
                            NextValue(nib_last, 1),
                            NextState("DRAIN"),
                        ).Else(
                            NextState("EOP"),
                        )
                    ).Else(
                        NextValue(nib_valid, 1),
                        NextValue(nib, self.sink_data[0:4]),
                        NextValue(nib_nostuff, self.raw),
                        NextValue(byte, self.sink_data),
                        NextValue(high, 1),
                    )
                )
            )
        )
        fsm.act("EOP",
            # EOP: 0 then seven 1s (LSB first: 0xfe), not stuffed.
            If(feed,
                NextValue(nib_valid, 1),
                NextValue(nib, Mux(high, 0xf, 0xe)),
                NextValue(nib_nostuff, 1),
                NextValue(high, ~high),
                If(high,
                    NextValue(nib_last, 1),
                    NextState("DRAIN"),
                )
            )
        )
        fsm.act("DRAIN",
            # Wait for the end of the transmission.
            If(~self.oe & ~nib_valid,
                NextState("IDLE"),
            )
        )

        # Bit stuffing (4 bits -> 4 or 5 bits) -----------------------------------------------------
        st_bits  = Signal(5)
        st_len   = Signal(3)
        st_valid = Signal()
        st_last  = Signal()
        ones     = Signal(3)
        c_ones   = [Signal(3) for _ in range(5)]
        c_bits   = [Signal(5) for _ in range(5)]
        c_len    = [Signal(3) for _ in range(5)]
        self.comb += [
            c_ones[0].eq(ones),
            c_bits[0].eq(0),
            c_len[0].eq(0),
        ]
        for i in range(4):
            bit   = nib[i]
            stuff = Signal()
            # A stuffed bit due after the previous nibble is inserted even before the EOP.
            self.comb += [
                stuff.eq((c_ones[i] == 6) & (~nib_nostuff if i > 0 else 1)),
                If(stuff,
                    # Stuffed 0 then the bit.
                    c_bits[i + 1].eq(c_bits[i] | (bit << (c_len[i] + 1))),
                    c_len[i + 1].eq(c_len[i] + 2),
                    c_ones[i + 1].eq(bit & ~nib_nostuff),
                ).Else(
                    c_bits[i + 1].eq(c_bits[i] | (bit << c_len[i])),
                    c_len[i + 1].eq(c_len[i] + 1),
                    c_ones[i + 1].eq(Mux(bit & ~nib_nostuff, c_ones[i] + 1, 0)),
                )
            ]
        self.sync += [
            st_valid.eq(nib_valid),
            st_last.eq(nib_last),
            If(nib_valid,
                st_bits.eq(c_bits[4]),
                st_len.eq(c_len[4]),
                ones.eq(c_ones[4]),
            ),
            If(fsm.ongoing("IDLE"),
                ones.eq(0),
            ),
        ]

        # NRZI -------------------------------------------------------------------------------------
        nr_levels = Signal(5)
        nr_len    = Signal(3)
        nr_valid  = Signal()
        nr_last   = Signal()
        level     = Signal(reset=1) # J.
        c_level   = [Signal() for _ in range(6)]
        self.comb += c_level[0].eq(level)
        for i in range(5):
            self.comb += If(self.raw,
                c_level[i + 1].eq(st_bits[i]),
            ).Elif(i < st_len,
                c_level[i + 1].eq(c_level[i] ^ ~st_bits[i]),
            ).Else(
                c_level[i + 1].eq(c_level[i]),
            )
        self.sync += [
            nr_valid.eq(st_valid),
            nr_last.eq(st_last),
            If(st_valid,
                nr_levels.eq(Cat(*[c_level[i + 1] & (i < st_len) for i in range(5)])), # Masked.
                nr_len.eq(st_len),
                level.eq(Array(c_level)[st_len]),
            ),
            If(fsm.ongoing("IDLE"),
                level.eq(1),
            ),
        ]

        # Gearbox (4 line bits per cycle) ----------------------------------------------------------
        buf     = Signal(buf_depth)
        count   = Signal(max=buf_depth + 1)
        after   = Signal(max=buf_depth + 1)
        ending  = Signal()
        hold    = Signal() # Last level (padding at the end).
        consume = Signal()
        self.comb += [
            consume.eq(self.oe & (count >= BITS_PER_CYCLE)),
            after.eq(Mux(consume, count - BITS_PER_CYCLE, count)),
            feed.eq(count <= 24),
            self.line.eq(Mux(count >= BITS_PER_CYCLE, buf[:BITS_PER_CYCLE],
                Cat(*[Mux(i < count, buf[i], hold) for i in range(BITS_PER_CYCLE)]))),
        ]
        self.sync += [
            If(nr_valid,
                buf.eq(Mux(consume, buf >> BITS_PER_CYCLE, buf) | (nr_levels << after)),
                count.eq(after + nr_len),
                hold.eq(Array(Cat(*[nr_levels[i] for i in range(5)]))[nr_len - 1]),
            ).Else(
                buf.eq(Mux(consume, buf >> BITS_PER_CYCLE, buf)),
                count.eq(Mux(self.oe & ~consume, 0, after)),
            ),
            If(nr_last,
                ending.eq(1),
            ),
            # Start with 24 bits buffered (slack for the EOP marker, known when the UTMI TxValid
            # goes low), stop once the last bits are sent.
            If(~self.oe & (count >= 24),
                self.oe.eq(1),
            ).Elif(self.oe & ending & (count <= BITS_PER_CYCLE) & ~nr_valid & ~st_valid & ~nib_valid,
                self.oe.eq(0),
                ending.eq(0),
            ),
        ]

# USB HS Data Recovery -----------------------------------------------------------------------------

class USBHSDataRecovery(LiteXModule):
    """
    High-Speed data recovery from 4x oversampled line samples ("sys" = 120 MHz).

    ``samples``: 16 line samples per cycle (sample 0 first, 1: J). The sampling phase follows the
    line transitions (samples taken 2 samples after the edges); the bit rate difference is absorbed
    by outputting 3, 4 or 5 bits per cycle when the sampling phase wraps.

    Outputs ``bits`` (NRZI decoded bits, bit 0 first: 1 when no transition), ``valid`` (valid bits
    mask: 3 to 5 bits, none when idle) and ``idle`` (no transition for ``idle_cycles``). Tolerates
    +-500 ppm with +-0.12 UI edge jitter.

    Pipeline: samples register -> edges/phase classes counts register -> phase tracking -> line bits
    -> NRZI decoding.
    """
    def __init__(self, idle_cycles=8, threshold=4):
        self.samples = Signal(16)
        self.relock  = Signal() # End of packet: lock again on the next edge.
        self.bits    = Signal(5)
        self.valid   = Signal(5)
        self.idle    = Signal(reset=1)

        # # #

        # Stage 0: samples register.
        s0 = Signal(16)
        self.sync += s0.eq(self.samples)

        # Stage 1: edges (with the previous word's last sample), edges per phase class (edge between
        # samples c-1 and c, c = position mod 4), first edge class.
        last   = Signal()
        edges  = Signal(16)
        s1     = Signal(16)
        count  = [Signal(3) for _ in range(4)]
        any1   = Signal()
        first1 = Signal(2)
        first  = Signal(2)
        self.comb += [
            *[edges[i].eq(s0[i] ^ (s0[i - 1] if i > 0 else last)) for i in range(16)],
            first.eq(0),
            *[If(edges[i], first.eq(i + 2)) for i in reversed(range(16))],
        ]
        self.sync += [
            last.eq(s0[15]),
            s1.eq(s0),
            *[count[c].eq(edges[c] + edges[c + 4] + edges[c + 8] + edges[c + 12]) for c in range(4)],
            any1.eq(edges != 0),
            first1.eq(first),
        ]

        # Stage 2: sampling phase (expected edge class: sp + 2). Edges one sample late/early are
        # integrated (+1/-1 per edge), the sampling phase moves by one sample when the integrator
        # reaches +-threshold (jitter filtering, drift tracking).
        sp      = Signal(2)
        sp_prev = Signal(2)
        sp_next = Signal(2)
        late_c  = Signal(2)
        early_c = Signal(2)
        late    = Signal(3)
        early   = Signal(3)
        acc     = Signal((5, True))
        acc_new = Signal((6, True))
        quiet   = Signal(max=idle_cycles + 1)
        s2      = Signal(16)
        self.comb += [
            late_c.eq(sp + 3),
            early_c.eq(sp + 1),
            late.eq(Array(count)[late_c]),
            early.eq(Array(count)[early_c]),
            acc_new.eq(acc + late - early),
            sp_next.eq(sp),
            If(acc_new >= threshold,
                sp_next.eq(sp + 1),
            ).Elif(acc_new <= -threshold,
                sp_next.eq(sp - 1),
            ),
        ]
        self.sync += [
            s2.eq(s1),
            sp_prev.eq(sp),
            If(self.relock,
                self.idle.eq(1),
                quiet.eq(0),
                acc.eq(0),
            ).Elif(any1,
                quiet.eq(0),
                If(self.idle,
                    # Packet start: lock on the first edge.
                    self.idle.eq(0),
                    sp.eq(first1),
                    sp_prev.eq(first1),
                    acc.eq(0),
                ).Else(
                    sp.eq(sp_next),
                    acc.eq(Mux(sp_next != sp, 0, acc_new)),
                ),
            ).Elif(~self.idle,
                If(quiet == (idle_cycles - 1),
                    self.idle.eq(1),
                ).Else(
                    quiet.eq(quiet + 1),
                )
            ),
        ]

        # Stage 3: bits sampled at sp (4 bits), minus/plus one when the sampling phase wraps.
        wrap_fwd = Signal() # sp 3 -> 0: first bit already taken at the end of the previous word.
        wrap_bwd = Signal() # sp 0 -> 3: one bit missed: take sample 0 too.
        self.comb += [
            wrap_fwd.eq((sp_prev == 3) & (sp == 0)),
            wrap_bwd.eq((sp_prev == 0) & (sp == 3)),
        ]
        taps  = [Array(s2[k + 4*i] for k in range(4))[sp] for i in range(4)]
        lbits = Signal(5) # Line levels.
        lval  = Signal(5)
        self.sync += [
            If(self.idle,
                lval.eq(0b00000),
            ).Elif(wrap_fwd,
                lbits.eq(Cat(*taps[1:])),
                lval.eq(0b00111),
            ).Elif(wrap_bwd,
                lbits.eq(Cat(s2[0], *taps)),
                lval.eq(0b11111),
            ).Else(
                lbits.eq(Cat(*taps)),
                lval.eq(0b01111),
            ),
        ]

        # Stage 4: NRZI decoding (1: no transition), reference: J after idle.
        level = Signal(reset=1)
        self.sync += [
            self.valid.eq(lval),
            *[self.bits[i].eq(lbits[i] == (lbits[i - 1] if i > 0 else level)) for i in range(5)],
            If(self.idle,
                level.eq(1),
            ).Elif(lval[4],
                level.eq(lbits[4]),
            ).Elif(lval[3],
                level.eq(lbits[3]),
            ).Elif(lval[2],
                level.eq(lbits[2]),
            ),
        ]

# USB HS RX Decoder --------------------------------------------------------------------------------

class USBHSRXDecoder(LiteXModule):
    """
    High-Speed RX decoder ("sys" = 120 MHz): SYNC detection, bit unstuffing, EOP (bit stuffing
    violation) detection, then bytes, on the NRZI decoded bits (up to 5 per cycle).

    Outputs (one cycle pulses): ``start`` (SYNC detected), ``valid``/``data`` (byte), ``end`` (EOP or
    idle) with ``error`` (not byte aligned / no EOP). ``eop``: EOP detected (to relock the data
    recovery).

    Pipeline: unstuffing (SYNC/EOP detection, kept bits mask) -> byte assembly.
    """
    def __init__(self, sync_zeros=12):
        self.bits       = Signal(5)
        self.valid_bits = Signal(5)
        self.idle       = Signal()

        self.start = Signal()
        self.valid = Signal()
        self.data  = Signal(8)
        self.end   = Signal()
        self.error = Signal()
        self.eop   = Signal()

        # # #

        # Stage 1: SYNC/unstuffing/EOP -----------------------------------------------------------
        # Runs of consecutive 0s/1s on the bit stream (thermometer coded: zeros[k]/ones[k]: at least
        # k+1 consecutive 0s/1s before the bit, saturating) are independent of the packet state; the
        # packet state (data_mode) then only depends on the SYNC end/EOP events (short loops):
        # - SYNC end : 1 after at least sync_zeros 0s (the SYNC's 1 counts for bit stuffing).
        # - Stuffed  : 0 after six 1s (dropped).
        # - EOP      : 1 after six 1s (bit stuffing violation).
        data_mode = Signal()
        zeros     = Signal(sync_zeros)
        ones      = Signal(6)
        c_data  = [Signal()           for _ in range(6)]
        c_zeros = [Signal(sync_zeros) for _ in range(6)]
        c_ones  = [Signal(6)          for _ in range(6)]
        keep    = Signal(5)
        start   = Signal()
        eop     = Signal()
        self.comb += [
            c_data[0].eq(data_mode),
            c_zeros[0].eq(zeros),
            c_ones[0].eq(ones),
        ]
        for i in range(5):
            bit     = self.bits[i]
            valid   = self.valid_bits[i]
            start_i = Signal()
            eop_i   = Signal()
            stuff_i = Signal()
            self.comb += [
                # Runs.
                If(valid,
                    c_zeros[i + 1].eq(Mux(bit, 0, Cat(1, c_zeros[i][:-1]))),
                    c_ones[i + 1].eq(Mux(bit, Cat(1, c_ones[i][:-1]), 0)),
                ).Else(
                    c_zeros[i + 1].eq(c_zeros[i]),
                    c_ones[i + 1].eq(c_ones[i]),
                ),
                # Events.
                start_i.eq(valid & bit &  c_zeros[i][-1]),
                eop_i.eq(  valid & bit &  c_ones[i][5]),
                stuff_i.eq(valid & ~bit & c_ones[i][5]),
                # Packet state.
                c_data[i + 1].eq(Mux(c_data[i], ~eop_i, start_i)),
                keep[i].eq(valid & c_data[i] & ~eop_i & ~stuff_i),
                If(~c_data[i] & start_i, start.eq(1)),
                If( c_data[i] & eop_i,   eop.eq(1)),
            ]
        s1_bits  = Signal(5)
        s1_keep  = Signal(5)
        s1_start = Signal()
        s1_eop   = Signal()
        s1_idle  = Signal()
        self.sync += [
            If(self.idle,
                data_mode.eq(0),
                zeros.eq(0),
            ).Else(
                data_mode.eq(c_data[5]),
                zeros.eq(c_zeros[5]),
                ones.eq(c_ones[5]),
            ),
            s1_bits.eq(self.bits),
            s1_keep.eq(keep & ~Replicate(self.idle, 5)),
            s1_start.eq(start & ~self.idle),
            s1_eop.eq(eop & ~self.idle),
            s1_idle.eq(self.idle & data_mode),
            self.eop.eq(eop & ~self.idle),
        ]

        # Stage 2: byte assembly -------------------------------------------------------------------
        active  = Signal()
        shift   = Signal(8)
        count   = Signal(3)
        c_shift = [Signal(8) for _ in range(6)]
        c_count = [Signal(3) for _ in range(6)]
        byte    = Signal()
        byte_d  = Signal(8)
        self.comb += [
            c_shift[0].eq(shift),
            c_count[0].eq(Mux(s1_start, 0, count)),
        ]
        for i in range(5):
            self.comb += If(s1_keep[i],
                c_shift[i + 1].eq(Cat(c_shift[i][1:], s1_bits[i])),
                c_count[i + 1].eq(c_count[i] + 1),
                If(c_count[i] == 7,
                    byte.eq(1),
                    byte_d.eq(Cat(c_shift[i][1:], s1_bits[i])),
                ),
            ).Else(
                c_shift[i + 1].eq(c_shift[i]),
                c_count[i + 1].eq(c_count[i]),
            )
        # EOP: the EOP's first 0 and six 1s were kept as data: 7 bits pending when byte aligned.
        self.sync += [
            shift.eq(c_shift[5]),
            count.eq(c_count[5]),
            If(s1_start, active.eq(1)),
            If(s1_eop | s1_idle, active.eq(0)),
            self.start.eq(s1_start),
            self.valid.eq(byte & (active | s1_start) & ~s1_eop),
            self.data.eq(byte_d),
            self.end.eq((s1_eop | s1_idle) & active),
            self.error.eq(s1_idle | (s1_eop & (c_count[5] != 7))),
        ]

# USB HS PHY (UTMI) --------------------------------------------------------------------------------

class USBHSPHY(LiteXModule):
    """
    High-Speed UTMI PHY (vendor independent part): UTMI ("usb", 60 MHz) <-> line (``cd_hs``, 120 MHz,
    4 line bits per cycle, 4x oversampled).

    Line side (``cd_hs``): ``rx_samples`` (16 samples, sample 0 first, 1: J), ``tx_line`` (4 line
    states, bit 0 first) with ``tx_oe``. Each TX line state is to be repeated 4 times by the
    serializer (1.92 Gbps).
    """
    def __init__(self, cd_utmi="usb", cd_hs="usb_hs", rx_blank_tail=6):
        # UTMI.
        self.rx_data    = Signal(8)
        self.rx_valid   = Signal()
        self.rx_active  = Signal()
        self.rx_error   = Signal()
        self.tx_data    = Signal(8)
        self.tx_valid   = Signal()
        self.tx_ready   = Signal()
        self.op_mode    = Signal(2)

        # Line.
        self.rx_samples = Signal(16)
        self.tx_line    = Signal(4)
        self.tx_oe      = Signal()

        # # #

        sync_utmi = getattr(self.sync, cd_utmi)
        sync_hs   = getattr(self.sync, cd_hs)

        # TX: UTMI -> FIFO (bytes, EOP markers) -> encoder.
        self.tx_fifo = tx_fifo = ClockDomainsRenamer({"write": cd_utmi, "read": cd_hs})(
            stream.AsyncFIFO([("data", 8), ("eop", 1)], depth=8, buffered=False))
        self.tx_enc  = tx_enc  = ClockDomainsRenamer(cd_hs)(USBHSTXEncoder())
        tx_valid_d  = Signal()
        eop_pending = Signal()
        self.comb += [
            If(eop_pending,
                tx_fifo.sink.valid.eq(1),
                tx_fifo.sink.eop.eq(1),
            ).Else(
                tx_fifo.sink.valid.eq(self.tx_valid),
                tx_fifo.sink.data.eq(self.tx_data),
                self.tx_ready.eq(self.tx_valid & tx_fifo.sink.ready),
            ),
        ]
        sync_utmi += [
            tx_valid_d.eq(self.tx_valid),
            If(tx_valid_d & ~self.tx_valid,
                eop_pending.eq(1),
            ).Elif(tx_fifo.sink.ready,
                eop_pending.eq(0),
            ),
        ]
        raw = Signal()
        self.specials += MultiReg(self.op_mode == 0b10, raw, cd_hs)
        self.comb += [
            tx_enc.raw.eq(raw),
            tx_enc.sink_valid.eq(tx_fifo.source.valid),
            tx_enc.sink_data.eq(tx_fifo.source.data),
            tx_enc.sink_eop.eq(tx_fifo.source.eop),
            tx_fifo.source.ready.eq(tx_enc.sink_ready),
        ]
        sync_hs += [
            self.tx_line.eq(tx_enc.line),
            self.tx_oe.eq(tx_enc.oe),
        ]

        # RX: samples -> data recovery -> decoder -> FIFO (start/byte/end) -> UTMI.
        self.dru = dru = ClockDomainsRenamer(cd_hs)(USBHSDataRecovery())
        self.dec = dec = ClockDomainsRenamer(cd_hs)(USBHSRXDecoder())
        # RX blanked (samples forced to idle) while transmitting and for the line -> samples latency
        # after (own echo): no echo of the transmitted packets (would also corrupt the TX CRC of a
        # UTMI link layer computing it on both directions); the host response (at least 8 bit times
        # after our EOP) may only lose a few SYNC bits.
        rx_blank      = Signal()
        rx_blank_cnt  = Signal(max=rx_blank_tail + 1)
        sync_hs += [
            If(tx_enc.oe,
                rx_blank_cnt.eq(rx_blank_tail),
            ).Elif(rx_blank_cnt != 0,
                rx_blank_cnt.eq(rx_blank_cnt - 1),
            )
        ]
        self.comb += rx_blank.eq(tx_enc.oe | (rx_blank_cnt != 0))
        self.comb += [
            dru.samples.eq(Mux(rx_blank, 0, self.rx_samples)),
            dru.relock.eq(dec.eop | rx_blank),
            dec.bits.eq(dru.bits),
            dec.valid_bits.eq(dru.valid),
            dec.idle.eq(dru.idle),
        ]
        self.rx_fifo = rx_fifo = ClockDomainsRenamer({"write": cd_hs, "read": cd_utmi})(
            stream.AsyncFIFO([("data", 8), ("start", 1), ("end", 1), ("error", 1)], depth=16, buffered=False))
        self.comb += [
            rx_fifo.sink.valid.eq(dec.start | dec.valid | dec.end),
            rx_fifo.sink.data.eq(dec.data),
            rx_fifo.sink.start.eq(dec.start),
            rx_fifo.sink.end.eq(dec.end),
            rx_fifo.sink.error.eq(dec.error),
            rx_fifo.source.ready.eq(1),
        ]
        sync_utmi += [
            self.rx_valid.eq(0),
            self.rx_error.eq(0),
            If(rx_fifo.source.valid,
                If(rx_fifo.source.start,
                    self.rx_active.eq(1),
                ).Elif(rx_fifo.source.end,
                    self.rx_active.eq(0),
                    self.rx_error.eq(rx_fifo.source.error),
                ).Elif(self.rx_active,
                    self.rx_valid.eq(1),
                    self.rx_data.eq(rx_fifo.source.data),
                )
            ),
        ]
