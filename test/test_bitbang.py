#
# This file is part of LiteX.
#
# Copyright (c) 2019-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *
from migen.fhdl.specials import Tristate

from litex.soc.cores.bitbang import I2CMaster, I2CMasterSim, SPIMaster


# Tristate mock (lifted from test_i2c.py) --------------------------------------------------------
#
# Reproduced locally rather than imported to keep test files independent. If another test grows
# a need for it, a shared test/common.py becomes worth extracting.

class _MockTristateImpl(Module):
    def __init__(self, t):
        t.i_mock = Signal(reset=True)
        # Always drive the pad; only drive `i` if the consumer requested one (I2CMaster's SCL
        # tristate, for instance, passes no `i`).
        self.comb += If(t.oe,
            t.target.eq(t.o),
        ).Else(
            t.target.eq(t.i_mock),
        )
        if t.i is not None:
            self.comb += If(t.oe,
                t.i.eq(t.o),
            ).Else(
                t.i.eq(t.i_mock),
            )


class _MockTristate:
    @staticmethod
    def lower(t):
        return _MockTristateImpl(t)


# Bit-field offsets in I2CMaster._w / SPIMaster._w (copied from the CSRField definitions).
I2C_SCL = 1 << 0
I2C_OE  = 1 << 1
I2C_SDA = 1 << 2

SPI_CLK  = 1 << 0
SPI_MOSI = 1 << 1
SPI_OE   = 1 << 2
SPI_CS0  = 1 << 4


class TestBitBangI2C(unittest.TestCase):
    def test_syntax(self):
        # Original smoke test — kept so we still notice if the constructor's default-pads path
        # breaks.
        for m in [I2CMaster(), I2CMaster(Record(I2CMaster.pads_layout))]:
            self.assertTrue(hasattr(m, "pads"))

    def test_csr_drives_scl_and_sda(self):
        dut = I2CMaster()

        def gen():
            # Idle: _w.scl=1 (default), _w.oe=0 → both lines released, read as 1 by the mock.
            yield from dut._w.write(I2C_SCL)
            yield
            self.assertEqual((yield dut.pads.scl), 1)
            self.assertEqual((yield dut.pads.sda), 1)

            # Pull SCL low.
            yield from dut._w.write(0)
            yield
            self.assertEqual((yield dut.pads.scl), 0)

            # Release SCL; pull SDA low (oe=1, sda=0).
            yield from dut._w.write(I2C_SCL | I2C_OE)
            yield
            self.assertEqual((yield dut.pads.scl), 1)
            self.assertEqual((yield dut.pads.sda), 0)

            # Release SDA again.
            yield from dut._w.write(I2C_SCL | I2C_OE | I2C_SDA)
            yield
            self.assertEqual((yield dut.pads.sda), 1)

        run_simulation(dut, gen(), special_overrides={Tristate: _MockTristate})

    def test_start_then_stop_sequence(self):
        # Drive a textbook START (SDA falls while SCL high) followed by STOP (SDA rises while
        # SCL high). Only the pad waveform is checked; this isn't a full I2C conformance test.
        dut = I2CMaster()

        def gen():
            # Idle.
            yield from dut._w.write(I2C_SCL | I2C_OE | I2C_SDA)
            yield
            self.assertEqual(((yield dut.pads.scl), (yield dut.pads.sda)), (1, 1))

            # START: SDA low while SCL high.
            yield from dut._w.write(I2C_SCL | I2C_OE)
            yield
            self.assertEqual(((yield dut.pads.scl), (yield dut.pads.sda)), (1, 0))

            # SCL low to clock the start out.
            yield from dut._w.write(I2C_OE)
            yield
            self.assertEqual(((yield dut.pads.scl), (yield dut.pads.sda)), (0, 0))

            # SCL high with SDA still low (between bits on a real bus).
            yield from dut._w.write(I2C_SCL | I2C_OE)
            yield
            self.assertEqual(((yield dut.pads.scl), (yield dut.pads.sda)), (1, 0))

            # STOP: SDA rises while SCL is high.
            yield from dut._w.write(I2C_SCL | I2C_OE | I2C_SDA)
            yield
            self.assertEqual(((yield dut.pads.scl), (yield dut.pads.sda)), (1, 1))

        run_simulation(dut, gen(), special_overrides={Tristate: _MockTristate})

    def test_sda_readback_sim_variant(self):
        # I2CMasterSim exposes the SDA input as its own pad, avoiding tristate mocking. This is
        # the cleanest way to check that the readback path lands on `_r.sda`.
        dut = I2CMasterSim()

        def gen():
            # Release SDA (oe=0): input should follow pads.sda_in.
            yield from dut._w.write(I2C_SCL | I2C_SDA)
            yield dut.pads.sda_in.eq(1)
            yield
            self.assertEqual((yield dut._r.fields.sda), 1)

            yield dut.pads.sda_in.eq(0)
            yield
            self.assertEqual((yield dut._r.fields.sda), 0)

            # With oe=1 and sda=0 we drive the line low and _r.sda reflects the driven value.
            yield from dut._w.write(I2C_SCL | I2C_OE)
            yield
            self.assertEqual((yield dut._r.fields.sda), 0)

        run_simulation(dut, gen())


class TestBitBangSPI(unittest.TestCase):
    def test_syntax(self):
        for m in [SPIMaster(), SPIMaster(Record(SPIMaster.pads_layout))]:
            self.assertTrue(hasattr(m, "pads"))

    def test_csr_drives_clk_and_cs(self):
        dut = SPIMaster()

        def gen():
            # Idle: everything 0 → clk=0, cs_n=0b1111, mosi released.
            yield from dut._w.write(0)
            yield
            self.assertEqual((yield dut.pads.clk),  0)
            self.assertEqual((yield dut.pads.cs_n), 0b1111)

            # Assert CS0 (active-high control bit, inverted on the pad).
            yield from dut._w.write(SPI_CS0)
            yield
            self.assertEqual((yield dut.pads.cs_n), 0b1110)

            # Toggle the clock.
            yield from dut._w.write(SPI_CS0 | SPI_CLK)
            yield
            self.assertEqual((yield dut.pads.clk), 1)

            yield from dut._w.write(SPI_CS0)
            yield
            self.assertEqual((yield dut.pads.clk), 0)

        run_simulation(dut, gen(), special_overrides={Tristate: _MockTristate})

    def test_mosi_drive_and_release(self):
        dut = SPIMaster()

        def gen():
            # Drive MOSI high (oe=1, mosi=1).
            yield from dut._w.write(SPI_OE | SPI_MOSI)
            yield
            self.assertEqual((yield dut.pads.mosi), 1)

            # Drive low.
            yield from dut._w.write(SPI_OE)
            yield
            self.assertEqual((yield dut.pads.mosi), 0)

            # Release (oe=0) — mock input defaults high.
            yield from dut._w.write(0)
            yield
            self.assertEqual((yield dut.pads.mosi), 1)

        run_simulation(dut, gen(), special_overrides={Tristate: _MockTristate})

    def test_clocked_shift(self):
        # Drive a short 4-bit pattern on MOSI in lock-step with CLK and verify the waveform.
        dut     = SPIMaster()
        bits    = [1, 0, 1, 1]
        samples = []

        def gen():
            yield from dut._w.write(SPI_CS0 | SPI_OE)  # CS asserted, CLK low, MOSI low.
            yield

            for b in bits:
                # Set MOSI while CLK is low.
                w = SPI_CS0 | SPI_OE | (SPI_MOSI if b else 0)
                yield from dut._w.write(w)
                yield
                # Rising edge of CLK.
                yield from dut._w.write(w | SPI_CLK)
                yield
                samples.append((yield dut.pads.mosi))
                # Falling edge.
                yield from dut._w.write(w)
                yield

        run_simulation(dut, gen(), special_overrides={Tristate: _MockTristate})
        self.assertEqual(samples, bits)


if __name__ == "__main__":
    unittest.main()
