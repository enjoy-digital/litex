#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.gpio import GPIOIn, GPIOOut, GPIOInOut, GPIOTristate


# A small TSTriple-shaped record the GPIOTristate "external" path understands:
# it exposes `.o`, `.oe`, `.i`, each an n-bit Signal.
class _TristatePads:
    def __init__(self, nbits):
        self.o  = Signal(nbits)
        self.oe = Signal(nbits)
        self.i  = Signal(nbits)


# MultiReg default depth (registers input path for CDC/metastability).
_MULTIREG_DELAY = 2


class TestGPIO(unittest.TestCase):
    def test_gpio_out(self):
        pads = Signal(8)
        dut  = GPIOOut(pads)

        def gen():
            for value in [0x00, 0xA5, 0xFF, 0x01, 0x80]:
                yield from dut.out.write(value)
                # pads is combinational on storage; give the CSR write one extra cycle to settle.
                yield
                self.assertEqual((yield pads), value)
        run_simulation(dut, gen())

    def test_gpio_in(self):
        pads = Signal(8)
        dut  = GPIOIn(pads)

        def gen():
            for value in [0x00, 0x5A, 0xFF, 0x10, 0xC3]:
                yield pads.eq(value)
                # Account for MultiReg synchroniser depth.
                for _ in range(_MULTIREG_DELAY + 1):
                    yield
                read = yield from dut._in.read()
                self.assertEqual(read, value)
        run_simulation(dut, gen())

    def test_gpio_inout(self):
        in_pads  = Signal(4)
        out_pads = Signal(4)
        dut      = GPIOInOut(in_pads, out_pads)

        def gen():
            # Output path.
            yield from dut.gpio_out.out.write(0xA)
            yield
            self.assertEqual((yield out_pads), 0xA)

            # Input path.
            yield in_pads.eq(0x5)
            for _ in range(_MULTIREG_DELAY + 1):
                yield
            self.assertEqual((yield from dut.gpio_in._in.read()), 0x5)
        run_simulation(dut, gen())

    def test_gpio_tristate_external(self):
        # Drive `_out`/`_oe` via CSR and observe pads.o/pads.oe; conversely drive pads.i and
        # read `_in`.
        pads = _TristatePads(nbits=8)
        dut  = GPIOTristate(pads)

        def gen():
            # Output + output-enable.
            yield from dut._out.write(0xCA)
            yield from dut._oe.write(0xF0)
            yield
            self.assertEqual((yield pads.o),  0xCA)
            self.assertEqual((yield pads.oe), 0xF0)

            # Input (goes through MultiReg).
            yield pads.i.eq(0x37)
            for _ in range(_MULTIREG_DELAY + 1):
                yield
            self.assertEqual((yield from dut._in.read()), 0x37)
        run_simulation(dut, gen())


if __name__ == "__main__":
    unittest.main()
