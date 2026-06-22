#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Unit tests for stream.Pipeline and stream.BufferizeEndpoints — composition helpers that had
no dedicated coverage."""

import unittest

from migen import *

from litex.gen import *

from litex.soc.interconnect import stream


LAYOUT = [("data", 8)]


# Pipeline ----------------------------------------------------------------------------------------

class TestStreamPipeline(unittest.TestCase):
    def test_pipeline_chains_three_buffers(self):
        # Pipeline(B0, B1, B2): exposes B0.sink and B2.source; intermediate connects are
        # combinational. A byte pushed on the first sink must reach the last source unchanged
        # (with some pipeline latency).
        class DUT(LiteXModule):
            def __init__(self):
                self.b0 = stream.Buffer(LAYOUT)
                self.b1 = stream.Buffer(LAYOUT)
                self.b2 = stream.Buffer(LAYOUT)
                self.submodules.pipe = stream.Pipeline(self.b0, self.b1, self.b2)

        dut      = DUT()
        payload  = list(range(0x10, 0x20))
        captured = []

        def producer():
            for byte in payload:
                yield dut.pipe.sink.valid.eq(1)
                yield dut.pipe.sink.data.eq(byte)
                yield
                while not (yield dut.pipe.sink.ready):
                    yield
            yield dut.pipe.sink.valid.eq(0)

        def consumer():
            yield dut.pipe.source.ready.eq(1)
            timeout = 0
            while len(captured) < len(payload):
                yield
                if (yield dut.pipe.source.valid) and (yield dut.pipe.source.ready):
                    captured.append((yield dut.pipe.source.data))
                timeout += 1
                self.assertLess(timeout, 5_000, "pipeline stalled")

        run_simulation(dut, [producer(), consumer()])
        self.assertEqual(captured, payload)

    def test_pipeline_add_after_construction(self):
        # `Pipeline()` with no arguments stays unfinalized so further .add() calls work.
        # Adding modules later then consuming sink/source must behave the same.
        class DUT(LiteXModule):
            def __init__(self):
                self.submodules.pipe = stream.Pipeline()
                self.b0 = stream.Buffer(LAYOUT)
                self.b1 = stream.Buffer(LAYOUT)
                self.pipe.add(self.b0)
                self.pipe.add(self.b1)
                # Pipeline finalizes at use time. We force finalize here so sink/source exist.
                self.pipe.finalize()

        dut      = DUT()
        captured = []

        def producer():
            for byte in [0xAB, 0xCD]:
                yield dut.pipe.sink.valid.eq(1)
                yield dut.pipe.sink.data.eq(byte)
                yield
                while not (yield dut.pipe.sink.ready):
                    yield
            yield dut.pipe.sink.valid.eq(0)

        def consumer():
            yield dut.pipe.source.ready.eq(1)
            timeout = 0
            while len(captured) < 2:
                yield
                if (yield dut.pipe.source.valid) and (yield dut.pipe.source.ready):
                    captured.append((yield dut.pipe.source.data))
                timeout += 1
                self.assertLess(timeout, 1_000, "pipeline stalled")

        run_simulation(dut, [producer(), consumer()])
        self.assertEqual(captured, [0xAB, 0xCD])


# BufferizeEndpoints ------------------------------------------------------------------------------

# A trivial pass-through module whose endpoints we'll wrap with Buffers.
class _Identity(Module):
    def __init__(self):
        self.sink   = stream.Endpoint(LAYOUT)
        self.source = stream.Endpoint(LAYOUT)
        self.comb += self.sink.connect(self.source)


class TestStreamBufferizeEndpoints(unittest.TestCase):
    def test_bufferize_preserves_data_flow(self):
        # Apply BufferizeEndpoints to wrap the sink with a Buffer; data flowing into the new
        # sink must come out the source unchanged. Verifies the transformer keeps the data
        # path correct (it intentionally introduces some latency by inserting the Buffer).
        cls       = stream.BufferizeEndpoints({"sink": stream.DIR_SINK})(_Identity)
        dut       = cls()
        payload   = [0x11, 0x22, 0x33, 0x44]
        captured  = []

        def producer():
            for byte in payload:
                yield dut.sink.valid.eq(1)
                yield dut.sink.data.eq(byte)
                yield
                while not (yield dut.sink.ready):
                    yield
            yield dut.sink.valid.eq(0)

        def consumer():
            yield dut.source.ready.eq(1)
            timeout = 0
            while len(captured) < len(payload):
                yield
                if (yield dut.source.valid) and (yield dut.source.ready):
                    captured.append((yield dut.source.data))
                timeout += 1
                self.assertLess(timeout, 1_000, "bufferized stream stalled")

        run_simulation(dut, [producer(), consumer()])
        self.assertEqual(captured, payload)


if __name__ == "__main__":
    unittest.main()
