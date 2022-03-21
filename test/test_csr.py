#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.interconnect import csr
from litex.soc.interconnect import csr_bus


def csr32_write(dut, adr, dat):
    for i in range(4):
        yield from dut.csr.write(adr + 3 - i, (dat >> 8*i) & 0xff)


def csr32_read(dut, adr):
    dat = 0
    for i in range(4):
        dat |= ((yield from dut.csr.read(adr + 3 - i)) << 8*i)
    return dat


class CSRModule(Module, csr.AutoCSR):
    def __init__(self):
        self._csr      = csr.CSR()
        self._constant = csr.CSRConstant(0x12345678)
        self._storage  = csr.CSRStorage(32, reset=0x12345678, write_from_dev=True)
        self._status   = csr.CSRStatus(32, reset=0x12345678)

        # # #

        # When csr is written:
        # - set storage to 0xdeadbeef
        # - set status to storage value
        self.comb += [
            If(self._csr.re,
                self._storage.we.eq(1),
                self._storage.dat_w.eq(0xdeadbeef)
            )
        ]
        self.sync += [
            If(self._csr.re,
                self._status.status.eq(self._storage.storage)
            )
        ]


class CSRDUT(Module):
    def address_map(self, name, memory):
            return {"csrmodule": 0}[name]

    def __init__(self):
        self.csr = csr_bus.Interface()
        self.submodules.csrmodule = CSRModule()
        self.submodules.csrbankarray = csr_bus.CSRBankArray(
            self, self.address_map)
        self.submodules.csrcon = csr_bus.Interconnect(
            self.csr, self.csrbankarray.get_buses())

class TestCSR(unittest.TestCase):
    def test_csr_constant(self):
        def generator(dut):
            self.assertEqual(hex((yield from dut.csrmodule._constant.read())), hex(0x12345678))

        dut = CSRDUT()
        run_simulation(dut, generator(dut))

    def test_csr_storage(self):
        def generator(dut):
            # check init value
            self.assertEqual(hex((yield from csr32_read(dut, 5))), hex(0x12345678))

            # check writes
            yield from csr32_write(dut, 1, 0x5a5a5a5a)
            self.assertEqual(hex((yield from csr32_read(dut, 1))), hex(0x5a5a5a5a))
            yield from csr32_write(dut, 1, 0xa5a5a5a5)
            self.assertEqual(hex((yield from csr32_read(dut, 1))), hex(0xa5a5a5a5))

            # check update from dev
            yield from dut.csr.write(0, 1)
            self.assertEqual(hex((yield from csr32_read(dut, 1))), hex(0xdeadbeef))

        dut = CSRDUT()
        run_simulation(dut, generator(dut))

    def test_csr_status(self):
        def generator(dut):
            # check init value
            self.assertEqual(hex((yield from csr32_read(dut, 1))), hex(0x12345678))

            # check writes (no effect)
            yield from csr32_write(dut, 5, 0x5a5a5a5a)
            self.assertEqual(hex((yield from csr32_read(dut, 5))), hex(0x12345678))
            yield from csr32_write(dut, 5, 0xa5a5a5a5)
            self.assertEqual(hex((yield from csr32_read(dut, 5))), hex(0x12345678))

            # check update from dev
            yield from dut.csr.write(0, 1)
            yield from dut.csr.write(0, 1)
            self.assertEqual(hex((yield from csr32_read(dut, 5))), hex(0xdeadbeef))

        dut = CSRDUT()
        run_simulation(dut, generator(dut))

    def test_csr_fields(self):
        def generator(dut):
            # check reset values
            self.assertEqual((yield dut._storage.fields.foo), 0xa)
            self.assertEqual((yield dut._storage.fields.bar), 0x5a)
            self.assertEqual((yield dut._storage.storage), 0x5a000a)
            yield
            yield
            self.assertEqual((yield dut._status.fields.foo), 0xa)
            self.assertEqual((yield dut._status.fields.bar), 0x5a)

        class DUT(Module):
            def __init__(self):
                self._storage = csr.CSRStorage(fields=[
                    csr.CSRField("foo", size=4, offset=0,  reset=0xa,  description="foo"),
                    csr.CSRField("bar", size=8, offset=16, reset=0x5a, description="bar")
                ])
                self._status = csr.CSRStatus(fields=[
                    csr.CSRField("foo", size=4, offset=4, description="foo"),
                    csr.CSRField("bar", size=8, offset=8, description="bar")
                ])
                self.comb += [
                    self._status.fields.foo.eq(self._storage.fields.foo),
                    self._status.fields.bar.eq(self._storage.fields.bar),
                ]
        dut = DUT()
        run_simulation(dut, generator(dut))
