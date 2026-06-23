#
# This file is part of LiteX.
#
# Copyright (c) 2022 Wolfgang Nagele <mail@wnagele.com>
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.led import LedChaser, WS2812, SK2812RGBW


# Serial LED Common ------------------------------------------------------------------------------

WS2812_OLD_TIMINGS = dict(
    trst =  50e-6*1.25,
    t0h  =   0.40e-6,
    t0l  =   0.85e-6,
    t1h  =   0.80e-6,
    t1l  =   0.45e-6,
)

WS2812_NEW_TIMINGS = dict(
    trst = 280e-6*1.25,
    t0h  =   0.40e-6,
    t0l  =   0.85e-6,
    t1h  =   0.80e-6,
    t1l  =   0.45e-6,
)

SK2812RGBW_TIMINGS = dict(
    trst = 80e-6*1.25,
    t0h  =  0.30e-6,
    t0l  =  0.90e-6,
    t1h  =  0.60e-6,
    t1l  =  0.60e-6,
)

class SerialLedTestMixin:
    error_margin = 150e-9

    @staticmethod
    def _to_bits(value, width):
        return [(value >> bit) & 1 for bit in reversed(range(width))]

    def _assert_pulse_time(self, cycles, expected_time, sys_clk_freq, name):
        actual_time = cycles/sys_clk_freq
        self.assertGreaterEqual(actual_time, expected_time - self.error_margin, name)
        self.assertLessEqual(   actual_time, expected_time + self.error_margin, name)

    def _capture_frame(self, led_cls, led_data, bit_width, sys_clk_freq=10e6, init=None, generators=None, **kwargs):
        pad = Signal()
        dut = led_cls(pad, len(led_data), sys_clk_freq, init=led_data if init is None else init, **kwargs)

        total_bits             = len(led_data)*bit_width
        target_final_low       = int(dut.trst*sys_clk_freq) + int(max(dut.t0l, dut.t1l)*sys_clk_freq)
        max_bit_cycles         = int(max(dut.t0h + dut.t0l, dut.t1h + dut.t1l)*sys_clk_freq) + 8
        max_simulation_cycles  = int(3*dut.trst*sys_clk_freq) + total_bits*max_bit_cycles + 100
        runs                   = []

        def gen():
            level     = (yield pad)
            run       = 0
            high_runs = 0

            for _ in range(max_simulation_cycles):
                value = (yield pad)
                if value == level:
                    run += 1
                else:
                    runs.append((level, run))
                    if level:
                        high_runs += 1
                    level = value
                    run   = 1

                if high_runs == total_bits and level == 0 and run >= target_final_low:
                    runs.append((level, run))
                    return
                yield

            self.fail("timed out waiting for serial LED frame")

        simulation_generators = [gen()]
        if generators is not None:
            simulation_generators += [generator(dut) for generator in generators]

        run_simulation(dut, simulation_generators)
        return dut, runs

    def _check_serial_led_frame(
        self, led_cls, led_data, bit_width, timings, sys_clk_freq=10e6, init=None, generators=None, **kwargs):
        dut, runs = self._capture_frame(
            led_cls        = led_cls,
            led_data       = led_data,
            bit_width      = bit_width,
            sys_clk_freq   = sys_clk_freq,
            init           = init,
            generators     = generators,
            **kwargs,
        )

        expected_bits = []
        for value in led_data:
            expected_bits.extend(self._to_bits(value, bit_width))

        for name, expected in timings.items():
            self.assertEqual(getattr(dut, name), expected)

        self.assertEqual(runs[0][0], 0)
        self.assertGreaterEqual(runs[0][1]/sys_clk_freq, timings["trst"])
        self.assertEqual(sum(1 for level, _ in runs if level), len(expected_bits))

        data_runs = runs[1:1 + 2*len(expected_bits)]
        self.assertEqual(len(data_runs), 2*len(expected_bits))

        decoded_bits = []
        for index, bit in enumerate(expected_bits):
            high_level, high_cycles = data_runs[2*index]
            low_level,  low_cycles  = data_runs[2*index + 1]
            self.assertEqual(high_level, 1, f"bit {index} high level")
            self.assertEqual(low_level,  0, f"bit {index} low level")

            if bit:
                high_time = timings["t1h"]
                low_time  = timings["t1l"]
            else:
                high_time = timings["t0h"]
                low_time  = timings["t0l"]

            self._assert_pulse_time(high_cycles, high_time, sys_clk_freq, f"bit {index} high time")
            decoded_bits.append(1 if high_cycles/sys_clk_freq > (timings["t0h"] + timings["t1h"])/2 else 0)

            if index != len(expected_bits) - 1:
                self._assert_pulse_time(low_cycles, low_time, sys_clk_freq, f"bit {index} low time")
            else:
                self.assertGreaterEqual(low_cycles/sys_clk_freq, low_time + timings["trst"] - self.error_margin)

        self.assertEqual(decoded_bits, expected_bits)
        return dut, runs

    def _wishbone_write(self, bus, adr, data, sel=0xf):
        yield bus.adr.eq(adr)
        yield bus.dat_w.eq(data)
        yield bus.sel.eq(sel)
        yield bus.we.eq(1)
        yield bus.cyc.eq(1)
        yield bus.stb.eq(1)

        for _ in range(16):
            if (yield bus.ack):
                break
            yield
        else:
            self.fail("timed out waiting for Wishbone write ack")

        yield bus.cyc.eq(0)
        yield bus.stb.eq(0)
        yield bus.we.eq(0)
        yield bus.sel.eq(0)
        yield bus.dat_w.eq(0)
        yield

    def _check_mmap_write_frame(self, led_cls, write_ops, expected_data, bit_width, timings, **kwargs):
        def write_gen(dut):
            for adr, data, sel in write_ops:
                yield from self._wishbone_write(dut.bus, adr, data, sel)

        self._check_serial_led_frame(
            led_cls    = led_cls,
            led_data   = expected_data,
            bit_width  = bit_width,
            timings    = timings,
            init       = [0]*len(expected_data),
            generators = [write_gen],
            **kwargs,
        )

    def _check_bus_master_reads(self, led_cls, led_data, sys_clk_freq=10e6, **kwargs):
        pad      = Signal()
        bus_base = 0x20000000
        dut      = led_cls(
            pad            = pad,
            nleds          = len(led_data),
            sys_clk_freq   = sys_clk_freq,
            bus_mastering  = True,
            bus_base       = bus_base,
            **kwargs,
        )
        reads = []

        def gen():
            for _ in range(int(2*dut.trst*sys_clk_freq) + len(led_data)*512):
                if (yield dut.bus.cyc) and (yield dut.bus.stb) and not (yield dut.bus.ack):
                    index = len(reads)
                    reads.append((
                        (yield dut.bus.adr),
                        (yield dut.bus.sel),
                        (yield dut.bus.we),
                    ))
                    yield dut.bus.dat_r.eq(led_data[index])
                    yield dut.bus.ack.eq(1)
                    yield
                    yield dut.bus.ack.eq(0)
                    yield dut.bus.dat_r.eq(0)
                    if len(reads) == len(led_data):
                        return
                yield

            self.fail("timed out waiting for bus-master reads")

        run_simulation(dut, gen())
        self.assertEqual(reads, [
            ((bus_base >> 2) + index, 0xf, 0)
            for index in range(len(led_data))
        ])


# WS2812 ----------------------------------------------------------------------------------------

class TestWS2812(unittest.TestCase, SerialLedTestMixin):
    def test_ws2812_old_sends_24bit_words_msb_first(self):
        self._check_serial_led_frame(
            led_cls      = WS2812,
            led_data     = [0xa5003c, 0x00ff81],
            bit_width    = 24,
            timings      = WS2812_OLD_TIMINGS,
            revision     = "old",
        )

    def test_ws2812_new_revision_uses_long_reset(self):
        _dut, runs = self._check_serial_led_frame(
            led_cls      = WS2812,
            led_data     = [0x800001],
            bit_width    = 24,
            timings      = WS2812_NEW_TIMINGS,
            revision     = "new",
        )
        self.assertGreaterEqual(runs[0][1]/10e6, WS2812_NEW_TIMINGS["trst"])

    def test_ws2812_single_led(self):
        self._check_serial_led_frame(
            led_cls      = WS2812,
            led_data     = [0xa5a5a5],
            bit_width    = 24,
            timings      = WS2812_OLD_TIMINGS,
            revision     = "old",
        )

    def test_ws2812_mmap_writes_drive_next_frame_and_ignore_top_byte(self):
        self._check_mmap_write_frame(
            led_cls       = WS2812,
            write_ops     = [
                (0, 0x12a5003c, 0xf),
                (1, 0xfe00ff81, 0xf),
            ],
            expected_data = [0xa5003c, 0x00ff81],
            bit_width     = 24,
            timings       = WS2812_OLD_TIMINGS,
            revision      = "old",
        )

    def test_ws2812_bus_master_reads_from_word_base(self):
        self._check_bus_master_reads(
            led_cls      = WS2812,
            led_data     = [0x010203, 0x040506],
            revision     = "old",
        )

    def test_ws2812_bus_master_requires_base(self):
        with self.assertRaises(ValueError):
            WS2812(Signal(), nleds=1, sys_clk_freq=10e6, bus_mastering=True, revision="old")

    def test_ws2812_rejects_invalid_parameters(self):
        with self.assertRaisesRegex(ValueError, "nleds"):
            WS2812(Signal(), nleds=0, sys_clk_freq=10e6, revision="old")
        with self.assertRaisesRegex(ValueError, "revision"):
            WS2812(Signal(), nleds=1, sys_clk_freq=10e6, revision="invalid")
        with self.assertRaisesRegex(ValueError, "aligned"):
            WS2812(Signal(), nleds=1, sys_clk_freq=10e6,
                bus_mastering=True, bus_base=0x20000002, revision="old")
        with self.assertRaisesRegex(ValueError, "sys_clk_freq"):
            WS2812(Signal(), nleds=1, sys_clk_freq=1e6, revision="old")


# SK2812RGBW -------------------------------------------------------------------------------------

class TestSK2812RGBW(unittest.TestCase, SerialLedTestMixin):
    def test_sk2812rgbw_sends_32bit_words_msb_first(self):
        self._check_serial_led_frame(
            led_cls      = SK2812RGBW,
            led_data     = [0x12345678, 0x80ff0001],
            bit_width    = 32,
            timings      = SK2812RGBW_TIMINGS,
        )

    def test_sk2812rgbw_single_led(self):
        self._check_serial_led_frame(
            led_cls      = SK2812RGBW,
            led_data     = [0xa5a55a5a],
            bit_width    = 32,
            timings      = SK2812RGBW_TIMINGS,
        )

    def test_sk2812rgbw_mmap_byte_lane_writes_drive_next_frame(self):
        self._check_mmap_write_frame(
            led_cls       = SK2812RGBW,
            write_ops     = [
                (0, 0x00000078, 0x1),
                (0, 0x00005600, 0x2),
                (0, 0x00340000, 0x4),
                (0, 0x12000000, 0x8),
                (1, 0x00000001, 0x1),
                (1, 0xff000000, 0x8),
            ],
            expected_data = [0x12345678, 0xff000001],
            bit_width     = 32,
            timings       = SK2812RGBW_TIMINGS,
        )

    def test_sk2812rgbw_bus_master_reads_from_word_base(self):
        self._check_bus_master_reads(
            led_cls      = SK2812RGBW,
            led_data     = [0x01020304, 0x05060708],
        )

    def test_sk2812rgbw_bus_master_requires_base(self):
        with self.assertRaises(ValueError):
            SK2812RGBW(Signal(), nleds=1, sys_clk_freq=10e6, bus_mastering=True)

    def test_sk2812rgbw_rejects_invalid_parameters(self):
        with self.assertRaisesRegex(ValueError, "nleds"):
            SK2812RGBW(Signal(), nleds=0, sys_clk_freq=10e6)
        with self.assertRaisesRegex(ValueError, "aligned"):
            SK2812RGBW(Signal(), nleds=1, sys_clk_freq=10e6,
                bus_mastering=True, bus_base=0x20000002)
        with self.assertRaisesRegex(ValueError, "sys_clk_freq"):
            SK2812RGBW(Signal(), nleds=1, sys_clk_freq=1e6)


# LedChaser ---------------------------------------------------------------------------------------

class TestLedChaser(unittest.TestCase):
    def test_csr_override_takes_control(self):
        # Writing to `_out` switches the core out of chaser mode and into control mode — pads
        # then track the CSR directly.
        pads = Signal(4)
        dut  = LedChaser(pads=pads, sys_clk_freq=1e6)

        def gen():
            # Before any CSR write, the core runs the chaser pattern; allow a few cycles.
            for _ in range(8):
                yield
            # Write a CSR value; on the next cycle the core switches mode.
            yield from dut._out.write(0b1010)
            yield
            yield
            self.assertEqual((yield pads), 0b1010)
            # And another value — pads track it.
            yield from dut._out.write(0b0101)
            yield
            yield
            self.assertEqual((yield pads), 0b0101)
        run_simulation(dut, gen())

    def test_polarity_inverts_output(self):
        # With polarity=1 the pads are the inverted mask of the leds signal.
        pads = Signal(4)
        dut  = LedChaser(pads=pads, sys_clk_freq=1e6, polarity=1)

        def gen():
            yield from dut._out.write(0b1010)
            yield
            yield
            # Inverted: pads = ~leds = 0b0101.
            self.assertEqual((yield pads), 0b0101)
            yield from dut._out.write(0b1111)
            yield
            yield
            self.assertEqual((yield pads), 0b0000)
        run_simulation(dut, gen())

    def test_chaser_pattern_advances(self):
        # Without a CSR write the LedChaser cycles a chaser pattern at a rate set by `period`.
        # Just confirm that the pad value changes over time (without asserting exact pattern).
        pads = Signal(4)
        # period=1e-3 at sys_clk_freq=1e6 → timer = 1000/(2*4) = 125 cycles per step.
        dut  = LedChaser(pads=pads, sys_clk_freq=1e6, period=1e-3)
        samples = set()

        def gen():
            for _ in range(2000):
                samples.add((yield pads))
                yield
        run_simulation(dut, gen())
        # Chaser should produce at least 2 distinct pad values.
        self.assertGreaterEqual(len(samples), 2)


if __name__ == "__main__":
    unittest.main()
