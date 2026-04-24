#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Unit tests for litex.soc.interconnect.csr_bus.

test_csr.py exercises the per-CSR-primitive paths through a single bank at offset 0. This file
covers the bus-level routing: multiple banks at distinct paging addresses behind one
Interconnect, with each bank reachable independently.
"""

import unittest

from migen import *

from litex.soc.interconnect import csr, csr_bus


# Two trivial CSR-bearing modules -----------------------------------------------------------------

class _ModuleA(Module, csr.AutoCSR):
    def __init__(self):
        self._a0 = csr.CSRStorage(8, reset=0xA0)
        self._a1 = csr.CSRStorage(8, reset=0xA1)


class _ModuleB(Module, csr.AutoCSR):
    def __init__(self):
        self._b0 = csr.CSRStorage(8, reset=0xB0)
        self._b1 = csr.CSRStorage(8, reset=0xB1)
        self._b2 = csr.CSRStorage(8, reset=0xB2)


class _DUT(Module):
    """Two banks at distinct paging addresses behind one CSR Interconnect."""
    PAGING  = 0x800
    BANK_A  = 0
    BANK_B  = 1
    BUS_DW  = 8

    def address_map(self, name, memory):
        return {
            "moda": self.BANK_A,
            "modb": self.BANK_B,
        }[name]

    def __init__(self):
        self.bus = csr_bus.Interface(data_width=self.BUS_DW)
        self.submodules.moda = _ModuleA()
        self.submodules.modb = _ModuleB()
        self.submodules.bankarray = csr_bus.CSRBankArray(
            source      = self,
            address_map = self.address_map,
            paging      = self.PAGING,
            data_width  = self.BUS_DW,
        )
        self.submodules.con = csr_bus.Interconnect(
            master = self.bus,
            slaves = self.bankarray.get_buses(),
        )


# Helpers ------------------------------------------------------------------------------------------

# CSRBank computes `aligned_paging = paging // 4` regardless of bus width, so the bank-selection
# bit lives at log2(paging//4) on the bus address. Compute the matching bank stride here.
ALIGNED_PAGING = _DUT.PAGING//4


def csr_addr(bank, index):
    return bank*ALIGNED_PAGING + index


def bus_read(bus, adr):
    """Like csr_bus.Interface.read but with an extra cycle to absorb the CSRBank's `sync`
    dat_r register. The built-in helper is one cycle short for sync banks."""
    yield bus.adr.eq(adr)
    yield bus.re.eq(1)
    yield
    yield
    value = (yield bus.dat_r)
    yield bus.re.eq(0)
    return value


def bus_write(bus, adr, dat):
    yield bus.adr.eq(adr)
    yield bus.dat_w.eq(dat)
    yield bus.we.eq(1)
    yield
    yield bus.we.eq(0)
    yield


# Tests --------------------------------------------------------------------------------------------

class TestCSRBusInterconnect(unittest.TestCase):
    def test_reset_values_are_visible_per_bank(self):
        dut = _DUT()

        def gen():
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_A, 0))), 0xA0)
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_A, 1))), 0xA1)
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_B, 0))), 0xB0)
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_B, 1))), 0xB1)
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_B, 2))), 0xB2)

        run_simulation(dut, gen())

    def test_writes_land_in_correct_bank(self):
        dut = _DUT()

        def gen():
            yield from bus_write(dut.bus,csr_addr(_DUT.BANK_A, 0), 0x55)
            yield from bus_write(dut.bus,csr_addr(_DUT.BANK_B, 1), 0xAA)
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_A, 0))), 0x55)
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_B, 1))), 0xAA)
            # Sibling registers must remain untouched.
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_A, 1))), 0xA1)
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_B, 0))), 0xB0)
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_B, 2))), 0xB2)

        run_simulation(dut, gen())

    def test_no_crosstalk_across_banks(self):
        # Writing to bank A must not bleed into bank B even at the same in-bank index.
        dut = _DUT()

        def gen():
            yield from bus_write(dut.bus,csr_addr(_DUT.BANK_A, 0), 0x12)
            yield from bus_write(dut.bus,csr_addr(_DUT.BANK_B, 0), 0x34)
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_A, 0))), 0x12)
            self.assertEqual((yield from bus_read(dut.bus,csr_addr(_DUT.BANK_B, 0))), 0x34)

        run_simulation(dut, gen())


if __name__ == "__main__":
    unittest.main()
