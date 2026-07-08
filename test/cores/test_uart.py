#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import *

from litex.soc.cores.uart import (
    UART,
    UARTCrossover,
    UARTPads,
    RS232PHY,
    RS232PHYAutoSwap,
    RS232_IDLE,
    RS232_START,
    RS232_STOP,
    get_uart_core,
    get_uart_supported_names,
)


class _LoopbackDUT(LiteXModule):
    """A single RS232PHY with `pads.rx` tied back to `pads.tx` for self-loopback tests."""
    def __init__(self, clk_freq, baudrate):
        self.pads = UARTPads()
        self.phy  = RS232PHY(self.pads, clk_freq=clk_freq, baudrate=baudrate)
        self.comb += self.pads.rx.eq(self.pads.tx)


class _TristatePad:
    def __init__(self):
        self.o  = Signal(reset=RS232_IDLE)
        self.oe = Signal()
        self.i  = Signal(reset=RS232_IDLE)


class _AutoSwapPads:
    def __init__(self):
        self.tx = _TristatePad()
        self.rx = _TristatePad()


def _drive_uart_byte(line, byte, cycles_per_bit):
    yield line.eq(RS232_IDLE)
    for _ in range(cycles_per_bit):
        yield
    yield line.eq(RS232_START)
    for _ in range(cycles_per_bit):
        yield
    for bit in range(8):
        yield line.eq((byte >> bit) & 1)
        for _ in range(cycles_per_bit):
            yield
    yield line.eq(RS232_STOP)
    for _ in range(2*cycles_per_bit):
        yield


class TestUART(unittest.TestCase):
    def test_supported_uart_names_include_soc_modes(self):
        self.assertIn("crossover",          get_uart_supported_names())
        self.assertIn("crossover+uartbone", get_uart_supported_names())
        self.assertIn("jtag_uart",          get_uart_supported_names())
        self.assertIn("sim",                get_uart_supported_names())
        self.assertIn("stub",               get_uart_supported_names())
        self.assertIn("stream",             get_uart_supported_names())
        self.assertIn("uartbone",           get_uart_supported_names())
        self.assertIn("usb_acm",            get_uart_supported_names())

    def test_get_uart_core_builds_crossover(self):
        uart = get_uart_core("crossover", fifo_depth=8, rx_fifo_rx_we=True)

        self.assertIsInstance(uart, UARTCrossover)

    def test_get_uart_core_builds_regular_uart(self):
        uart = get_uart_core("serial", uart_pads=UARTPads(), clk_freq=1_000_000)

        self.assertIsInstance(uart, UART)
        self.assertTrue(hasattr(uart, "phy"))

    def test_get_uart_core_builds_auto_swap_regular_uart(self):
        uart = get_uart_core("serial", uart_pads=UARTPads(), clk_freq=1_000_000, with_auto_swap=True)

        self.assertIsInstance(uart, UART)
        self.assertIsInstance(uart.phy, RS232PHYAutoSwap)

    def test_get_uart_core_builds_stub_uart(self):
        uart = get_uart_core("stub")

        self.assertIsInstance(uart, UART)
        self.assertFalse(hasattr(uart, "phy"))

    def test_get_uart_core_returns_none_for_uartbone(self):
        self.assertIsNone(get_uart_core("uartbone"))

    def test_get_uart_core_validates_soc_supplied_dependencies(self):
        with self.assertRaisesRegex(ValueError, "platform"):
            get_uart_core("jtag_uart")
        with self.assertRaisesRegex(ValueError, "pads"):
            get_uart_core("sim")
        with self.assertRaisesRegex(ValueError, "pads"):
            get_uart_core("serial")
        with self.assertRaisesRegex(ValueError, "clk_freq"):
            get_uart_core("serial", uart_pads=UARTPads())

    def test_get_uart_core_rejects_auto_swap_on_soc_uart_modes(self):
        with self.assertRaisesRegex(ValueError, "serial"):
            get_uart_core("crossover", with_auto_swap=True)

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

    def test_auto_swap_idle_keeps_outputs_disabled(self):
        pads = _AutoSwapPads()
        dut  = RS232PHYAutoSwap(pads, clk_freq=1_000_000, baudrate=50_000)

        def gen():
            yield pads.tx.i.eq(RS232_IDLE)
            yield pads.rx.i.eq(RS232_IDLE)
            yield dut.source.ready.eq(1)
            for _ in range(2_000):
                self.assertEqual((yield dut.locked),       0)
                self.assertEqual((yield pads.tx.oe),       0)
                self.assertEqual((yield pads.rx.oe),       0)
                self.assertEqual((yield dut.source.valid), 0)
                yield

        run_simulation(dut, gen())

    def _run_auto_swap_receive_test(self, input_name, expected_swap):
        cycles_per_bit = 20
        byte           = 0x5a
        pads           = _AutoSwapPads()
        dut            = RS232PHYAutoSwap(pads, clk_freq=1_000_000, baudrate=50_000)
        input_pad      = getattr(pads, input_name)
        received       = []
        status         = {}

        def driver():
            yield pads.tx.i.eq(RS232_IDLE)
            yield pads.rx.i.eq(RS232_IDLE)
            for _ in range(cycles_per_bit):
                yield
            yield from _drive_uart_byte(input_pad.i, byte, cycles_per_bit)

        def monitor():
            yield dut.source.ready.eq(1)
            for _ in range(2_000):
                if (yield dut.source.valid):
                    received.append((yield dut.source.data))
                    yield
                    status["locked"] = (yield dut.locked)
                    status["swap"]   = (yield dut.swap)
                    status["tx_oe"]  = (yield pads.tx.oe)
                    status["rx_oe"]  = (yield pads.rx.oe)
                    return
                yield
            status["timeout"] = True

        run_simulation(dut, [driver(), monitor()])

        self.assertNotIn("timeout", status)
        self.assertEqual(received, [byte])
        self.assertEqual(status["locked"], 1)
        self.assertEqual(status["swap"],   expected_swap)
        self.assertEqual(status["tx_oe"],  int(not expected_swap))
        self.assertEqual(status["rx_oe"],  int(expected_swap))

    def test_auto_swap_detects_normal_wiring(self):
        self._run_auto_swap_receive_test(input_name="rx", expected_swap=0)

    def test_auto_swap_detects_swapped_wiring(self):
        self._run_auto_swap_receive_test(input_name="tx", expected_swap=1)

    def test_auto_swap_drops_tx_until_locked(self):
        pads = _AutoSwapPads()
        dut  = RS232PHYAutoSwap(pads, clk_freq=1_000_000, baudrate=50_000)

        def gen():
            yield pads.tx.i.eq(RS232_IDLE)
            yield pads.rx.i.eq(RS232_IDLE)
            yield dut.sink.data.eq(0xa5)
            yield dut.sink.valid.eq(1)
            for _ in range(100):
                self.assertEqual((yield dut.locked),     0)
                self.assertEqual((yield dut.sink.ready), 1)
                self.assertEqual((yield pads.tx.oe),     0)
                self.assertEqual((yield pads.rx.oe),     0)
                yield

        run_simulation(dut, gen())

    def test_idle_line_no_spurious_rx(self):
        # With `tx` tied to `rx` and no data ever sent, the RX path must stay idle.
        dut = _LoopbackDUT(clk_freq=1_000_000, baudrate=100_000)

        def gen(dut):
            yield dut.phy.source.ready.eq(1)
            for _ in range(2_000):
                yield
                self.assertEqual((yield dut.phy.source.valid), 0)
        run_simulation(dut, gen(dut))

    def test_long_burst_stable(self):
        # A 16-byte burst exercises the TX backpressure path: the producer holds
        # `sink.valid=1` for each byte and waits for `sink.ready` to pulse, which only happens
        # when the TX FSM finishes its current 10-bit frame. Any reordering or drop would
        # show up as a mismatch.
        dut      = _LoopbackDUT(clk_freq=1_000_000, baudrate=100_000)
        payload  = list(range(0x40, 0x40 + 16))
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
                self.assertLess(timeout, 100_000, "long burst stalled")

        run_simulation(dut, [tx_driver(dut), rx_driver(dut)])
        self.assertEqual(received, payload)


if __name__ == "__main__":
    unittest.main()
