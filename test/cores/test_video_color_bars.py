#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Unit tests for litex.soc.cores.video.ColorBarsPattern.

Wired to a VideoTimingGenerator running a tiny custom timing so the simulation completes
quickly. We sample (r, g, b) on every DE-active pixel and verify each pixel falls into the
expected colour band.
"""

import unittest

from migen import *

from litex.gen import *

from litex.soc.cores.video import VideoTimingGenerator, ColorBarsPattern


# Tiny timing — hres=8, hres/8=1 → each colour bar is exactly 1 pixel wide. 8 bars per line.
TINY_TIMINGS = {
    "pix_clk"       : 1e6,
    "h_active"      : 8,
    "h_blanking"    : 4,
    "h_sync_offset" : 1,
    "h_sync_width"  : 2,
    "v_active"      : 4,
    "v_blanking"    : 4,
    "v_sync_offset" : 1,
    "v_sync_width"  : 1,
}

# Reference colour bars (matches video.py).
COLOR_BARS = [
    (0xff, 0xff, 0xff),  # White
    (0xff, 0xff, 0x00),  # Yellow
    (0x00, 0xff, 0xff),  # Cyan
    (0x00, 0xff, 0x00),  # Green
    (0xff, 0x00, 0xff),  # Purple
    (0xff, 0x00, 0x00),  # Red
    (0x00, 0x00, 0xff),  # Blue
    (0x00, 0x00, 0x00),  # Black
]


class _DUT(LiteXModule):
    def __init__(self):
        self.vtg  = VideoTimingGenerator(default_video_timings=TINY_TIMINGS)
        self.bars = ColorBarsPattern()
        self.comb += self.vtg.source.connect(self.bars.vtg_sink)


class TestColorBarsPattern(unittest.TestCase):
    def test_pixels_match_color_bars(self):
        dut          = _DUT()
        hres         = TINY_TIMINGS["h_active"]
        bar_width    = hres//8  # 1 in this config.
        active_per_frame = hres*TINY_TIMINGS["v_active"]

        captured = []  # list of (de, r, g, b) per cycle when source.valid & source.ready.

        def gen():
            yield dut.bars.source.ready.eq(1)
            # Run long enough to capture at least one full frame past initial sync settling.
            for _ in range(2_000):
                yield
                if (yield dut.bars.source.valid) and (yield dut.bars.source.ready):
                    captured.append((
                        (yield dut.bars.source.de),
                        (yield dut.bars.source.r),
                        (yield dut.bars.source.g),
                        (yield dut.bars.source.b),
                    ))
        run_simulation(dut, gen())

        # Keep only DE-active pixels (the bars only stride on de=1).
        active = [(r, g, b) for (de, r, g, b) in captured if de]
        # Take a clean window in the middle (skip startup transients).
        self.assertGreaterEqual(len(active), 2*active_per_frame, "not enough active pixels")

        # Inside that window, the per-line colour pattern must repeat: pixel n in a line gets
        # COLOR_BARS[n // bar_width].
        # Find a line boundary by scanning for the white→white reset across two adjacent lines.
        # Easier: just check that the captured stream is a prefix-aligned repetition of the
        # 8-pixel bar pattern starting from somewhere — slide a window to find the first line
        # start that matches `White, Yellow, Cyan, ...` exactly.
        expected_line = []
        for bar_idx in range(8):
            for _ in range(bar_width):
                expected_line.append(COLOR_BARS[bar_idx])
        # Find an alignment offset.
        offset = None
        for o in range(len(active) - len(expected_line)):
            if active[o:o + len(expected_line)] == expected_line:
                offset = o
                break
        self.assertIsNotNone(offset,
            f"no aligned colour-bar line found; first 16 pixels were {active[:16]}")

        # From the aligned offset, every consecutive `hres` pixels should be one full bar line.
        nlines = (len(active) - offset)//hres
        self.assertGreaterEqual(nlines, TINY_TIMINGS["v_active"], "not enough complete lines")
        for line in range(nlines):
            start = offset + line*hres
            self.assertEqual(active[start:start + hres], expected_line,
                f"line {line} mismatch")

    def test_disabled_holds_fsm_in_idle(self):
        # With enable=0 the FSM is held in reset; source.valid never asserts.
        dut = _DUT()

        def gen():
            yield dut.bars.enable.eq(0)
            yield dut.bars.source.ready.eq(1)
            for _ in range(200):
                yield
                self.assertEqual((yield dut.bars.source.valid), 0)
        run_simulation(dut, gen())


if __name__ == "__main__":
    unittest.main()
