#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""
USB 2.0 Full-Speed/Low-Speed PHY (UTMI, 8-bit, 60 MHz).

Vendor independent: D+/D- single-ended inputs and driven outputs (with output enable). The bit rate
is recovered from the 60 MHz clock (5 clocks per Full-Speed bit, 40 per Low-Speed bit), the bit phase
is realigned on each line transition and bits are sampled in the middle of their period.

Implements (USB 2.0, 7.1.x):
- Line state (UTMI LineState: [0] = D+, [1] = D-, synchronized).
- RX: start of packet (J -> K), SYNC, NRZI decoding, bit unstuffing (a 1 after six 1s is a stuff
  error), EOP (SE0 then J), UTMI RxActive/RxValid/RxError.
- TX: SYNC, NRZI encoding, bit stuffing, EOP (2 bits SE0 + 1 bit J), UTMI TxReady handshake.
- UTMI OpMode: 00 normal, 01 non-driving, 10 bit stuffing/NRZI disabled (raw bits, no SYNC/EOP).
- UTMI XcvrSelect: 01 Full-Speed, 10/11 Low-Speed (J/K swapped, 1.5 Mbps).
"""

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *

# Constants ----------------------------------------------------------------------------------------

LINE_SE0 = 0b00
LINE_J   = 0b01 # Full-Speed J (D+ high); Low-Speed K.
LINE_K   = 0b10 # Full-Speed K (D- high); Low-Speed J.
LINE_SE1 = 0b11

OP_MODE_NORMAL      = 0b00
OP_MODE_NON_DRIVING = 0b01
OP_MODE_RAW         = 0b10

def bit_cycles(clk_freq, bit_rate):
    cycles = clk_freq/bit_rate
    assert cycles == int(cycles) and cycles >= 4
    return int(cycles)

# USB FS/LS RX -------------------------------------------------------------------------------------

class USBFSRX(LiteXModule):
    """
    Full-Speed/Low-Speed receiver.

    ``line`` is the synchronized line state ({D-, D+}), ``low_speed`` selects the Low-Speed bit rate
    and J/K polarity. Outputs UTMI RX signals (``data``/``valid`` per byte, ``active`` from SYNC to
    EOP, ``error`` on bit stuffing errors or SE0 in the middle of a byte).
    """
    def __init__(self, clk_freq=60e6):
        self.line      = Signal(2)
        self.low_speed = Signal()
        self.enable    = Signal(reset=1)

        self.data      = Signal(8)
        self.valid     = Signal()
        self.active    = Signal()
        self.error     = Signal()

        # # #

        fs_cycles = bit_cycles(clk_freq, 12e6)
        ls_cycles = bit_cycles(clk_freq, 1.5e6)

        # Line state (J/K relative to the speed).
        j = Signal(2)
        k = Signal(2)
        self.comb += [
            j.eq(Mux(self.low_speed, LINE_K, LINE_J)),
            k.eq(Mux(self.low_speed, LINE_J, LINE_K)),
        ]

        # Bit phase: realigned on each line transition, bits sampled at mid-period.
        line_d  = Signal(2)
        phase   = Signal(max=ls_cycles)
        sample  = Signal()
        period  = Signal(max=ls_cycles + 1)
        self.comb += [
            period.eq(Mux(self.low_speed, ls_cycles, fs_cycles)),
            sample.eq(phase == Mux(self.low_speed, ls_cycles//2, fs_cycles//2)),
        ]
        self.sync += [
            line_d.eq(self.line),
            If(self.line != line_d,
                phase.eq(0),
            ).Elif(phase == (period - 1),
                phase.eq(0),
            ).Else(
                phase.eq(phase + 1),
            ),
        ]

        # NRZI decoding: 1 when the sampled state doesn't change, 0 otherwise.
        prev = Signal(2)
        bit  = Signal()
        self.comb += bit.eq(self.line == prev)

        # Bit unstuffing / byte assembly.
        ones      = Signal(3)
        shift     = Signal(8)
        count     = Signal(3)
        byte_done = Signal()
        self.sync += [
            self.valid.eq(byte_done),
            If(byte_done, self.data.eq(Cat(shift[1:], bit))),
        ]

        # Last stable J/K state (D+/D- skew: transient SE0/SE1 samples at the transitions).
        last_jk = Signal(2)
        self.sync += If((self.line == j) | (self.line == k), last_jk.eq(self.line))

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            # Start of packet: J -> K (possibly through a transient SE0/SE1).
            If(self.enable & (self.line == k) & (last_jk == j),
                NextValue(prev, j),
                NextState("SYNC"),
            )
        )
        fsm.act("SYNC",
            # SYNC: K/J alternations (0s) ending with K K (1): start of the data.
            If(sample,
                NextValue(prev, self.line),
                If(self.line == LINE_SE0,
                    NextState("IDLE"),
                ).Elif(bit,
                    NextValue(ones,  1), # The SYNC's last bit counts for bit stuffing.
                    NextValue(count, 0),
                    NextState("DATA"),
                )
            )
        )
        fsm.act("DATA",
            self.active.eq(1),
            If(sample,
                NextValue(prev, self.line),
                If(self.line == LINE_SE0,
                    # SE0: EOP (a partial byte is an error).
                    self.error.eq(count != 0),
                    NextState("EOP"),
                ).Elif(ones == 6,
                    # Stuffed bit: must be a 0 (transition).
                    NextValue(ones, 0),
                    If(bit,
                        self.error.eq(1),
                        NextState("ERROR"),
                    )
                ).Else(
                    NextValue(ones, Mux(bit, ones + 1, 0)),
                    NextValue(shift, Cat(shift[1:], bit)),
                    NextValue(count, count + 1),
                    byte_done.eq(count == 7),
                )
            )
        )
        fsm.act("EOP",
            self.active.eq(1),
            # End of EOP (J).
            If(self.line != LINE_SE0,
                NextState("IDLE"),
            )
        )
        fsm.act("ERROR",
            # Wait for the line to be idle (J) for a bit period.
            If(sample & (self.line == j),
                NextState("IDLE"),
            )
        )

# USB FS/LS TX -------------------------------------------------------------------------------------

class USBFSTX(LiteXModule):
    """
    Full-Speed/Low-Speed transmitter.

    UTMI TX (``data``/``valid``/``ready``): ``ready`` is asserted for one cycle when ``data`` is
    loaded; the packet ends (EOP) when ``valid`` is low at a byte boundary. Drives ``line`` (with
    ``oe``) and ``busy`` while transmitting.
    """
    def __init__(self, clk_freq=60e6):
        self.data      = Signal(8)
        self.valid     = Signal()
        self.ready     = Signal()
        self.low_speed = Signal()
        self.op_mode   = Signal(2)

        self.line      = Signal(2)
        self.oe        = Signal()
        self.busy      = Signal()

        # # #

        fs_cycles = bit_cycles(clk_freq, 12e6)
        ls_cycles = bit_cycles(clk_freq, 1.5e6)

        j = Signal(2)
        k = Signal(2)
        self.comb += [
            j.eq(Mux(self.low_speed, LINE_K, LINE_J)),
            k.eq(Mux(self.low_speed, LINE_J, LINE_K)),
        ]

        # Bit timing (strobe: end of the current bit period).
        phase  = Signal(max=ls_cycles)
        period = Signal(max=ls_cycles + 1)
        strobe = Signal()
        self.comb += [
            period.eq(Mux(self.low_speed, ls_cycles, fs_cycles)),
            strobe.eq(phase == (period - 1)),
        ]
        self.sync += If(self.busy & ~strobe, phase.eq(phase + 1)).Else(phase.eq(0))

        # Line state shown during the current bit period, NRZI/bit stuffing.
        raw   = Signal()
        state = Signal(2, reset=LINE_J)
        shift = Signal(7)
        bits  = Signal(3) # Bits remaining in shift.
        ones  = Signal(3)
        stuff = Signal()
        eop   = Signal(2)
        self.comb += [
            raw.eq(self.op_mode == OP_MODE_RAW),
            stuff.eq(~raw & (ones == 6)),
        ]

        def show(bit):
            """Show a data bit during the next bit period."""
            return If(raw,
                NextValue(state, Mux(bit, j, k)),
            ).Elif(bit,
                NextValue(ones, ones + 1),
            ).Else(
                # 0: transition.
                NextValue(ones, 0),
                NextValue(state, state ^ 0b11),
            )

        def load(byte, idle=False):
            # From idle (J), the first bit is J (1) or K (0) in all modes.
            first = [
                NextValue(state, Mux(byte[0], j, k)),
                NextValue(ones, ~raw & byte[0]),
            ] if idle else [show(byte[0])]
            return first + [
                NextValue(shift, byte[1:]),
                NextValue(bits, 7),
            ]

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            NextValue(state, j),
            If(self.valid & (self.op_mode != OP_MODE_NON_DRIVING),
                If(raw,
                    # Raw mode: data directly (no SYNC).
                    self.ready.eq(1),
                    *load(self.data, idle=True),
                ).Else(
                    *load(Constant(0x80, 8), idle=True), # SYNC.
                ),
                NextState("SEND"),
            )
        )
        fsm.act("SEND",
            self.busy.eq(1),
            self.oe.eq(1),
            If(strobe,
                If(stuff,
                    # Stuffed 0 (transition) after six 1s.
                    NextValue(ones, 0),
                    NextValue(state, state ^ 0b11),
                ).Elif(bits != 0,
                    show(shift[0]),
                    NextValue(shift, shift[1:]),
                    NextValue(bits, bits - 1),
                ).Elif(self.valid,
                    # Next byte.
                    self.ready.eq(1),
                    *load(self.data),
                ).Elif(raw,
                    NextState("IDLE"),
                ).Else(
                    # EOP: 2 bits SE0 + 1 bit J.
                    NextValue(eop, 0),
                    NextState("EOP"),
                )
            )
        )
        fsm.act("EOP",
            self.busy.eq(1),
            self.oe.eq(1),
            If(strobe,
                NextValue(eop, eop + 1),
                If(eop == 2,
                    NextState("IDLE"),
                )
            )
        )
        self.comb += [
            If(fsm.ongoing("EOP"),
                self.line.eq(Mux(eop == 2, j, LINE_SE0)),
            ).Else(
                self.line.eq(state),
            )
        ]

# USB FS/LS PHY ------------------------------------------------------------------------------------

class USBFSPHY(LiteXModule):
    """
    USB 2.0 Full-Speed/Low-Speed UTMI PHY (8-bit, "sys" clock at ``clk_freq``, 60 MHz typically).

    ``utmi`` signals are exposed as attributes (LUNA naming: ``rx_data``, ``rx_valid``, ``rx_active``,
    ``rx_error``, ``line_state``, ``tx_data``, ``tx_valid``, ``tx_ready``, ``op_mode``,
    ``xcvr_select``, ``term_select``). Transceiver side: ``dp_i``/``dn_i`` (asynchronous),
    ``dp_o``/``dn_o``/``oe``.
    """
    def __init__(self, clk_freq=60e6):
        # UTMI.
        self.rx_data     = Signal(8)
        self.rx_valid    = Signal()
        self.rx_active   = Signal()
        self.rx_error    = Signal()
        self.line_state  = Signal(2)
        self.tx_data     = Signal(8)
        self.tx_valid    = Signal()
        self.tx_ready    = Signal()
        self.op_mode     = Signal(2)
        self.xcvr_select = Signal(2, reset=0b01)
        self.term_select = Signal()

        # Transceiver.
        self.dp_i = Signal()
        self.dn_i = Signal()
        self.dp_o = Signal()
        self.dn_o = Signal()
        self.oe   = Signal()

        # # #

        low_speed = Signal()
        self.comb += low_speed.eq(self.xcvr_select[1])

        # Line state.
        line = Signal(2)
        self.specials += MultiReg(Cat(self.dp_i, self.dn_i), line)
        self.comb += self.line_state.eq(line)

        # TX.
        self.tx = tx = USBFSTX(clk_freq)
        self.comb += [
            tx.data.eq(self.tx_data),
            tx.valid.eq(self.tx_valid),
            self.tx_ready.eq(tx.ready),
            tx.low_speed.eq(low_speed),
            tx.op_mode.eq(self.op_mode),
            self.dp_o.eq(tx.line[0]),
            self.dn_o.eq(tx.line[1]),
            self.oe.eq(tx.oe),
        ]

        # RX (disabled while transmitting).
        self.rx = rx = USBFSRX(clk_freq)
        self.comb += [
            rx.line.eq(line),
            rx.low_speed.eq(low_speed),
            rx.enable.eq(~tx.busy),
            self.rx_data.eq(rx.data),
            self.rx_valid.eq(rx.valid),
            self.rx_active.eq(rx.active),
            self.rx_error.eq(rx.error),
        ]
