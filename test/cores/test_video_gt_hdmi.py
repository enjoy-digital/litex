#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import random
import unittest
import importlib.util

from migen import ClockDomain, Instance, Module, Record, Signal, passive, run_simulation
from migen.fhdl.structure import _Assign

from litex.soc.cores.video import VideoGTHDMILane, VideoS7GTPHDMIPHY, VideoUSPGTHHDMIPHY

from test.cores.test_code_tmds import tmds_encode

# Tests --------------------------------------------------------------------------------------------

class TestVideoGTHDMI(unittest.TestCase):
    def test_lane(self):
        # Exercise changing data/control symbols across several TX clock phases. Check every
        # symbol, including its order within a 20-bit word, against the independent TMDS model.
        prng = random.Random(42)
        items = [(0, 0, 0)]*20
        items += [(prng.randrange(256), n % 4, int(n % 29 >= 4)) for n in range(1024)]
        expected = []
        disparity = 0
        for data, ctrl, de in items:
            encoded, disparity = tmds_encode(data, ctrl, de, disparity)
            expected.append(encoded)

        for phase in [1, 7, 13, 19]:
            with self.subTest(phase=phase):
                dut = VideoGTHDMILane("video", "tx")
                received = []

                def send():
                    yield dut.source.ready.eq(1)
                    for data, ctrl, de in items:
                        yield dut.d.eq(data)
                        yield dut.c.eq(ctrl)
                        yield dut.de.eq(de)
                        yield
                    for _ in range(40):
                        yield

                @passive
                def receive():
                    while True:
                        if (yield dut.source.valid):
                            word = yield dut.source.data
                            received.extend([word & 0x3ff, word >> 10])
                        yield

                run_simulation(dut, {"video": send(), "tx": receive()},
                    clocks={"video": 10, "tx": (20, phase)})
                # Ignore startup latency, then require the complete sequence without drops/repeats.
                start = next(n for n in range(40) if received[n:n+8] == expected[20:28])
                self.assertEqual(received[start:start+len(items)-20], expected[20:])

    @unittest.skipUnless(importlib.util.find_spec("liteiclink"), "LiteICLink is required")
    def test_gtp_clocking(self):
        layout = [(f"{name}_{polarity}", 1)
            for name in ["clk", "data0", "data1", "data2", "rx0", "rx1", "rx2"]
            for polarity in ["p", "n"]]
        for pixel_clk_freq, refclk_freq, polarity in [(148.5e6, 148.5e6, 1), (74.25e6, 148.5e6, 0)]:
            with self.subTest(pixel_clk_freq=pixel_clk_freq, polarity=polarity):
                dut = VideoS7GTPHDMIPHY(Record(layout), 148.5e6,
                    clk_freq    = pixel_clk_freq,
                    refclk      = Signal(),
                    refclk_freq = refclk_freq,
                    tx_polarity = polarity,
                )
                self.assertEqual(dut.pll.config["linerate"], 10*pixel_clk_freq)
                for color in ["r", "g", "b"]:
                    gtp = getattr(dut, f"gtp{color}")
                    self.assertEqual(gtp.gtp_params["i_TXPOLARITY"], polarity)
                    self.assertIs(gtp.cd_tx.clk, dut.gtpb.cd_tx.clk)
                    self.assertEqual(gtp.gtp_params["i_RXPD"], 0b11)
                fragment = dut.get_fragment()
                drivers = [stmt for stmt in fragment.comb
                    if isinstance(stmt, _Assign) and stmt.l is dut.pll.reset]
                self.assertEqual(len(drivers), 1)

    @unittest.skipUnless(importlib.util.find_spec("liteiclink"), "LiteICLink is required")
    def test_gtp_raw_tmds_alignment(self):
        # Observe the primitive TX ports, including the disparity bits, for all three lanes.
        # Shared-clock startup must preserve complete TMDS words and RGB alignment. Hard GT
        # serialization and TX-buffer latency still require hardware validation.
        layout = [(f"{name}_{polarity}", 1)
            for name in ["clk", "data0", "data1", "data2", "rx0", "rx1", "rx2"]
            for polarity in ["p", "n"]]
        prng = random.Random(763)
        items = [(prng.randrange(256), int(n % 29 >= 4)) for n in range(256)]
        expected = []
        disparity = 0
        for data, de in items:
            symbol, disparity = tmds_encode(data, 0, de, disparity)
            expected.append(symbol)

        for phase, reset_cycles in [(1, 0), (7, 21), (13, 40), (19, 61)]:
            with self.subTest(phase=phase, reset_cycles=reset_cycles):
                dut = VideoS7GTPHDMIPHY(Record(layout), 148.5e6, clock_domain="video")
                probe = Module()
                probe.clock_domains.cd_gtpb_tx = ClockDomain("gtpb_tx")
                probe.comb += dut._fragment.comb
                for color in ["r", "g", "b"]:
                    probe.submodules += getattr(dut, f"lane{color}")
                received = {color: [] for color in ["r", "g", "b"]}

                def send():
                    for n, (data, de) in enumerate(items):
                        yield probe.cd_gtpb_tx.rst.eq(n < reset_cycles)
                        yield dut.sink.de.eq(de)
                        for color in received:
                            yield getattr(dut.sink, color).eq(data)
                        yield
                    for _ in range(40):
                        yield

                @passive
                def receive():
                    while True:
                        for color in received:
                            params = getattr(dut, f"gtp{color}").gtp_params
                            data = yield params["i_TXDATA"]
                            bit8 = yield params["i_TXCHARDISPVAL"]
                            bit9 = yield params["i_TXCHARDISPMODE"]
                            self.assertEqual(data >> 16, 0)
                            self.assertEqual(bit8 >> 2, 0)
                            self.assertEqual(bit9 >> 2, 0)
                            for n in range(2):
                                received[color].append(((data >> (8*n)) & 0xff)
                                    | (((bit8 >> n) & 1) << 8) | (((bit9 >> n) & 1) << 9))
                        yield

                run_simulation(probe, {"video": send(), "gtpb_tx": receive()},
                    clocks={"video": 10, "gtpb_tx": (20, phase)})
                self.assertEqual(received["r"], received["g"])
                self.assertEqual(received["r"], received["b"])
                # Skip startup, which can drop pixels while the transmitter is held in reset.
                words = received["b"]
                start = next(n for n in range(len(words)-8) if words[n:n+8] == expected[100:108])
                self.assertEqual(words[start:start+len(items)-100], expected[100:])

    @unittest.skipUnless(importlib.util.find_spec("liteiclink"), "LiteICLink is required")
    def test_gth_clock_lane(self):
        layout = [(f"{name}_{polarity}", 1)
            for name in ["clk", "data0", "data1", "data2"] for polarity in ["p", "n"]]
        for pixel_clk_freq in [74.25e6, 148.5e6]:
            with self.subTest(pixel_clk_freq=pixel_clk_freq):
                dut = VideoUSPGTHHDMIPHY(Record(layout), 100e6, Signal(), 148.5e6,
                    clock_domain = "video",
                    clk_freq     = pixel_clk_freq,
                )
                self.assertEqual(dut.pll.config["linerate"], 10*pixel_clk_freq)
                for color in ["r", "g", "b"]:
                    gth = getattr(dut, f"gth{color}")
                    self.assertIs(gth.cd_tx.clk, dut.gthclk.cd_tx.clk)
                    self.assertEqual(gth.gth_params["i_RXPD"], 0b11)

                # Reconstruct the serial clock from the primitive's raw TX data/control inputs.
                # There must be two complete 50% duty-cycle pixel clocks in each TX word.
                probe = Module()
                probe.comb += dut._fragment.comb
                params = dut.gthclk.gth_params

                def check_clock():
                    yield
                    data  = yield params["i_TXDATA"]
                    ctrl0 = yield params["i_TXCTRL0"]
                    ctrl1 = yield params["i_TXCTRL1"]
                    bits = []
                    for n in range(2):
                        symbol = ((data >> (8*n)) & 0xff)
                        symbol |= ((ctrl0 >> n) & 1) << 8
                        symbol |= ((ctrl1 >> n) & 1) << 9
                        bits.extend((symbol >> bit) & 1 for bit in range(10))
                    self.assertEqual(bits, ([1]*5 + [0]*5)*2)

                run_simulation(probe, check_clock())
                fragment = dut.get_fragment()
                self.assertEqual(sum(isinstance(s, Instance) and s.of == "GTHE4_CHANNEL"
                    for s in fragment.specials), 4)
                drivers = [stmt for stmt in fragment.comb
                    if isinstance(stmt, _Assign) and stmt.l is dut.pll.reset]
                self.assertEqual(len(drivers), 1)


if __name__ == "__main__":
    unittest.main()
