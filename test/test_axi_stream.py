#
# This file is part of LiteX.
#
# Copyright (c) 2020-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *

from litex.gen import *

from litex.soc.interconnect.axi import AXIStreamInterface


# Helpers ------------------------------------------------------------------------------------------

class _Loopback(LiteXModule):
    """Two AXIStreamInterface endpoints wired together combinationally.

    Good enough to exercise the interface plumbing: the source drives tvalid/tdata, the sink
    drives tready, and the interconnect just forwards.
    """
    def __init__(self, **kwargs):
        self.source = AXIStreamInterface(**kwargs)
        self.sink   = AXIStreamInterface(**kwargs)
        self.comb += self.source.connect(self.sink)


def producer(endpoint, beats, valid_prob=100, seed=42):
    """Drive `beats` onto `endpoint`. Each beat is a dict with optional data/keep/last/id/dest/user.

    `valid_prob`: % chance of asserting valid each cycle — randomised backpressure on the master
    side.
    """
    prng = random.Random(seed)
    for beat in beats:
        # Randomised valid.
        while prng.randint(0, 99) >= valid_prob:
            yield endpoint.valid.eq(0)
            yield
        yield endpoint.valid.eq(1)
        for field, value in beat.items():
            yield getattr(endpoint, field).eq(value)
        yield
        while not (yield endpoint.ready):
            yield
    yield endpoint.valid.eq(0)


def consumer(endpoint, nbeats, captured, fields, ready_prob=100, seed=43):
    """Collect `nbeats` beats off `endpoint`, sampling each listed field on every accepted beat."""
    prng = random.Random(seed)
    for _ in range(nbeats):
        while prng.randint(0, 99) >= ready_prob:
            yield endpoint.ready.eq(0)
            yield
        yield endpoint.ready.eq(1)
        yield
        # Hunt for valid&ready.
        timeout = 0
        while not ((yield endpoint.valid) and (yield endpoint.ready)):
            yield
            timeout += 1
            assert timeout < 10_000, "consumer stalled"
        sample = {}
        for f in fields:
            sample[f] = (yield getattr(endpoint, f))
        captured.append(sample)
        # Randomly throttle between beats.
        yield endpoint.ready.eq(0)
    yield endpoint.ready.eq(0)


# Syntax tests (preserved) -------------------------------------------------------------------------

class TestAXIStreamSyntax(unittest.TestCase):
    def test_axi_stream_constructors(self):
        AXIStreamInterface(data_width=32)
        AXIStreamInterface(data_width=32, keep_width=4)
        AXIStreamInterface(data_width=32, keep_width=4, id_width=4)
        AXIStreamInterface(data_width=32, keep_width=4, id_width=4, dest_width=4)
        AXIStreamInterface(data_width=32, keep_width=4, id_width=4, dest_width=4, user_width=4)

    def test_axi_stream_get_ios(self):
        axis = AXIStreamInterface(data_width=32, keep_width=4, id_width=4, dest_width=4, user_width=4)
        pads = axis.get_ios()
        # tvalid / tlast / tready + tdata / tkeep / tid / tdest / tuser.
        self.assertEqual(len(pads), 1)


# Behaviour tests ----------------------------------------------------------------------------------

class TestAXIStreamLoopback(unittest.TestCase):
    def test_basic_loopback(self):
        dut = _Loopback(data_width=32)
        payload = [{"data": (i*0x1111_1111) & 0xffff_ffff} for i in range(16)]
        captured = []

        def gen():
            yield from producer(dut.source, payload)

        def consume():
            yield from consumer(dut.sink, len(payload), captured, fields=["data"])

        run_simulation(dut, [gen(), consume()])
        self.assertEqual(captured, payload)

    def test_loopback_with_backpressure(self):
        # Both producer and consumer randomly throttle; data must still arrive in order.
        dut = _Loopback(data_width=32)
        payload = [{"data": i & 0xffff_ffff} for i in range(64)]
        captured = []

        def gen():
            yield from producer(dut.source, payload, valid_prob=60)

        def consume():
            yield from consumer(dut.sink, len(payload), captured, fields=["data"], ready_prob=60)

        run_simulation(dut, [gen(), consume()])
        self.assertEqual(captured, payload)

    def test_loopback_carries_side_channels(self):
        # data/keep/id/dest/user/last should all survive the loopback.
        dut = _Loopback(data_width=32, keep_width=4, id_width=4, dest_width=4, user_width=4)
        payload = [
            {"data": 0x11223344, "keep": 0xF, "last": 0, "id": 1, "dest": 2, "user": 0xA},
            {"data": 0xdeadbeef, "keep": 0x3, "last": 0, "id": 2, "dest": 3, "user": 0xB},
            {"data": 0xcafebabe, "keep": 0xF, "last": 1, "id": 3, "dest": 4, "user": 0xC},
        ]
        captured = []

        def gen():
            yield from producer(dut.source, payload)

        def consume():
            yield from consumer(dut.sink, len(payload), captured,
                fields=["data", "keep", "last", "id", "dest", "user"])

        run_simulation(dut, [gen(), consume()])
        self.assertEqual(captured, payload)

    def test_packetised_transfer(self):
        # Use `last` to mark packet boundaries and verify each packet ends on a beat with last=1.
        dut = _Loopback(data_width=32)
        packets = [
            [0x0001, 0x0002, 0x0003],
            [0x0101, 0x0102, 0x0103, 0x0104],
            [0x0201],
        ]
        payload = []
        for pkt in packets:
            for i, word in enumerate(pkt):
                payload.append({"data": word, "last": 1 if i == len(pkt)-1 else 0})
        captured = []

        def gen():
            yield from producer(dut.source, payload, valid_prob=70)

        def consume():
            yield from consumer(dut.sink, len(payload), captured,
                fields=["data", "last"], ready_prob=70)

        run_simulation(dut, [gen(), consume()])
        self.assertEqual(captured, payload)
        last_positions = [i for i, b in enumerate(captured) if b["last"]]
        expected_ends  = [2, 6, 7]
        self.assertEqual(last_positions, expected_ends)


if __name__ == "__main__":
    unittest.main()
