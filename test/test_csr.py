#!/usr/bin/env python3

import unittest

from migen import *

from litex.soc.interconnect.csr import *


class CSRModule(Module, AutoCSR):
    def __init__(self, *args, **kw):
        self.submodules.csr = CSRStorage(*args, **kw)


class TestCSRStorage(unittest.TestCase):

    def assert_csr(self, csr, expected):
        actual = yield from csr.read()
        self.assertEqual(hex(expected), hex(actual))

    def stim_csr_write(self, dut, values, mask):
        yield from self.assert_csr(dut.csr, 0)
        for v in values:
            yield from dut.csr.write(v)
            yield from self.assert_csr(dut.csr, v & mask)

    def test_readwrite_nibble(self):
        dut = CSRModule(size=4)
        stim = self.stim_csr_write(dut, [0, 0xff, 0x0b, 0xaa], 0x0f)
        run_simulation(dut, stim, vcd_name="vcd/%s.vcd" %  self.id())

    def test_readwrite_byte(self):
        dut = CSRModule(size=8)
        stim = self.stim_csr_write(dut, [0, 0xff, 0x0b, 0xaa], 0xff)
        run_simulation(dut, stim, vcd_name="vcd/%s.vcd" %  self.id())

    def test_readwrite_32bit(self):
        dut = CSRModule(size=32)
        stim = self.stim_csr_write(dut, [0, 0xffffffff, 0x0a0a0a0a, 0xa0a0a0a0], 0xffffffff),
        run_simulation(dut, stim, vcd_name="vcd/%s.vcd" %  self.id())

    def test_readwrite_byte_alignment(self):
        dut = CSRModule(size=16, alignment_bits=8)
        stim = self.stim_csr_write(dut, [0, 0xffff, 0x0a0a, 0xa0a0], 0xff00),
        run_simulation(dut, stim, vcd_name="vcd/%s.vcd" %  self.id())

    def test_readwrite_from_dev(self):
        dut = CSRModule(size=8, write_from_dev=True)

        def stim():
            yield from self.assert_csr(dut.csr, 0)
            for v in [0, 0xff, 0x0a, 0xa0]:
                yield from dut.csr.write_from_dev(v)

                # Read the CSR value and check it
                actual = yield from dut.csr.read()
                self.assertEqual(hex(actual), hex(v))

        run_simulation(dut, stim(), vcd_name="vcd/%s.vcd" %  self.id())


if __name__ == '__main__':
    import doctest
    doctest.testmod()
    unittest.main()
