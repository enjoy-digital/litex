#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import *
from litex.soc.interconnect import stream

from litex.soc.cores.uart import (
    UART,
    UARTCrossover,
    UARTPads,
    RS232PHY,
    RS232PHYRX,
    get_uart_core,
    get_uart_supported_names,
)


class _LoopbackDUT(LiteXModule):
    """A single RS232PHY with `pads.rx` tied back to `pads.tx` for self-loopback tests."""
    def __init__(self, clk_freq, baudrate):
        self.pads = UARTPads()
        self.phy  = RS232PHY(self.pads, clk_freq=clk_freq, baudrate=baudrate)
        self.comb += self.pads.rx.eq(self.pads.tx)


class _ErrorPHY(LiteXModule):
    def __init__(self):
        self.sink = stream.Endpoint([("data", 8)])
        self.source = stream.Endpoint([("data", 8)])
        self.rx_framing_error = Signal()
        self.rx_overflow = Signal()


class TestUART(unittest.TestCase):
    def test_receive_error_status_is_optional(self):
        dut = UART(RS232PHY(UARTPads(), 1_000_000))
        self.assertFalse(hasattr(dut, "_rx_errors"))
        with self.assertRaisesRegex(ValueError, "PHY"):
            UART(with_error_status=True)

    def test_receive_errors_from_serial_phy(self):
        pads = UARTPads()
        dut = UART(RS232PHY(pads, clk_freq=1_000_000, baudrate=62_500),
                   rx_fifo_depth=1, with_error_status=True)

        def drive(level, cycles):
            yield pads.rx.eq(level)
            for _ in range(cycles):
                yield

        def send(value, stop=1):
            yield from drive(0, 16)
            for bit in range(8):
                yield from drive((value >> bit) & 1, 16)
            yield from drive(stop, 16)
            yield from drive(1, 32)

        def gen():
            yield from drive(1, 32)
            yield from send(0x12)
            self.assertEqual((yield dut._rx_errors.fields.overflow), 0)
            # Do not drain the RX FIFO: subsequent valid frames must report actual loss.
            for value in [0x34, 0x56, 0x78]:
                yield from send(value)
            self.assertEqual((yield dut._rx_errors.fields.overflow), 1)
            self.assertEqual((yield dut._rx_errors.fields.framing), 0)
            yield from send(0xa5, stop=0)
            self.assertEqual((yield dut._rx_errors.fields.framing), 1)
            yield dut._rx_errors.wr_data.eq(1)
            yield dut._rx_errors.wr_stb.eq(1)
            yield
            yield dut._rx_errors.wr_stb.eq(0)
            yield
            self.assertEqual((yield dut._rx_errors.fields.framing), 0)
            self.assertEqual((yield dut._rx_errors.fields.overflow), 1)

        run_simulation(dut, gen())

    def test_receive_error_latching_and_cdc(self):
        for phy_cd, period in [("sys", 10), ("phy", 7), ("phy", 29)]:
            with self.subTest(phy_cd=phy_cd, period=period):
                phy = _ErrorPHY()
                dut = UART(phy, phy_cd=phy_cd, with_error_status=True)
                fired = Signal()
                cleared = Signal()

                def errors():
                    yield phy.rx_framing_error.eq(1)
                    yield
                    yield phy.rx_framing_error.eq(0)
                    yield phy.rx_overflow.eq(1)
                    yield
                    yield phy.rx_overflow.eq(0)
                    yield fired.eq(1)
                    while not (yield cleared):
                        yield

                def check():
                    while not (yield fired):
                        yield
                    for _ in range(20):
                        yield
                    self.assertEqual((yield dut._rx_errors.fields.framing), 1)
                    self.assertEqual((yield dut._rx_errors.fields.overflow), 1)
                    for mask, expected in [(0, (1, 1)), (1, (0, 1)), (2, (0, 0))]:
                        yield dut._rx_errors.wr_data.eq(mask)
                        yield dut._rx_errors.wr_stb.eq(1)
                        yield
                        yield dut._rx_errors.wr_stb.eq(0)
                        for _ in range(30):
                            yield
                        self.assertEqual(((yield dut._rx_errors.fields.framing),
                                          (yield dut._rx_errors.fields.overflow)), expected)
                    yield cleared.eq(1)

                generators = {"sys": [check()]}
                generators.setdefault(phy_cd, []).append(errors())
                run_simulation(dut, generators, clocks={"sys": 10, "phy": period})

    def test_new_receive_error_wins_over_clear(self):
        dut = UART(_ErrorPHY(), with_error_status=True)
        # Inject the event at the PHY/UART boundary to hit the exact clear cycle.
        def gen():
            yield dut.phy.rx_framing_error.eq(1)
            yield dut._rx_errors.wr_data.eq(1)
            yield dut._rx_errors.wr_stb.eq(1)
            yield
            yield dut._rx_errors.wr_stb.eq(0)
            yield dut.phy.rx_framing_error.eq(0)
            yield
            self.assertEqual((yield dut._rx_errors.fields.framing), 1)
        run_simulation(dut, gen())

    def test_rx_rejects_short_start_glitches(self):
        for glitch_length in [1, 2, 4]:
            with self.subTest(glitch_length=glitch_length):
                pads = UARTPads()
                dut = RS232PHYRX(pads, tuning_word=2**32//16)
                received = []

                @passive
                def monitor():
                    while True:
                        if (yield dut.source.valid):
                            received.append((yield dut.source.data))
                        yield

                def drive(level, cycles):
                    yield pads.rx.eq(level)
                    for _ in range(cycles):
                        yield

                def gen():
                    yield dut.source.ready.eq(1)
                    yield from drive(1, 20)
                    yield from drive(0, glitch_length)
                    yield from drive(1, 24)
                    # A real frame soon after the glitch must not be missed.
                    value = 0xa5
                    yield from drive(0, 16)
                    for bit in range(8):
                        yield from drive((value >> bit) & 1, 16)
                    yield from drive(1, 48)
                    self.assertEqual(received, [value])

                run_simulation(dut, [gen(), monitor()])

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
