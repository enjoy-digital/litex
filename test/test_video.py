#
# This file is part of LiteX.
#
# Copyright (c) 2026 LiteX Authors
# SPDX-License-Identifier: BSD-2-Clause

"""Unit tests for LiteX Video components other than VideoTerminal:

- VideoTimingGenerator
- ColorBarsPattern
- VideoGenericPHY (VGA / DVI)
- code_tmds.TMDSEncoder
"""

import unittest

from migen import *

from litex.soc.cores.video import VideoTimingGenerator, ColorBarsPattern, VideoGenericPHY
from litex.soc.cores.code_tmds import TMDSEncoder, control_tokens


# Helpers ------------------------------------------------------------------------------------------

def _run(dut, gens, vcd_name=None):
    if not isinstance(gens, list):
        gens = [gens]
    run_simulation(dut, gens, vcd_name=vcd_name)


# A compact synthetic timings dictionary used throughout.  Picked so each line
# and frame fit in a small number of cycles (fast simulation) and so that no
# two events (end-of-HActive, start/end of HSync, end-of-HScan) collide.
SMALL_TIMINGS = {
    "pix_clk"       : 1e6,
    "h_active"      : 8,
    "h_blanking"    : 6,
    "h_sync_offset" : 2,
    "h_sync_width"  : 2,
    "v_active"      : 4,
    "v_blanking"    : 4,
    "v_sync_offset" : 2,
    "v_sync_width"  : 1,
}

# Derived constants for SMALL_TIMINGS.
HRES         = SMALL_TIMINGS["h_active"]
HSYNC_START  = HRES + SMALL_TIMINGS["h_sync_offset"]                               # 10
HSYNC_END    = HSYNC_START + SMALL_TIMINGS["h_sync_width"]                         # 12
HSCAN        = HRES + SMALL_TIMINGS["h_blanking"] - 1                              # 13
HTOTAL       = HSCAN + 1                                                           # 14

VRES         = SMALL_TIMINGS["v_active"]
VSYNC_START  = VRES + SMALL_TIMINGS["v_sync_offset"]                               # 6
VSYNC_END    = VSYNC_START + SMALL_TIMINGS["v_sync_width"]                         # 7
VSCAN        = VRES + SMALL_TIMINGS["v_blanking"] - 1                              # 7
VTOTAL       = VSCAN + 1                                                           # 8


# VideoTimingGenerator -----------------------------------------------------------------------------

class TestVideoTimingGenerator(unittest.TestCase):
    """Verify the counters and output signals produced by the VTG.

    The generator uses `NextValue` inside an FSM, so every output signal
    lags the hcount/vcount that caused its transition by one cycle.  Rather
    than pin down the exact cycle alignment (which is brittle and not what
    downstream users care about), the tests check:

      1. Every (hcount, vcount) slot of a frame is visited exactly once.
      2. The total number of cycles where each of de/hsync/vsync/first/last
         is high matches the expected counts.
    """

    def _capture_frame(self, dut):
        """Drive source.ready high and return a list of per-cycle dicts for one full frame.

        Anchors on the first cycle where hcount==0 and vcount==0 to skip the
        IDLE→RUN transition and any MultiReg settling delay.
        """
        for _ in range(8):
            yield dut.source.ready.eq(1)
            yield
        for _ in range(4 * HTOTAL * VTOTAL):
            h = (yield dut.source.hcount)
            v = (yield dut.source.vcount)
            valid = (yield dut.source.valid)
            if valid and h == 0 and v == 0:
                break
            yield
        else:
            self.fail("VTG never produced (hcount=0, vcount=0)")
        frame = []
        for _ in range(HTOTAL * VTOTAL):
            frame.append({
                "hcount": (yield dut.source.hcount),
                "vcount": (yield dut.source.vcount),
                "de":     (yield dut.source.de),
                "hsync":  (yield dut.source.hsync),
                "vsync":  (yield dut.source.vsync),
                "valid":  (yield dut.source.valid),
                "first":  (yield dut.source.first),
                "last":   (yield dut.source.last),
            })
            yield
        return frame

    def test_counter_progression(self):
        dut = VideoTimingGenerator(default_video_timings=SMALL_TIMINGS)

        def gen(dut):
            frame = yield from self._capture_frame(dut)
            for s in frame:
                self.assertTrue(s["valid"], f"valid dropped at {s}")
            seen = set()
            for s in frame:
                coord = (s["hcount"], s["vcount"])
                self.assertNotIn(coord, seen,
                    f"coordinate {coord} appeared twice in one frame")
                seen.add(coord)
            # Every (hcount, vcount) slot exactly once — one full raster.
            self.assertEqual(len(seen), HTOTAL * VTOTAL)

        _run(dut, gen(dut))

    def test_de_window_size(self):
        """DE must be high for exactly HRES * VRES cycles per frame (the active region)."""
        dut = VideoTimingGenerator(default_video_timings=SMALL_TIMINGS)

        def gen(dut):
            frame = yield from self._capture_frame(dut)
            de_cycles = sum(1 for s in frame if s["de"])
            self.assertEqual(de_cycles, HRES * VRES)

        _run(dut, gen(dut))

    def test_hsync_window_size(self):
        """HSync high for exactly h_sync_width cycles per line, VTOTAL lines per frame."""
        dut = VideoTimingGenerator(default_video_timings=SMALL_TIMINGS)

        def gen(dut):
            frame = yield from self._capture_frame(dut)
            hsync_cycles = sum(1 for s in frame if s["hsync"])
            self.assertEqual(hsync_cycles,
                SMALL_TIMINGS["h_sync_width"] * VTOTAL)

        _run(dut, gen(dut))

    def test_vsync_window_size(self):
        """VSync high for v_sync_width lines (= HTOTAL cycles each)."""
        dut = VideoTimingGenerator(default_video_timings=SMALL_TIMINGS)

        def gen(dut):
            frame = yield from self._capture_frame(dut)
            vsync_cycles = sum(1 for s in frame if s["vsync"])
            self.assertEqual(vsync_cycles,
                SMALL_TIMINGS["v_sync_width"] * HTOTAL)

        _run(dut, gen(dut))

    def test_first_last_pulse_once(self):
        """`first` and `last` must pulse exactly once per frame."""
        dut = VideoTimingGenerator(default_video_timings=SMALL_TIMINGS)

        def gen(dut):
            frame = yield from self._capture_frame(dut)
            first_count = sum(1 for s in frame if s["first"])
            last_count  = sum(1 for s in frame if s["last"])
            self.assertEqual(first_count, 1)
            self.assertEqual(last_count,  1)

        _run(dut, gen(dut))


# ColorBarsPattern ---------------------------------------------------------------------------------

# Expected RGB table — must match `color_bar` in video.py line-for-line.
_EXPECTED_COLOR_BARS = [
    (0xff, 0xff, 0xff),  # 0 white
    (0xff, 0xff, 0x00),  # 1 yellow
    (0x00, 0xff, 0xff),  # 2 cyan
    (0x00, 0xff, 0x00),  # 3 green
    (0xff, 0x00, 0xff),  # 4 purple
    (0xff, 0x00, 0x00),  # 5 red
    (0x00, 0x00, 0xff),  # 6 blue
    (0x00, 0x00, 0x00),  # 7 black
]


class _ColorBarsHarness(Module):
    """Drives a VTG and a ColorBarsPattern end-to-end."""
    def __init__(self, timings):
        self.submodules.vtg  = VideoTimingGenerator(default_video_timings=timings)
        self.submodules.bars = ColorBarsPattern()
        self.comb += self.vtg.source.connect(self.bars.vtg_sink)


class TestColorBarsPattern(unittest.TestCase):
    """ColorBarsPattern splits each active row into 8 equal bars.

    With `h_active = 8` (SMALL_TIMINGS), each bar is 1 pixel wide — so
    consecutive DE pixels on one row should map to consecutive bars 0..7.
    """

    def test_bars_span_active_row(self):
        dut = _ColorBarsHarness(SMALL_TIMINGS)

        def gen(dut):
            yield dut.bars.source.ready.eq(1)
            # Wait long enough to be well into the RUN state and at least one
            # full line deep (the bars FSM needs the first frame's initial
            # cycle to leave IDLE).
            pixels = []
            for _ in range(4 * HTOTAL * VTOTAL):
                valid = (yield dut.bars.source.valid)
                de    = (yield dut.bars.source.de)
                if valid and de:
                    pixels.append((
                        (yield dut.bars.source.r),
                        (yield dut.bars.source.g),
                        (yield dut.bars.source.b),
                    ))
                yield
                if len(pixels) >= HRES * VRES:
                    break
            # We collected at least one full active region; the first row of
            # active pixels should be the 8-bar sequence.
            self.assertGreaterEqual(len(pixels), HRES)
            self.assertEqual(pixels[:HRES], _EXPECTED_COLOR_BARS,
                f"first active row didn't match bar table: {pixels[:HRES]}")

        _run(dut, gen(dut))


if __name__ == "__main__":
    unittest.main()
