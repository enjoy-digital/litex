#
# This file is part of LiteHyperBus
#
# Copyright (c) 2019-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.hyperbus import HyperRAM

def c2bool(c):
    return {"-": 1, "_": 0}[c]


class Pads: pass


class HyperRamPads:
    def __init__(self, dw=8):
        self.clk  = Signal()
        self.cs_n = Signal()
        self.dq   = Record([("oe", 1), ("o", dw),     ("i", dw)])
        self.rwds = Record([("oe", 1), ("o", dw//8),  ("i", dw//8)])


class TestHyperBus(unittest.TestCase):
    def test_hyperram_syntax(self):
        pads = Record([("clk", 1), ("cs_n", 1), ("dq", 8), ("rwds", 1)])
        hyperram = HyperRAM(pads)

        pads = Record([("clk_p", 1), ("clk_n", 1), ("cs_n", 1), ("dq", 8), ("rwds", 1)])
        hyperram = HyperRAM(pads)

    def test_hyperram_write(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "___--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "--________________________________________________________________------"
            dq_oe   = "__------------____________________________________________--------______"
            dq_o    = "002000048d000000000000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "__________________________________________________________--------______"
            rwds_o  = "____________________________________________________________----________"
            for i in range(3):
                yield
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads())
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_read(self):
        def fpga_gen(dut):
            dat = yield from dut.bus.read(0x1234)
            self.assertEqual(dat, 0xdeadbeef)
            dat = yield from dut.bus.read(0x1235)
            self.assertEqual(dat, 0xcafefade)

        def hyperram_gen(dut):
            clk     = "___--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_"
            cs_n    = "--________________________________________________________________________________"
            dq_oe   = "__------------____________________________________________________________________"
            dq_o    = "00a000048d000000000000000000000000000000000000000000000000000000000000000000000000"
            dq_i    = "0000000000000000000000000000000000000000000000000000000000deadbeefcafefade00000000"
            rwds_oe = "__________________________________________________________________________________"
            for i in range(3):
                yield
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                yield

        dut = HyperRAM(HyperRamPads())
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")
