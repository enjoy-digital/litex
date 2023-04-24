#
# This file is part of LiteX.
#
# Copyright (c) 2023 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.interconnect import wishbone, avalon

# TestWishbone -------------------------------------------------------------------------------------

class TestAvalon2Wishbone(unittest.TestCase):

    def test_sram(self):
        def generator(dut):
            yield from dut.avl.bus_write(0x0000, 0x01234567)
            yield from dut.avl.bus_write(0x0004, 0x89abcdef)
            yield from dut.avl.bus_write(0x0008, 0xdeadbeef)
            yield from dut.avl.bus_write(0x000c, 0xc0ffee00)
            yield from dut.avl.bus_write(0x0010, 0x76543210)
            yield
            self.assertEqual((yield from dut.avl.bus_read(0x0000)), 0x01234567)
            self.assertEqual((yield from dut.avl.bus_read(0x0004)), 0x89abcdef)
            self.assertEqual((yield from dut.avl.bus_read(0x0008)), 0xdeadbeef)
            self.assertEqual((yield from dut.avl.bus_read(0x000c)), 0xc0ffee00)
            self.assertEqual((yield from dut.avl.bus_read(0x0010)), 0x76543210)

        class DUT(Module):
            def __init__(self):
                a2w = avalon.AvalonMM2Wishbone()
                self.wb  = a2w.wishbone
                self.avl = a2w.avalon
                wishbone_mem = wishbone.SRAM(32, bus=self.wb)
                self.submodules += a2w
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut)) #, vcd_name="avalon.vcd")

    def test_sram_burst_write(self):
        def generator(dut):
            yield from dut.avl.bus_write(0x0, [0x01234567, 0x89abcdef, 0xdeadbeef, 0xc0ffee00, 0x76543210])
            yield
            self.assertEqual((yield from dut.avl.bus_read(0x0000)), 0x01234567)
            self.assertEqual((yield from dut.avl.bus_read(0x0004)), 0x89abcdef)
            self.assertEqual((yield from dut.avl.bus_read(0x0008)), 0xdeadbeef)
            self.assertEqual((yield from dut.avl.bus_read(0x000c)), 0xc0ffee00)
            self.assertEqual((yield from dut.avl.bus_read(0x0010)), 0x76543210)

        class DUT(Module):
            def __init__(self):
                a2w = avalon.AvalonMM2Wishbone()
                self.wb  = a2w.wishbone
                self.avl = a2w.avalon
                wishbone_mem = wishbone.SRAM(32, bus=self.wb)
                self.submodules += a2w
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut)) # , vcd_name="avalon_burst.vcd")
