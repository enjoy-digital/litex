#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import *

from litex.soc.cores.uart import UARTPads, RS232PHY


class _LoopbackDUT(LiteXModule):
    """A single RS232PHY with `pads.rx` tied back to `pads.tx` for self-loopback tests."""
    def __init__(self, clk_freq, baudrate):
        self.pads = UARTPads()
        self.phy  = RS232PHY(self.pads, clk_freq=clk_freq, baudrate=baudrate)
        self.comb += self.pads.rx.eq(self.pads.tx)


class TestUART(unittest.TestCase):
    def test_loopback(self):
        # Use a short "symbol time" so the test runs in tens of ms, not seconds.
        # clk/baud = 10 → 10 sys cycles per UART bit, 100 cycles per 10-bit frame.
        dut     = _LoopbackDUT(clk_freq=1_000_000, baudrate=100_000)
        payload = [0x12, 0x34, 0xAB, 0xCD, 0xA5, 0x5A, 0xFF, 0x00]
        received = []

        def tx_driver(dut):
            for byte in payload:
                yield dut.phy.sink.data.eq(byte)
                yield dut.phy.sink.valid.eq(1)
                yield
                while not (yield dut.phy.sink.ready):
                    yield
                yield dut.phy.sink.valid.eq(0)
                yield

        def rx_driver(dut):
            yield dut.phy.source.ready.eq(1)
            timeout = 0
            while len(received) < len(payload):
                if (yield dut.phy.source.valid) and (yield dut.phy.source.ready):
                    received.append((yield dut.phy.source.data))
                yield
                timeout += 1
                self.assertLess(timeout, 20_000, "RX stalled")

        run_simulation(dut, [tx_driver(dut), rx_driver(dut)])
        self.assertEqual(received, payload)

    def test_idle_line_no_spurious_rx(self):
        # With `tx` tied to `rx` and no data ever sent, the RX path must stay idle.
        dut = _LoopbackDUT(clk_freq=1_000_000, baudrate=100_000)

        def gen(dut):
            yield dut.phy.source.ready.eq(1)
            for _ in range(2_000):
                yield
                self.assertEqual((yield dut.phy.source.valid), 0)
        run_simulation(dut, gen(dut))


if __name__ == "__main__":
    unittest.main()
