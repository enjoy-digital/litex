#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Unit tests for litex.soc.cores.video.

Scope: just VideoTimingGenerator. The rest of video.py (framebuffer, overlay, terminal, palette,
DVI/HDMI PHYs) is large and interacts with several clock domains — out of scope here.
"""

import unittest

from migen import *

from litex.soc.cores.video import VideoTimingGenerator


# A tiny custom timing. h_active=8, h_blanking=4 → 12 pixels per line; v_active=4, v_blanking=4
# → 8 lines per frame; 96 cycles per full frame. v_blanking is sized so that vsync_end falls
# strictly before vscan (otherwise vsync would never be cleared before vcount wraps).
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


def derive_markers(vt):
    """Mirror the reset-value arithmetic the VideoTimingGenerator does internally."""
    hres        = vt["h_active"]
    hsync_start = vt["h_active"] + vt["h_sync_offset"]
    hsync_end   = vt["h_active"] + vt["h_sync_offset"] + vt["h_sync_width"]
    hscan       = vt["h_active"] + vt["h_blanking"] - 1
    vres        = vt["v_active"]
    vsync_start = vt["v_active"] + vt["v_sync_offset"]
    vsync_end   = vt["v_active"] + vt["v_sync_offset"] + vt["v_sync_width"]
    vscan       = vt["v_active"] + vt["v_blanking"] - 1
    return dict(hres=hres, hsync_start=hsync_start, hsync_end=hsync_end, hscan=hscan,
                vres=vres, vsync_start=vsync_start, vsync_end=vsync_end, vscan=vscan)


def sample_frame(vt, ncycles):
    dut     = VideoTimingGenerator(default_video_timings=vt)
    samples = []

    def gen():
        yield dut.source.ready.eq(1)
        # Enable CSR reset=1, so no need to write.
        # Let the MultiReg synchronisers settle before we start recording.
        for _ in range(8):
            yield
        for _ in range(ncycles):
            yield
            samples.append({
                "valid":  (yield dut.source.valid),
                "de":     (yield dut.source.de),
                "hsync":  (yield dut.source.hsync),
                "vsync":  (yield dut.source.vsync),
                "hcount": (yield dut.source.hcount),
                "vcount": (yield dut.source.vcount),
            })
    run_simulation(dut, gen())
    return samples


class TestVideoTimingGenerator(unittest.TestCase):
    def test_hres_and_vres_from_resets(self):
        # The CSR reset values match the timing dict; verify hres/vres signals on the source
        # carry the expected values.
        m = derive_markers(TINY_TIMINGS)
        dut = VideoTimingGenerator(default_video_timings=TINY_TIMINGS)

        def gen():
            yield dut.source.ready.eq(1)
            for _ in range(20):
                yield
            self.assertEqual((yield dut.source.hres), m["hres"])
            self.assertEqual((yield dut.source.vres), m["vres"])
        run_simulation(dut, gen())

    def test_de_active_count_per_line(self):
        # After the sync pipeline settles, `de` must be high for exactly `hres` cycles on each
        # of `vres` consecutive lines.
        m = derive_markers(TINY_TIMINGS)
        line_len  = m["hscan"] + 1
        frame_len = line_len*(m["vscan"] + 1)
        # Sample two frames so we definitely catch one clean one.
        samples = sample_frame(TINY_TIMINGS, ncycles=3*frame_len + 30)

        # Find a vcount=0, hcount=0 to mark the start of a clean frame.
        start = None
        for i, s in enumerate(samples):
            if s["hcount"] == 0 and s["vcount"] == 0:
                start = i
                break
        self.assertIsNotNone(start, "never saw a frame start")

        de_count = sum(1 for s in samples[start:start + frame_len] if s["de"])
        self.assertEqual(de_count, m["hres"]*m["vres"])

    def test_hsync_window(self):
        # Within one line, hsync must be 1 for exactly (hsync_end - hsync_start) cycles.
        m = derive_markers(TINY_TIMINGS)
        line_len = m["hscan"] + 1
        samples  = sample_frame(TINY_TIMINGS, ncycles=4*line_len + 20)

        # Find a line start.
        start = None
        for i, s in enumerate(samples):
            if s["hcount"] == 0 and s["vcount"] == 1:  # pick a line in the middle of a frame
                start = i
                break
        self.assertIsNotNone(start)
        line = samples[start:start + line_len]

        hsync_cycles = sum(1 for s in line if s["hsync"])
        self.assertEqual(hsync_cycles, TINY_TIMINGS["h_sync_width"])

    def test_vsync_window(self):
        # Over a full frame, vsync must be 1 for exactly (v_sync_width * line_len) cycles.
        m = derive_markers(TINY_TIMINGS)
        line_len  = m["hscan"] + 1
        frame_len = line_len*(m["vscan"] + 1)
        samples   = sample_frame(TINY_TIMINGS, ncycles=3*frame_len + 20)

        start = None
        for i, s in enumerate(samples):
            if s["hcount"] == 0 and s["vcount"] == 0:
                start = i
                break
        self.assertIsNotNone(start)

        vsync_cycles = sum(1 for s in samples[start:start + frame_len] if s["vsync"])
        self.assertEqual(vsync_cycles, TINY_TIMINGS["v_sync_width"]*line_len)


if __name__ == "__main__":
    unittest.main()
