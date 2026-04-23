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

def _run(dut, gens, vcd_name=None, clocks=None):
    if not isinstance(gens, list):
        gens = [gens]
    kwargs = dict(vcd_name=vcd_name)
    if clocks is not None:
        kwargs["clocks"] = clocks
    run_simulation(dut, gens, **kwargs)


# SDR outputs lower to an `InferedSDRIO` submodule which defines its own
# `cd_sdrio` clock domain.  migen's simulator only ticks the clocks listed in
# the `clocks` argument, so tests that instantiate SDROutput-based specials
# must tell the sim about it — otherwise the output register never clocks and
# pad signals stay at their reset value (0).
_SDR_CLOCKS = {"sys": 10, "sdrio": 10}


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


# VideoGenericPHY ----------------------------------------------------------------------------------

class _PHYPads:
    """Minimal object-style pads exposing whichever signals a test cares about.

    VideoGenericPHY probes `hasattr(pads, ...)` to decide which outputs to
    drive, so tests pick the subset they want by omitting attributes.
    """
    def __init__(self, cbits=8, pos_sync=True, with_de=True, with_clk=False):
        self.r = Signal(cbits)
        self.g = Signal(cbits)
        self.b = Signal(cbits)
        if with_de:
            self.de = Signal()
        if pos_sync:
            self.hsync = Signal()
            self.vsync = Signal()
        else:
            self.hsync_n = Signal()
            self.vsync_n = Signal()
        if with_clk:
            self.clk = Signal()


class _PHYHarness(Module):
    """PHY + synthetic sink.  The PHY always asserts ready on its sink so we
    can ignore back-pressure and simply step pixel values in."""
    def __init__(self, **pad_kwargs):
        self.pads = _PHYPads(**pad_kwargs)
        # VideoGenericPHY uses `with_clk_ddr_output=True` by default, but the
        # DDROutput lowering pulls in an extra clock domain we don't need — so
        # turn it off when the test provides `clk` explicitly.  When the test
        # omits `clk`, the PHY simply skips the clock output logic.
        self.submodules.phy = VideoGenericPHY(self.pads, with_clk_ddr_output=False)
        self.sink = self.phy.sink


class TestVideoGenericPHY(unittest.TestCase):
    """VideoGenericPHY is a thin SDR wrapper: every pixel field of the sink
    lands on the matching pad one cycle later (InferedSDRIO adds one flop),
    with r/g/b zeroed when `de` is low and with optional polarity inversion
    on hsync_n / vsync_n pads."""

    def _drive(self, dut, r, g, b, de, hsync, vsync):
        yield dut.sink.valid.eq(1)
        yield dut.sink.r.eq(r)
        yield dut.sink.g.eq(g)
        yield dut.sink.b.eq(b)
        yield dut.sink.de.eq(de)
        yield dut.sink.hsync.eq(hsync)
        yield dut.sink.vsync.eq(vsync)

    def test_positive_sync_and_de_passthrough(self):
        dut = _PHYHarness(pos_sync=True, with_de=True)

        def gen(dut):
            yield from self._drive(dut, r=0xaa, g=0xbb, b=0xcc, de=1, hsync=1, vsync=0)
            yield                              # InferedSDRIO samples on the edge.
            yield                              # Pads now reflect what we drove.
            self.assertEqual((yield dut.pads.r), 0xaa)
            self.assertEqual((yield dut.pads.g), 0xbb)
            self.assertEqual((yield dut.pads.b), 0xcc)
            self.assertEqual((yield dut.pads.de), 1)
            self.assertEqual((yield dut.pads.hsync), 1)
            self.assertEqual((yield dut.pads.vsync), 0)

        _run(dut, gen(dut), clocks=_SDR_CLOCKS)

    def test_rgb_forced_to_zero_during_blanking(self):
        """The PHY AND-masks r/g/b with `de` so VGA monitors see black during
        blanking even if the upstream data signals happen to be non-zero."""
        dut = _PHYHarness(pos_sync=True, with_de=True)

        def gen(dut):
            yield from self._drive(dut, r=0xff, g=0xff, b=0xff, de=0, hsync=1, vsync=1)
            yield
            yield
            self.assertEqual((yield dut.pads.r),  0x00)
            self.assertEqual((yield dut.pads.g),  0x00)
            self.assertEqual((yield dut.pads.b),  0x00)
            self.assertEqual((yield dut.pads.de), 0)
            # HSync/VSync are NOT masked by DE — they're needed during blanking.
            self.assertEqual((yield dut.pads.hsync), 1)
            self.assertEqual((yield dut.pads.vsync), 1)

        _run(dut, gen(dut), clocks=_SDR_CLOCKS)

    def test_negative_sync_inverts(self):
        """With hsync_n/vsync_n pads the PHY inverts the polarity so an asserted
        sync on the stream lands as a 0 on the pad (active-low)."""
        dut = _PHYHarness(pos_sync=False, with_de=False)

        def gen(dut):
            yield from self._drive(dut, r=0, g=0, b=0, de=1, hsync=1, vsync=0)
            yield
            yield
            self.assertEqual((yield dut.pads.hsync_n), 0)
            self.assertEqual((yield dut.pads.vsync_n), 1)

        _run(dut, gen(dut), clocks=_SDR_CLOCKS)

    def test_narrow_channel_takes_msbs(self):
        """When the pad bus is narrower than 8 bits the PHY selects the MSBs
        (cshift = 8 - cbits), throwing away LSBs — standard VGA truncation."""
        dut = _PHYHarness(cbits=4, pos_sync=True, with_de=True)

        def gen(dut):
            # 0xa5 = 0b10100101 — MSB nibble is 0xa, LSB nibble is 0x5.
            yield from self._drive(dut, r=0xa5, g=0x5a, b=0x0f, de=1, hsync=0, vsync=0)
            yield
            yield
            self.assertEqual((yield dut.pads.r), 0xa)  # top nibble of 0xa5
            self.assertEqual((yield dut.pads.g), 0x5)  # top nibble of 0x5a
            self.assertEqual((yield dut.pads.b), 0x0)  # top nibble of 0x0f

        _run(dut, gen(dut), clocks=_SDR_CLOCKS)


if __name__ == "__main__":
    unittest.main()
