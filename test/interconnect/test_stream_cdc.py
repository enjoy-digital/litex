#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import logging

from migen import *
from migen.sim import passive

from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.stream_cdc import ClockDomainCrossingConverter

LOGGER = "ClockDomainCrossingConverter"

# Helpers ------------------------------------------------------------------------------------------

def _even(x):
    return max(2, 2*int(round(x/2)))

def _clocks(cd_from, cd_to, ratio):
    """ratio = f_to/f_from (cd_from at period 1000), with a phase offset on cd_to."""
    if cd_from == cd_to:
        return {cd_from: 1000}
    period = _even(1000/ratio)
    return {cd_from: 1000, cd_to: (period, period//3)}

def _run_units(dut, sink, source, unit, cd_from, cd_to, ratio, cycles=400, common_rst_cdc=None):
    """Stream consecutive `unit`-bit values (packed into the sink/source data words) through `dut`,
    with an always-valid writer in cd_from and an always-ready reader in cd_to.

    common_rst_cdc: ClockDomainCrossing built with_common_rst; its intermediate clock domains are
    driven combinatorially, which the simulator doesn't follow, so they get their own clocks.

    Returns (units received in order, share of cd_to cycles with source.valid after warm-up).
    """
    n_from = len(sink.data)//unit
    n_to   = len(source.data)//unit

    class Top(LiteXModule):
        def __init__(self):
            for cd in sorted({cd_from, cd_to}):
                setattr(self.clock_domains, f"cd_{cd}", ClockDomain(cd))
            self.dut = dut
            count = Signal(32)
            self.comb += [
                sink.valid.eq(1),
                sink.data.eq(Cat(*[(count + i)[:unit] for i in range(n_from)])),
                source.ready.eq(1),
            ]
            # Writer counter in cd_from.
            sync  = getattr(self.sync, cd_from)
            sync += If(sink.ready, count.eq(count + n_from))

    top = Top()

    log = []
    def reader():
        for _ in range(cycles):
            log.append(((yield source.valid), (yield source.data)))
            yield

    @passive
    def idle():
        while True:
            yield

    generators = {cd_to: reader()}
    if cd_from != cd_to:
        generators[cd_from] = idle()
    clocks = _clocks(cd_from, cd_to, ratio)
    if common_rst_cdc is not None:
        clocks[f"from{common_rst_cdc.duid}"] = clocks[cd_from]
        clocks[f"to{common_rst_cdc.duid}"]   = clocks[cd_to]
    run_simulation(top, generators, clocks=clocks)

    units = []
    for valid, data in log:
        if valid:
            units += [(data >> (unit*i)) & (2**unit - 1) for i in range(n_to)]
    first  = next(i for i, (v, _) in enumerate(log) if v)
    steady = log[first + 32:]
    return units, sum(v for v, _ in steady)/len(steady)

# AsyncFIFO full-rate depth ------------------------------------------------------------------------

class TestAsyncFIFODepth(unittest.TestCase):
    def test_full_rate_depth(self):
        # Pointer round trip of ~2*sync_stages + 1 cycles, rounded up to a power of two.
        self.assertEqual(stream.async_fifo_full_rate_depth(), 8)
        self.assertEqual(stream.async_fifo_full_rate_depth(buffered=True), 8)
        self.assertEqual(stream.async_fifo_full_rate_depth(sync_stages=3), 8)
        self.assertEqual(stream.async_fifo_full_rate_depth(sync_stages=4), 16)

    def test_default_depth(self):
        self.assertEqual(stream.AsyncFIFO([("data", 8)]).fifo.depth, 8)
        self.assertEqual(stream.AsyncFIFO([("data", 8)], buffered=True).fifo.depth, 8)
        self.assertEqual(stream.AsyncFIFO([("data", 8)], depth=4).fifo.depth, 4)

    def test_depth_ok(self):
        self.assertTrue( stream.async_fifo_depth_ok(8, ratio=1.0))
        self.assertTrue( stream.async_fifo_depth_ok(4, ratio=0.5))
        self.assertFalse(stream.async_fifo_depth_ok(4, ratio=0.8))
        self.assertTrue( stream.async_fifo_depth_ok(4, ratio=1.0, utilization=0.25))

    def _throughput(self, depth, ratio):
        # Fast writer in "write", slower reader in "read" (ratio = f_read/f_write).
        cdc = stream.ClockDomainCrossing([("data", 16)], cd_from="write", cd_to="read", depth=depth)
        _, throughput = _run_units(cdc, cdc.sink, cdc.source, 16, "write", "read", ratio)
        return throughput

    def test_default_depth_is_full_rate(self):
        # Regression for bubbles above a ~2/3 clock ratio with depth 4.
        for ratio in [0.5, 0.8, 1.0]:
            with self.subTest(ratio=ratio):
                self.assertEqual(self._throughput(None, ratio), 1.0)

    def test_depth_4_bubbles_above_two_thirds(self):
        self.assertEqual(self._throughput(4, 0.5), 1.0)
        for ratio in [0.8, 1.0]:
            with self.subTest(ratio=ratio):
                self.assertLess(self._throughput(4, ratio), 0.9)

# ClockDomainCrossingConverter: choices ------------------------------------------------------------

class TestClockDomainCrossingConverterChoices(unittest.TestCase):
    def _cdc(self, width_from, width_to, clk_freq_from=None, clk_freq_to=None, **kwargs):
        return ClockDomainCrossingConverter([("data", width_from)], [("data", width_to)],
            cd_from       = "sys",
            cd_to         = "video",
            clk_freq_from = clk_freq_from,
            clk_freq_to   = clk_freq_to,
            **kwargs)

    def test_down_conversion_side(self):
        # Wide DMA words in sys, narrow pixels in video.
        self.assertEqual(self._cdc(64, 16, 100e6,  50e6).convert_in, "from")  # Sys fast enough.
        self.assertEqual(self._cdc(64, 16, 100e6, 100e6).convert_in, "from")
        self.assertEqual(self._cdc(64, 16, 100e6, 120e6).convert_in, "to")    # Sys too slow.
        self.assertEqual(self._cdc(64, 16).convert_in, "to")                  # No frequencies.
        self.assertEqual(self._cdc(64, 16, 100e6, 90e6, rate_margin=1.2).convert_in, "to")

    def test_up_conversion_side(self):
        # Narrow words in sys, wide words in video.
        self.assertEqual(self._cdc(16, 64, 100e6, 150e6).convert_in, "to")
        self.assertEqual(self._cdc(16, 64, 100e6,  50e6).convert_in, "from")
        self.assertEqual(self._cdc(16, 64).convert_in, "from")

    def test_no_conversion(self):
        self.assertIsNone(self._cdc(32, 32, 100e6, 50e6).convert_in)

    def test_crossing_width(self):
        self.assertEqual(len(self._cdc(64, 16, 100e6, 50e6).cdc.sink.data), 16)
        self.assertEqual(len(self._cdc(64, 16, 100e6, 150e6).cdc.sink.data), 64)

    def test_default_depth(self):
        self.assertEqual(self._cdc(64, 16).depth, 8)
        self.assertEqual(self._cdc(64, 16, depth=16).depth, 16)

# ClockDomainCrossingConverter: warnings -----------------------------------------------------------

class TestClockDomainCrossingConverterWarnings(unittest.TestCase):
    def _cdc(self, clk_freq_to, **kwargs):
        return ClockDomainCrossingConverter([("data", 64)], [("data", 16)],
            cd_from="sys", cd_to="video", clk_freq_from=100e6, clk_freq_to=clk_freq_to, **kwargs)

    def test_small_depth_warns(self):
        with self.assertLogs(LOGGER, logging.WARNING) as logs:
            self._cdc(80e6, depth=4)
        self.assertIn("depth 4", logs.output[0])

    def test_slow_converter_side_warns(self):
        with self.assertLogs(LOGGER, logging.WARNING) as logs:
            self._cdc(120e6, convert_in="from")
        self.assertIn("can't sustain", logs.output[0])

    def test_no_warning_when_full_rate(self):
        for kwargs in [
            dict(clk_freq_to= 80e6),                   # Default depth.
            dict(clk_freq_to= 50e6, depth=4),          # Low clock ratio.
            dict(clk_freq_to=120e6, depth=4),          # Crossing at the wide width: 1 word / 4 pixels.
            dict(clk_freq_to= 80e6, convert_in="from"),
        ]:
            with self.subTest(**kwargs):
                with self.assertNoLogs(LOGGER, logging.WARNING):
                    self._cdc(**kwargs)

# ClockDomainCrossingConverter: datapath -----------------------------------------------------------

class TestClockDomainCrossingConverterData(unittest.TestCase):
    def _stream(self, width_from, width_to, ratio, unit, cd_to="video", **kwargs):
        clk_freq_to = 100e6*ratio
        dut = ClockDomainCrossingConverter([("data", width_from)], [("data", width_to)],
            cd_from="sys", cd_to=cd_to, clk_freq_from=100e6, clk_freq_to=clk_freq_to, **kwargs)
        units, throughput = _run_units(dut, dut.sink, dut.source, unit, "sys", cd_to, ratio,
            common_rst_cdc = dut.cdc if kwargs.get("with_common_rst", False) else None)
        self.assertGreater(len(units), 100)
        self.assertEqual(units, list(range(units[0], units[0] + len(units))), "units out of order")
        return throughput

    def test_down_conversion_full_rate(self):
        # 64-bit words in sys to 16-bit pixels in video: one pixel per video cycle.
        for ratio in [0.5, 0.8, 1.0, 1.5]:
            with self.subTest(ratio=ratio):
                self.assertEqual(self._stream(64, 16, ratio, unit=16), 1.0)

    def test_up_conversion(self):
        # 16-bit words in sys to 64-bit words in video: one output word per 4 sys cycles at most.
        for ratio in [0.25, 0.5, 1.0]:
            with self.subTest(ratio=ratio):
                expected = min(1.0, 0.25/ratio)
                self.assertGreater(self._stream(16, 64, ratio, unit=16), 0.98*expected)

    def test_pipes_and_common_rst(self):
        throughput = self._stream(64, 16, 0.8, unit=16,
            pipe_valid_in   = True,
            pipe_ready_out  = True,
            with_common_rst = True,
        )
        self.assertEqual(throughput, 1.0)

    def test_same_clock_domain(self):
        self.assertEqual(self._stream(64, 16, 1.0, unit=16, cd_to="sys"), 1.0)

    def test_stride_converter_layout(self):
        # Multi-field layouts use StrideConverter (each field converted on its own).
        layout_from = [("dat", 32), ("be", 4)]
        layout_to   = [("dat", 64), ("be", 8)]
        dut = ClockDomainCrossingConverter(layout_from, layout_to, cd_from="sys", cd_to="video",
            clk_freq_from=100e6, clk_freq_to=100e6)
        self.assertIsInstance(dut.converter, stream.StrideConverter)

        class Top(LiteXModule):
            def __init__(self):
                self.clock_domains.cd_sys   = ClockDomain("sys")
                self.clock_domains.cd_video = ClockDomain("video")
                self.dut = dut
                count = Signal(32)
                self.comb += [
                    dut.sink.valid.eq(1),
                    dut.sink.dat.eq(count),
                    dut.sink.be.eq(count[:4]),
                    dut.source.ready.eq(1),
                ]
                self.sync += If(dut.sink.ready, count.eq(count + 1))

        received = []
        def reader():
            for _ in range(200):
                if (yield dut.source.valid):
                    received.append(((yield dut.source.dat), (yield dut.source.be)))
                yield

        @passive
        def idle():
            while True:
                yield

        run_simulation(Top(), {"video": reader(), "sys": idle()},
            clocks={"sys": 1000, "video": (1000, 333)})
        self.assertGreater(len(received), 10)
        for dat, be in received:
            lo, hi = dat & 0xffffffff, dat >> 32
            self.assertEqual(hi, lo + 1)
            self.assertEqual(be, (lo & 0xf) | ((hi & 0xf) << 4))

if __name__ == "__main__":
    unittest.main()
