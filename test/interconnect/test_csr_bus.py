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


class TestCSRBankPaging(unittest.TestCase):
    # A CSRBank decodes its simple CSRs with bus.adr[:log2(paging//4)] == i and is mapped to a
    # single page. A bank with more than paging//4 simple CSRs used to silently roll its last
    # words over the page-select bits, aliasing them into the next module's bank (with the
    # generated csr.h still documenting them at the rolled-over addresses). Such a bank must
    # now be rejected at generation time.

    def test_bank_exceeding_paging_rejected(self):
        # One CSRStorage(32*513) on a 32-bit bus expands to 513 simple CSRs, one more than the
        # 512 CSRs/page of the default paging.
        with self.assertRaisesRegex(ValueError, "CSRs but paging only supports"):
            csr_bus.CSRBank(
                description = [csr.CSRStorage(32*513, name="blob")],
                address     = 0,
                bus         = csr_bus.Interface(data_width=32),
                paging      = 0x800,
            )

    def test_bank_exceeding_paging_rejected_through_bankarray(self):
        # Same rejection through CSRBankArray, with a reduced paging to keep the test small:
        # paging=0x10 allows 4 CSRs/page; the module below needs 5.
        class _WideMod(Module, csr.AutoCSR):
            def __init__(self):
                self._w = csr.CSRStorage(32, name="w")
                self._x = csr.CSRStorage(8,  name="x")

        class _DUTWide(Module):
            def address_map(self, name, memory):
                return {"widemod": 0}[name]

            def __init__(self):
                self.submodules.widemod = _WideMod()
                self.submodules.bankarray = csr_bus.CSRBankArray(
                    source      = self,
                    address_map = self.address_map,
                    paging      = 0x10,
                    data_width  = 8,
                )

        with self.assertRaisesRegex(ValueError, "CSRs but paging only supports"):
            _DUTWide()

    def test_bank_at_paging_capacity_does_not_alias_next_bank(self):
        # A bank with exactly paging//4 simple CSRs is still legal: its last word must decode
        # inside its own page and must not reach the next bank.
        class _ModA(Module, csr.AutoCSR):
            def __init__(self):
                self._w = csr.CSRStorage(32, name="w")  # 4 simple CSRs at data_width=8.

        class _ModB(Module, csr.AutoCSR):
            def __init__(self):
                self._b = csr.CSRStorage(8, name="b", reset=0xB0)

        class _DUTBoundary(Module):
            PAGING = 0x10  # 4 CSRs/page.

            def address_map(self, name, memory):
                return {"moda": 0, "modb": 1}[name]

            def __init__(self):
                self.bus = csr_bus.Interface(data_width=8)
                self.submodules.moda = _ModA()
                self.submodules.modb = _ModB()
                self.submodules.bankarray = csr_bus.CSRBankArray(
                    source      = self,
                    address_map = self.address_map,
                    paging      = self.PAGING,
                    data_width  = 8,
                )
                self.submodules.con = csr_bus.Interconnect(
                    master = self.bus,
                    slaves = self.bankarray.get_buses(),
                )

        dut = _DUTBoundary()
        last_word_of_a = 0 * (dut.PAGING//4) + 3
        bank_b_first   = 1 * (dut.PAGING//4) + 0

        def gen():
            # Bank B is reachable through its own page.
            yield from bus_write(dut.bus, bank_b_first, 0x0F)
            self.assertEqual((yield from bus_read(dut.bus, bank_b_first)), 0x0F)
            # Writing the last legal word of Bank A must not modify Bank B.
            yield from bus_write(dut.bus, last_word_of_a, 0x5A)
            self.assertEqual((yield from bus_read(dut.bus, last_word_of_a)), 0x5A)
            self.assertEqual((yield from bus_read(dut.bus, bank_b_first)),   0x0F)

        run_simulation(dut, gen())


if __name__ == "__main__":
    unittest.main()
