#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Unit tests for stream.Pack / stream.Unpack / stream.StrideConverter — width adapters that
were not directly covered.
"""

import unittest

from migen import *

from litex.soc.interconnect import stream


# Pack: 4 × 8-bit beats packed into 1 × 32-bit beat (chunk0..chunk3) ------------------------------

class TestStreamPack(unittest.TestCase):
    def test_pack_4_words(self):
        dut    = stream.Pack(layout_from=[("data", 8)], n=4)
        inputs = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]  # 8 in → 2 packed beats
        results = []

        def producer():
            for word in inputs:
                yield dut.sink.valid.eq(1)
                yield dut.sink.data.eq(word)
                yield
                while not (yield dut.sink.ready):
                    yield
            yield dut.sink.valid.eq(0)

        def consumer():
            yield dut.source.ready.eq(1)
            timeout = 0
            while len(results) < 2:
                yield
                if (yield dut.source.valid) and (yield dut.source.ready):
                    sample = {}
                    for i in range(4):
                        sample[i] = (yield getattr(dut.source.payload, f"chunk{i}").data)
                    results.append(sample)
                timeout += 1
                assert timeout < 200, "Pack consumer stalled"

        run_simulation(dut, [producer(), consumer()])

        self.assertEqual(results, [
            {0: 0x11, 1: 0x22, 2: 0x33, 3: 0x44},
            {0: 0x55, 1: 0x66, 2: 0x77, 3: 0x88},
        ])


# Unpack: 1 × packed (chunk0..chunk3) beat unpacked into 4 × 8-bit beats --------------------------

class TestStreamUnpack(unittest.TestCase):
    def test_unpack_into_4_beats(self):
        dut    = stream.Unpack(n=4, layout_to=[("data", 8)])
        # Build one packed beat where chunk0/1/2/3 = 0xA0/0xA1/0xA2/0xA3.
        # The sink's layout has chunk0..chunk3 each containing a `data` field.
        results = []

        def gen():
            yield dut.source.ready.eq(1)
            yield getattr(dut.sink.payload, "chunk0").data.eq(0xA0)
            yield getattr(dut.sink.payload, "chunk1").data.eq(0xA1)
            yield getattr(dut.sink.payload, "chunk2").data.eq(0xA2)
            yield getattr(dut.sink.payload, "chunk3").data.eq(0xA3)
            yield dut.sink.valid.eq(1)
            for _ in range(40):
                yield
                if (yield dut.source.valid) and (yield dut.source.ready):
                    results.append((yield dut.source.data))
                    if len(results) == 4:
                        break
        run_simulation(dut, gen())

        self.assertEqual(results, [0xA0, 0xA1, 0xA2, 0xA3])


# StrideConverter: width down-conversion 32→8 (split each 32-bit beat into 4 × 8) ------------------

class TestStrideConverter(unittest.TestCase):
    def _stride_loopback(self, dut, inputs, nresults):
        results = []

        def producer():
            for word in inputs:
                yield dut.sink.valid.eq(1)
                yield dut.sink.data.eq(word)
                yield
                while not (yield dut.sink.ready):
                    yield
            yield dut.sink.valid.eq(0)

        def consumer():
            yield dut.source.ready.eq(1)
            timeout = 0
            while len(results) < nresults:
                yield
                if (yield dut.source.valid) and (yield dut.source.ready):
                    results.append((yield dut.source.data))
                timeout += 1
                assert timeout < 200, "stride consumer stalled"

        run_simulation(dut, [producer(), consumer()])
        return results

    def test_stride_down_32_to_8(self):
        dut     = stream.StrideConverter([("data", 32)], [("data", 8)])
        inputs  = [0x11223344, 0xdeadbeef]
        results = self._stride_loopback(dut, inputs, nresults=8)

        # Each 32-bit input emits 4 bytes, lowest byte first.
        expected = []
        for w in inputs:
            for byte in range(4):
                expected.append((w >> (byte*8)) & 0xff)
        self.assertEqual(results, expected)

    def test_stride_up_8_to_32(self):
        dut     = stream.StrideConverter([("data", 8)], [("data", 32)])
        inputs  = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]
        results = self._stride_loopback(dut, inputs, nresults=2)

        expected = [
            (0x44 << 24) | (0x33 << 16) | (0x22 << 8) | 0x11,
            (0x88 << 24) | (0x77 << 16) | (0x66 << 8) | 0x55,
        ]
        self.assertEqual(results, expected)


if __name__ == "__main__":
    unittest.main()
