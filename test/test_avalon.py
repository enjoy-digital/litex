#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.interconnect import wishbone, avalon

# TestWishbone -------------------------------------------------------------------------------------

class TestAvalon2Wishbone(unittest.TestCase):

    def test_sram(self):
        def generator(dut):
            yield from dut.avl.bus_write(0x0000, 0x01234567)
            yield from dut.avl.bus_write(0x0001, 0x89abcdef)
            yield from dut.avl.bus_write(0x0002, 0xdeadbeef)
            yield from dut.avl.bus_write(0x0003, 0xc0ffee00)
            yield from dut.avl.bus_write(0x0004, 0x76543210)
            self.assertEqual((yield from dut.avl.bus_read(0x0000)), 0x01234567)
            self.assertEqual((yield from dut.avl.bus_read(0x0001)), 0x89abcdef)
            self.assertEqual((yield from dut.avl.bus_read(0x0002)), 0xdeadbeef)
            self.assertEqual((yield from dut.avl.bus_read(0x0003)), 0xc0ffee00)
            self.assertEqual((yield from dut.avl.bus_read(0x0004)), 0x76543210)

        class DUT(Module):
            def __init__(self):
                a2w = avalon.Avalon2Wishbone()
                self.wb  = a2w.wishbone
                self.avl = a2w.avalon
                wishbone_mem = wishbone.SRAM(32, bus=self.wb)
                self.submodules += a2w
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut)) # , vcd_name="avalon.vcd")
