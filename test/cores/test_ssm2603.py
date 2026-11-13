#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from migen import ClockDomain, Module, Signal
from migen.sim import run_simulation

from litex.soc.cores.audio.ssm2603 import SSM2603, SSM2603PCM
from litex.soc.cores.bitbang import I2CMaster
from litex.soc.interconnect.stream import Endpoint


class _DirectStream(Module):
    """Bypass asynchronous FIFOs to check the serial framing in isolation."""

    def __init__(self, layout, **kwargs):
        self.sink = Endpoint(layout)
        self.source = Endpoint(layout)
        self.comb += self.sink.connect(self.source)


class TestSSM2603(unittest.TestCase):
    def test_stereo_playback(self):
        for rate, setting in ((48_000, 0), (44_100, 0x20)):
            for width in (16, 20, 24, 32):
                with self.subTest(sample_rate=rate, sample_width=width):
                    self.check_stereo_playback(rate, setting, width)

    def check_stereo_playback(self, rate, setting, width):
        slot_width = 16 if width == 16 else 32
        left = 0x12e9 << (width - 16) | 1
        right = 0xa63c << (width - 16) | 1
        configs = {}
        soc = SimpleNamespace(codec_bus=I2CMaster(), add_config=configs.__setitem__)
        SSM2603(soc, "codec_bus", sample_rate=rate, sample_width=width)
        self.assertEqual(configs["SSM2603_I2C_BUS"], "codec_bus")
        self.assertEqual(configs["SSM2603_INTERFACE"], 1 + 4 * (16, 20, 24, 32).index(width))
        self.assertEqual(configs["SSM2603_SAMPLING"], setting)
        self.assertEqual(soc.codec_bus.init, [])

        dut = Module()
        dut.clock_domains.cd_audio = ClockDomain("audio")
        pads = SimpleNamespace(**{name: Signal() for name in (
            "bclk", "dacdat", "daclrck", "adclrck", "adcdat", "xck")})
        with patch("litex.soc.cores.audio.pcm.stream.ClockDomainCrossing", _DirectStream):
            dut.submodules.pcm = pcm = SSM2603PCM(pads, dut.cd_audio.clk, sample_rate=rate, sample_width=width)
        dut.comb += pads.adcdat.eq(pads.dacdat)
        self.assertEqual(pcm.master_clk_freq, 256 * rate)

        def transmit():
            yield pcm.sample.storage.eq((right << width) | left)
            yield pcm.sample.re.eq(1)
            yield
            while not (yield pcm.ready.status):
                yield
            yield pcm.sample.re.eq(0)

        def monitor():
            words = []
            bits = []
            previous_clock = previous_channel = 0
            last_left = None
            captured = []
            for cycle in range(1024):
                if (yield pcm.record.valid):
                    captured.append((yield pcm.record.sample))
                clock = yield pads.bclk
                channel = yield pads.daclrck
                if clock and not previous_clock:
                    if channel != previous_channel:
                        bits = []
                    bits.append((yield pads.dacdat))
                    if len(bits) == slot_width:
                        word = sum(bit << (slot_width - 1 - i) for i, bit in enumerate(bits))
                        words.append((channel, word))
                        if channel:
                            if last_left is not None:
                                self.assertEqual(cycle - last_left, 256)
                            last_left = cycle
                    previous_channel = channel
                previous_clock = clock
                yield
            self.assertEqual(words[1:3], [(1, left << (slot_width - width)), (0, right << (slot_width - width))])
            self.assertEqual(words[3:5], [(1, 0), (0, 0)])
            self.assertIn((right << width) | left, captured)

        run_simulation(dut, {"audio": [transmit(), monitor()]}, clocks={"sys": 10, "audio": 40})
