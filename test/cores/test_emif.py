#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.interconnect import wishbone

from litex.soc.cores.emif import EMIF


class EMIFPads:
    def __init__(self):
        self.cs_n   = Signal(reset=1)
        self.we_n   = Signal(reset=1)
        self.oe_n   = Signal(reset=1)
        self.wait_n = Signal(reset=1)
        self.ba     = Signal(2)
        self.addr   = Signal(22)
        self.dqm_n  = Signal(2)
        self.data   = Record([("oe", 1), ("o", 16), ("i", 16)])


def emif_write(pads, addr, data, release_cs=True):
    for i in range(2):
        yield pads.cs_n.eq(0)
        yield pads.we_n.eq(1)
        yield pads.oe_n.eq(1)
        yield pads.ba.eq(1<<i)
        yield pads.addr.eq(addr)
        yield pads.data.i.eq((data >> 16*i) & 0xffff)
        yield
        yield pads.we_n.eq(0)
        for i in range(8):
            yield
        yield pads.we_n.eq(1)
        yield
        yield pads.cs_n.eq(release_cs)
        yield


def emif_read(pads, addr, release_cs=True, release_oe=True):
    data = 0
    for i in range(2):
        yield pads.cs_n.eq(0)
        yield pads.we_n.eq(1)
        yield pads.oe_n.eq(release_oe)
        yield pads.ba.eq(1<<i)
        yield pads.addr.eq(addr)
        yield
        yield pads.oe_n.eq(0)
        for i in range(8):
            yield
        data >>= 16
        data |= (yield pads.data.o) << 16
        yield pads.oe_n.eq(release_oe)
        yield
        yield pads.cs_n.eq(release_cs)
        yield
    return data


class TestEMIF(unittest.TestCase):
    def test_emif(self):
        pads = EMIFPads()
        def generator(dut):
            # Test writes/reads with cs release between accesses
            yield from emif_write(pads, 0, 0xdeadbeef, True)
            yield from emif_write(pads, 1, 0x12345678, True)
            yield from emif_write(pads, 2, 0x5aa55aa5, True)
            self.assertEqual((yield from emif_read(pads, 0, True)), 0xdeadbeef)
            self.assertEqual((yield from emif_read(pads, 1, True)), 0x12345678)
            self.assertEqual((yield from emif_read(pads, 2, True)), 0x5aa55aa5)

            # Test writes/reads without cs release between accesses
            yield from emif_write(pads, 0, 0xdeadbeef, False)
            yield from emif_write(pads, 1, 0x12345678, False)
            yield from emif_write(pads, 2, 0x5aa55aa5, False)
            self.assertEqual((yield from emif_read(pads, 0, False)), 0xdeadbeef)
            self.assertEqual((yield from emif_read(pads, 1, False)), 0x12345678)
            self.assertEqual((yield from emif_read(pads, 2, False)), 0x5aa55aa5)

        class DUT(Module):
            def __init__(self, pads):
                emif = EMIF(pads)
                self.submodules += emif
                mem = wishbone.SRAM(16, bus=emif.bus)
                self.submodules += mem
        dut = DUT(pads)
        run_simulation(dut, [generator(dut)])
