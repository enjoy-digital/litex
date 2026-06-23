#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import *

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.ahb import AHBInterface, AHB2Wishbone, AHBTransferType


# Helpers ------------------------------------------------------------------------------------------

# AHB transfer "size" field: log2(bytes).
SIZE_WORD = 0b10  # 4-byte access (matches 32-bit wishbone).


def _wait_for_readyout_cycle(ahb):
    """Wait for readyout to drop (transaction accepted) then rise again (transaction done).

    The two-stage wait is needed because between transactions readyout is already 1; without
    confirming the drop, the loop would exit before the new transaction ever started.
    """
    timeout = 0
    while (yield ahb.readyout):
        yield
        timeout += 1
        assert timeout < 1000, "AHB transaction never started"
    while not (yield ahb.readyout):
        yield
        timeout += 1
        assert timeout < 1000, "AHB transaction never completed"


def ahb_write(ahb, addr, data, size=SIZE_WORD):
    yield ahb.addr.eq(addr)
    yield ahb.sel.eq(1)
    yield ahb.size.eq(size)
    yield ahb.trans.eq(int(AHBTransferType.NONSEQUENTIAL))
    yield ahb.write.eq(1)
    yield ahb.wdata.eq(data)
    yield
    yield ahb.trans.eq(int(AHBTransferType.IDLE))
    yield ahb.sel.eq(0)
    yield from _wait_for_readyout_cycle(ahb)


def ahb_read(ahb, addr, size=SIZE_WORD):
    yield ahb.addr.eq(addr)
    yield ahb.sel.eq(1)
    yield ahb.size.eq(size)
    yield ahb.trans.eq(int(AHBTransferType.NONSEQUENTIAL))
    yield ahb.write.eq(0)
    yield
    yield ahb.trans.eq(int(AHBTransferType.IDLE))
    yield ahb.sel.eq(0)
    yield from _wait_for_readyout_cycle(ahb)
    return (yield ahb.rdata)


# DUT ----------------------------------------------------------------------------------------------

class _AHB2WishboneDUT(LiteXModule):
    """AHB master → AHB2Wishbone bridge → wishbone.SRAM slave."""
    def __init__(self, mem_size=64):
        self.ahb = AHBInterface(data_width=32, address_width=32)
        self.wb  = wishbone.Interface(data_width=32, adr_width=30, addressing="word")
        self.submodules.bridge = AHB2Wishbone(self.ahb, self.wb)
        self.submodules.sram   = wishbone.SRAM(mem_size, bus=self.wb)


# Tests --------------------------------------------------------------------------------------------

class TestAHB2Wishbone(unittest.TestCase):
    def test_write_then_read(self):
        dut = _AHB2WishboneDUT()

        def gen():
            yield from ahb_write(dut.ahb, 0x00, 0xdeadbeef)
            yield from ahb_write(dut.ahb, 0x04, 0xcafebabe)
            yield from ahb_write(dut.ahb, 0x08, 0x12345678)
            self.assertEqual((yield from ahb_read(dut.ahb, 0x00)), 0xdeadbeef)
            self.assertEqual((yield from ahb_read(dut.ahb, 0x04)), 0xcafebabe)
            self.assertEqual((yield from ahb_read(dut.ahb, 0x08)), 0x12345678)

        run_simulation(dut, gen())

    def test_read_of_unwritten_word_is_zero(self):
        dut = _AHB2WishboneDUT()

        def gen():
            self.assertEqual((yield from ahb_read(dut.ahb, 0x10)), 0)

        run_simulation(dut, gen())

    def test_interleaved_access(self):
        # Write, read back, write same address, read again — verifies no stale state leaks
        # between transactions.
        dut = _AHB2WishboneDUT()

        def gen():
            yield from ahb_write(dut.ahb, 0x00, 0x11111111)
            self.assertEqual((yield from ahb_read(dut.ahb, 0x00)), 0x11111111)
            yield from ahb_write(dut.ahb, 0x00, 0x22222222)
            self.assertEqual((yield from ahb_read(dut.ahb, 0x00)), 0x22222222)

        run_simulation(dut, gen())


if __name__ == "__main__":
    unittest.main()
