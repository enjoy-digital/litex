#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import Memory, Signal
from migen.sim import passive, run_simulation

from litex.soc.cores.audio.pcm import PCM
from litex.soc.interconnect import wishbone


class TestPCM(unittest.TestCase):
    def test_rejects_byte_addressed_dma_ports(self):
        for name in ("playback_bus", "capture_bus"):
            with self.subTest(port=name):
                bus = wishbone.Interface(data_width=32, addressing="byte")
                with self.assertRaisesRegex(ValueError, "word-addressed"):
                    PCM(**{name: bus})

    def test_dma_owns_each_direction_until_disabled(self):
        for width in (8, 16, 24, 32):
            with self.subTest(sample_width=width):
                self.check_dma(width)

    def check_dma(self, width):
        bus_width = 32 if width <= 16 else 64
        word_bytes = bus_width // 8
        read_bus = wishbone.Interface(data_width=bus_width, mode="r")
        write_bus = wishbone.Interface(data_width=bus_width, mode="w")
        pcm = PCM(sample_width=width, clock_domain="sys", fifo_depth=4, playback_bus=read_bus, capture_bus=write_bus)
        frame_mask = (1 << (2 * width)) - 1
        samples = [word & frame_mask for word in (0x1234abcd1234abcd, 0xfedc5678fedc5678)]
        padding = ((1 << bus_width) - 1) ^ frame_mask
        writes = []

        @passive
        def memory():
            while True:
                yield read_bus.ack.eq(0)
                yield write_bus.ack.eq(0)
                if (yield read_bus.cyc) and not (yield read_bus.ack):
                    address = yield read_bus.adr
                    self.assertIn(address, (4, 5))
                    yield read_bus.dat_r.eq(samples[address - 4] | padding)
                    yield read_bus.ack.eq(1)
                if (yield write_bus.cyc) and not (yield write_bus.ack):
                    writes.append(((yield write_bus.adr), (yield write_bus.dat_w)))
                    yield write_bus.ack.eq(1)
                yield

        def check():
            yield from pcm.capture.write(1)
            yield from pcm.capture_dma._base.write(8 * word_bytes)
            yield from pcm.capture_dma._length.write(2 * word_bytes)
            yield from pcm.playback_dma._base.write(4 * word_bytes)
            yield from pcm.playback_dma._length.write(2 * word_bytes)
            yield from pcm.capture_dma._enable.write(1)
            yield from pcm.playback_dma._enable.write(1)
            self.assertFalse((yield pcm.playback_sink.ready))
            self.assertFalse((yield pcm.capture_source.valid))
            yield from pcm.sample.write(0xbad)
            self.assertFalse((yield pcm.ready.status))

            played = []
            # Queue the frames as the capture controller starts, and keep the
            # last one for the CPU after the DMA reaches done.
            for sample in [*samples, 0x123]:
                yield pcm.record.sample.eq(sample)
                yield pcm.record.valid.eq(1)
                yield
            yield pcm.record.valid.eq(0)
            yield pcm.playback.ready.eq(1)
            for _ in range(20):
                if (yield pcm.playback.valid) and (yield pcm.playback.ready):
                    played.append((yield pcm.playback.sample))
                yield
            self.assertEqual(played, samples)
            self.assertEqual((yield pcm.playback.sample), 0)
            self.assertEqual(writes, [(8, samples[0]), (9, samples[1])])
            self.assertTrue((yield pcm.capture_dma.done))
            self.assertFalse((yield pcm.rx_ready.status))
            yield from pcm.capture_dma._enable.write(0)
            yield from pcm.playback_dma._enable.write(0)
            self.assertTrue((yield pcm.rx_ready.status))
            self.assertEqual((yield pcm.rx_sample.status), 0x123)
            yield from pcm.capture_stream.write(1)
            self.assertTrue((yield pcm.capture_source.valid))
            yield from pcm.rx_pop.write(1)
            yield from pcm.capture_stream.write(0)
            yield from pcm.capture_dma._enable.write(1)
            self.assertFalse((yield pcm.rx_ready.status))
            self.assertTrue((yield pcm.capture_source.valid))
            self.assertEqual((yield pcm.capture_source.sample), 0x123)
            yield pcm.capture_source.ready.eq(1)
            yield
            yield pcm.capture_source.ready.eq(0)
            yield
            self.assertFalse((yield pcm.capture_source.valid))
            self.assertEqual(writes, [(8, samples[0]), (9, samples[1])])
            yield from pcm.capture_dma._enable.write(0)

            yield pcm.playback_sink.sample.eq(0x789)
            yield pcm.playback_sink.valid.eq(1)
            yield
            self.assertTrue((yield pcm.playback_sink.ready))
            self.assertFalse((yield pcm.ready.status))
            yield
            yield pcm.playback_sink.valid.eq(0)
            yield
            self.assertTrue((yield pcm.playback.valid))
            self.assertEqual((yield pcm.playback.sample), 0x789)
            yield from pcm.sample.write(0x456)
            for _ in range(5):
                if (yield pcm.playback.valid) and (yield pcm.playback.ready):
                    self.assertEqual((yield pcm.playback.sample), 0x456)
                    return
                yield
            self.fail("CSR sample did not reach playback")

        fragment = pcm.get_fragment()
        # Migen's simulator expects even write-only memory ports to have a
        # read signal when lowering memories to arrays.
        for special in fragment.specials:
            if isinstance(special, Memory):
                for port in special.ports:
                    if port.dat_r is None:
                        port.dat_r = Signal(special.width)
        run_simulation(fragment, [memory(), check()])
