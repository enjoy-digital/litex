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
