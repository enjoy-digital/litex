#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.adat import ADATTX
from litex.soc.cores.adat import ADATRX
from litex.soc.cores.adat import ADAT_FRAME_BITS


def adat_frame(samples, user=0):
    bits = []
    bits += [0]*10
    bits += [1, (user >> 3) & 1, (user >> 2) & 1, (user >> 1) & 1, user & 1, 1]
    for sample in samples:
        for nibble in range(6):
            for bit in range(4):
                bits.append((sample >> (23 - 4*nibble - bit)) & 1)
            bits.append(1)
    return bits


def nrzi_encode(bits, level=0):
    encoded = []
    for bit in bits:
        if bit:
            level ^= 1
        encoded.append(level)
    return encoded


class ADATLoopback(Module):
    def __init__(self):
        self.bit_tick = Signal()

        self.submodules.tx = ADATTX()
        self.submodules.rx = ADATRX()

        self.comb += [
            self.tx.bit_tick.eq(self.bit_tick),
            self.rx.bit_tick.eq(self.bit_tick),
            self.rx.rx.eq(self.tx.tx),
        ]


class TestADAT(unittest.TestCase):
    def test_adattx_syntax(self):
        pads = Record([("tx", 1)])
        ADATTX(pads=pads)

    def test_adatrx_syntax(self):
        pads = Record([("rx", 1)])
        ADATRX(pads=pads)

    def test_adattx_frame(self):
        dut     = ADATTX()
        samples = [
            0x123456,
            0xabcdef,
            0x000001,
            0x800000,
            0x55aa55,
            0xaa55aa,
            0x0f0f0f,
            0xf0f0f0,
        ]
        user = 0b1010
        tx   = []

        def generator():
            yield dut.user.eq(user)

            for sample in samples:
                yield dut.sink.valid.eq(1)
                yield dut.sink.data.eq(sample)
                yield

            yield dut.sink.valid.eq(0)
            yield dut.bit_tick.eq(1)
            yield

            for _ in range(2*ADAT_FRAME_BITS):
                yield
                tx.append((yield dut.tx))

        run_simulation(dut, generator())

        self.assertEqual(tx[:ADAT_FRAME_BITS], [0]*ADAT_FRAME_BITS)
        self.assertEqual(
            tx[ADAT_FRAME_BITS:],
            nrzi_encode(adat_frame(samples, user=user)),
        )

    def test_adattx_underflow(self):
        dut        = ADATTX()
        underflows = []

        def generator():
            yield dut.bit_tick.eq(1)
            yield
            for _ in range(ADAT_FRAME_BITS):
                yield
                underflows.append((yield dut.underflow))

        run_simulation(dut, generator())

        self.assertEqual(sum(underflows), 1)

    def test_adatrx_frame(self):
        dut     = ADATRX()
        samples = [
            0x123456,
            0xabcdef,
            0x000001,
            0x800000,
            0x55aa55,
            0xaa55aa,
            0x0f0f0f,
            0xf0f0f0,
        ]
        user     = 0b1010
        rx       = nrzi_encode(adat_frame(samples, user=user))
        rx_user  = []
        received = []

        def generator():
            yield dut.source.ready.eq(1)
            yield dut.bit_tick.eq(1)
            yield

            for bit in rx:
                yield dut.rx.eq(bit)
                yield
                if (yield dut.source.valid):
                    received.append((
                        (yield dut.source.channel),
                        (yield dut.source.data),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
            yield
            if (yield dut.source.valid):
                received.append((
                    (yield dut.source.channel),
                    (yield dut.source.data),
                    (yield dut.source.first),
                    (yield dut.source.last),
                ))
            rx_user.append((yield dut.user))

        run_simulation(dut, generator())

        self.assertEqual(rx_user[0], user)
        self.assertEqual(
            received,
            [(n, sample, n == 0, n == 7) for n, sample in enumerate(samples)],
        )

    def test_adatrx_invalid_marker(self):
        dut     = ADATRX()
        samples = [0]*8
        bits    = adat_frame(samples)
        invalid = []

        bits[20] = 0
        rx = nrzi_encode(bits)

        def generator():
            yield dut.bit_tick.eq(1)
            yield

            for bit in rx:
                yield dut.rx.eq(bit)
                yield
                invalid.append((yield dut.invalid))

        run_simulation(dut, generator())

        self.assertGreater(sum(invalid), 0)

    def test_adat_loopback_example(self):
        dut = ADATLoopback()

        samples = [
            0x111111,
            0x222222,
            0x333333,
            0x444444,
            0x555555,
            0x666666,
            0x777777,
            0x888888,
        ]
        user     = 0b0101
        received = []
        rx_user  = []

        def generator():
            yield dut.bit_tick.eq(1)
            yield dut.rx.source.ready.eq(1)
            yield dut.tx.user.eq(user)
            yield

            for sample in samples:
                yield dut.tx.sink.valid.eq(1)
                yield dut.tx.sink.data.eq(sample)
                yield
            yield dut.tx.sink.valid.eq(0)

            for _ in range(3*ADAT_FRAME_BITS):
                yield
                if (yield dut.rx.source.valid):
                    received.append((
                        (yield dut.rx.source.channel),
                        (yield dut.rx.source.data),
                    ))
                    if len(received) == len(samples):
                        break

            rx_user.append((yield dut.rx.user))

        run_simulation(dut, generator())

        self.assertEqual(rx_user[0], user)
        self.assertEqual(received, list(enumerate(samples)))


if __name__ == "__main__":
    unittest.main()
