#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.esc import ESCDShot, D150Timings


# DShot frame math (per the reference in the core docstring): the 16-bit frame sent on the wire
# is (11-bit throttle | 1-bit telemetry | 4-bit CRC), MSB first.
def encode_dshot_frame(throttle, telemetry=0):
    data = ((throttle & 0x7ff) << 1) | (telemetry & 1)
    crc  = (data ^ (data >> 4) ^ (data >> 8)) & 0x0f
    return (data << 4) | crc


def decode_one_frame_after_gap(samples, t1h_cycles, t0h_cycles, period_cycles):
    """Find the inter-frame GAP (a long low run) in `samples` and decode the 16 bits that follow.

    Necessary because the CSR write happens after the very first frame has already started —
    so the first frame out of the DUT carries the reset value (0), not the value we just wrote.
    """
    gap_threshold = period_cycles*4  # GAP is 16*period; any run ≥ 4*period is the gap.
    threshold     = (t0h_cycles + t1h_cycles) / 2

    # Find the end of a gap.
    i       = 0
    low_run = 0
    while i < len(samples):
        if samples[i] == 0:
            low_run += 1
        else:
            if low_run >= gap_threshold:
                break
            low_run = 0
        i += 1
    assert i < len(samples), "no gap found — increase sample window"

    bits = []
    while len(bits) < 16 and i < len(samples):
        while i < len(samples) and samples[i] == 0:
            i += 1
        high = 0
        while i < len(samples) and samples[i] == 1:
            high += 1
            i += 1
        bits.append(1 if high > threshold else 0)
    return bits


def frame_to_bits(value16):
    return [(value16 >> (15 - i)) & 1 for i in range(16)]


class TestESCDShot(unittest.TestCase):
    # Pick a tiny sys_clk_freq so the simulated frame fits in a few hundred cycles. The ratios
    # (T1H/T0H/period) are the thing being tested; the absolute cycle count doesn't matter as
    # long as it's big enough to decode unambiguously.
    SYS_CLK_FREQ = 2e-6  # int(t1h * sys_clk_freq) = 10 cycles for D150 T1H.

    @classmethod
    def setUpClass(cls):
        t = D150Timings()
        t.compute()
        cls.t1h_cycles = int(t.t1h*cls.SYS_CLK_FREQ)
        cls.t0h_cycles = int(t.t0h*cls.SYS_CLK_FREQ)
        cls.period_cyc = int(t.period*cls.SYS_CLK_FREQ)

    def _sample_frame(self, frame_value, ncycles=1500):
        pad     = Signal()
        dut     = ESCDShot(pad, self.SYS_CLK_FREQ, protocol="D150")
        samples = []

        def gen():
            yield from dut.value.write(frame_value)
            for _ in range(ncycles):
                yield
                samples.append((yield pad))
        run_simulation(dut, gen())
        return samples

    def test_frame_zero(self):
        # Throttle=0 + telemetry=0 + CRC=0 → all bits zero → only T0H-length pulses.
        samples = self._sample_frame(0)
        bits    = decode_one_frame_after_gap(samples, self.t1h_cycles, self.t0h_cycles, self.period_cyc)
        self.assertEqual(bits[:16], [0]*16)

    def test_frame_throttle_value(self):
        # A specific mid-range throttle command (matches the example in the core docstring).
        frame = encode_dshot_frame(throttle=1000, telemetry=0)
        samples = self._sample_frame(frame)
        bits    = decode_one_frame_after_gap(samples, self.t1h_cycles, self.t0h_cycles, self.period_cyc)
        self.assertEqual(bits[:16], frame_to_bits(frame))

    def test_frame_with_telemetry(self):
        frame = encode_dshot_frame(throttle=500, telemetry=1)
        samples = self._sample_frame(frame)
        bits    = decode_one_frame_after_gap(samples, self.t1h_cycles, self.t0h_cycles, self.period_cyc)
        self.assertEqual(bits[:16], frame_to_bits(frame))

    def test_frame_all_ones(self):
        # Every data bit high; CRC computed over that pattern.
        frame = encode_dshot_frame(throttle=0x7ff, telemetry=1)
        samples = self._sample_frame(frame)
        bits    = decode_one_frame_after_gap(samples, self.t1h_cycles, self.t0h_cycles, self.period_cyc)
        self.assertEqual(bits[:16], frame_to_bits(frame))


if __name__ == "__main__":
    unittest.main()
