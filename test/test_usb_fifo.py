#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *
from migen.fhdl.specials import Tristate

from litex.soc.cores.usb_fifo import FT245PHYAsynchronous

from test.common import MockTristate


# Mock FT245 pads ----------------------------------------------------------------------------------

class _FT245Pads:
    """Mirror of the signals the FT245 async PHY pokes at.

    `rxf_n` / `txe_n` default high so the PHY starts with "nothing to read" and "cannot write"
    — the test generator flips them as it acts as the FTDI side of the bus.
    """
    def __init__(self, dw=8):
        self.data  = Signal(dw)
        self.rxf_n = Signal(reset=1)
        self.txe_n = Signal(reset=1)
        self.rd_n  = Signal()
        self.wr_n  = Signal()


# Tests --------------------------------------------------------------------------------------------

# 100 MHz clock keeps the PHY's timing counters down to single-digit cycles.
CLK_FREQ = 100e6


class TestFT245PHYAsynchronous(unittest.TestCase):
    def test_instantiation(self):
        # Smoke test: the module builds with a plausible pad record and a real-world frequency.
        pads = _FT245Pads()
        dut  = FT245PHYAsynchronous(pads, CLK_FREQ)
        self.assertEqual(dut.sink.data.nbits,   8)
        self.assertEqual(dut.source.data.nbits, 8)

    def test_read_byte_arrives_on_source(self):
        # FTDI-side mock: hold rxf_n=0 to signal "data available", and drive `i_mock` of the
        # data tristate so the PHY's read FSM samples our chosen byte. Verify it shows up on
        # the SoC-side stream source.
        #
        # The local `rxf_n` Signal in the PHY (after MultiReg) defaults to 0, so the read FSM
        # has already armed by the time the pad's reset value (1) propagates through the
        # synchroniser. To get a deterministic byte on the source, override the i_mock reset
        # value to our wanted byte — that way the very first capture carries it instead of the
        # MockTristate default of 1.
        pads = _FT245Pads()
        wanted = 0xC3

        class _PrimedMockTristateImpl(Module):
            def __init__(self, t):
                # Same as common.MockTristate, but i_mock starts at `wanted` rather than 1.
                t.i_mock = Signal(8, reset=wanted)
                self.comb += If(t.oe,
                    t.target.eq(t.o),
                ).Else(
                    t.target.eq(t.i_mock),
                )
                if t.i is not None:
                    self.comb += If(t.oe,
                        t.i.eq(t.o),
                    ).Else(
                        t.i.eq(t.i_mock),
                    )

        class _PrimedMockTristate:
            @staticmethod
            def lower(t):
                return _PrimedMockTristateImpl(t)

        dut = FT245PHYAsynchronous(pads, CLK_FREQ)
        captured = []

        @passive
        def ftdi_side():
            yield pads.txe_n.eq(1)
            # rxf_n is already low by virtue of the MultiReg default, so the read FSM is
            # already armed at cycle 0 — no need to drive rxf_n explicitly here.
            while True:
                yield

        def consumer():
            yield dut.source.ready.eq(1)
            timeout = 0
            while not ((yield dut.source.valid) and (yield dut.source.ready)):
                yield
                timeout += 1
                self.assertLess(timeout, 200, "source never delivered a byte")
            captured.append((yield dut.source.data))

        run_simulation(dut, [consumer(), ftdi_side()], special_overrides={Tristate: _PrimedMockTristate})
        self.assertEqual(captured, [wanted])

    def test_write_byte_reaches_pads(self):
        # Push a byte into the SoC-side sink and verify the PHY drives it out on `pads.data` with
        # `wr_n` pulsed low. Uses a passive "FTDI" generator that keeps `txe_n` low (FIFO has
        # room) and captures whatever byte is presented when `wr_n` goes active.
        pads = _FT245Pads()
        dut  = FT245PHYAsynchronous(pads, CLK_FREQ)
        captured = []

        @passive
        def ftdi_side():
            # FTDI says "I can accept writes" immediately.
            yield pads.txe_n.eq(0)
            yield pads.rxf_n.eq(1)
            prev_wr_n = 1
            while True:
                cur_wr_n = (yield pads.wr_n)
                # Falling edge of wr_n — sample data.
                if prev_wr_n == 1 and cur_wr_n == 0:
                    captured.append((yield pads.data))
                prev_wr_n = cur_wr_n
                yield

        def producer():
            yield dut.sink.data.eq(0xA5)
            yield dut.sink.valid.eq(1)
            # Hold valid for a handful of cycles so the sync FIFO commits the beat.
            for _ in range(4):
                yield
            yield dut.sink.valid.eq(0)
            # Run long enough for the top FSM to switch from READ to WRITE (with MultiReg +
            # anti-starvation plumbing that takes a few cycles).
            for _ in range(200):
                yield

        run_simulation(dut, [producer(), ftdi_side()], special_overrides={Tristate: MockTristate})
        self.assertIn(0xA5, captured)


if __name__ == "__main__":
    unittest.main()
