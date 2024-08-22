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

    def test_hyperram_write_latency_5_2x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "___--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "--________________________________________________________------"
            dq_oe   = "__------------____________________________________--------______"
            dq_o    = "002000048d0000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "__________________________________________________--------______"
            rwds_o  = "____________________________________________________----________"
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(), latency=5, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_write_latency_5_2x_sys2x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "____--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "--________________________________________________________-------"
            dq_oe   = "___------------____________________________________--------______"
            dq_o    = "0002000048d0000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "___________________________________________________--------______"
            rwds_o  = "_____________________________________________________----________"
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                #if (yield dut.pads.dq.oe):
                #    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(), latency=5, latency_mode="fixed", clk_ratio="2:1")
        generators = {
            "sys"   : fpga_gen(dut),
            "sys2x" : hyperram_gen(dut),
        }
        clocks = {
            "sys"      : 4,
            "sys2x"    : 2,
            "sys2x_ps" : 2,
        }
        run_simulation(dut, generators, clocks, vcd_name="sim.vcd")

    def test_hyperram_write_latency_6_2x(self):
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
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(), latency=6, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_write_latency_7_2x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "___--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "--________________________________________________________________________------"
            dq_oe   = "__------------____________________________________________________--------______"
            dq_o    = "002000048d00000000000000000000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "__________________________________________________________________--------______"
            rwds_o  = "____________________________________________________________________----________"
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(), latency=7, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_write_latency_7_1x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "___--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "--____________________________________________------"
            dq_oe   = "__------------________________________--------______"
            dq_o    = "002000048d0000000000000000000000000000deadbeef000000"
            rwds_oe = "______________________________________--------______"
            rwds_o  = "________________________________________----________"
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(), latency=7, latency_mode="variable")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_read_latency_5_2x(self):
        def fpga_gen(dut):
            dat = yield from dut.bus.read(0x1234)
            self.assertEqual(dat, 0xdeadbeef)
            dat = yield from dut.bus.read(0x1235)
            self.assertEqual(dat, 0xcafefade)

        def hyperram_gen(dut):
            clk     = "___--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_"
            cs_n    = "--________________________________________________________________________"
            dq_oe   = "__------------____________________________________________________________"
            dq_o    = "00a000048d0000000000000000000000000000000000000000000000000000000000000000"
            dq_i    = "00000000000000000000000000000000000000000000000000deadbeefcafefade00000000"
            rwds_oe = "__________________________________________________________________________"
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                yield

        dut = HyperRAM(HyperRamPads(), latency=5, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_read_latency_6_2x(self):
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
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                yield

        dut = HyperRAM(HyperRamPads(), latency=6, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_read_latency_7_2x(self):
        def fpga_gen(dut):
            dat = yield from dut.bus.read(0x1234)
            self.assertEqual(dat, 0xdeadbeef)
            dat = yield from dut.bus.read(0x1235)
            self.assertEqual(dat, 0xcafefade)

        def hyperram_gen(dut):
            clk     = "___--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_"
            cs_n    = "--________________________________________________________________________________________"
            dq_oe   = "__------------____________________________________________________________________________"
            dq_o    = "00a000048d00000000000000000000000000000000000000000000000000000000000000000000000000000000"
            dq_i    = "000000000000000000000000000000000000000000000000000000000000000000deadbeefcafefade00000000"
            rwds_oe = "__________________________________________________________________________________________"
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                yield

        dut = HyperRAM(HyperRamPads(), latency=7, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_read_latency_7_1x(self):
        def fpga_gen(dut):
            dat = yield from dut.bus.read(0x1234)
            self.assertEqual(dat, 0xdeadbeef)
            dat = yield from dut.bus.read(0x1235)
            self.assertEqual(dat, 0xcafefade)

        def hyperram_gen(dut):
            clk     = "___--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_"
            cs_n    = "--____________________________________________________________"
            dq_oe   = "__------------________________________________________________"
            dq_o    = "00a000048d0000000000000000000000000000000000000000000000000000"
            dq_i    = "00000000000000000000000000000000000000deadbeefcafefade00000000"
            rwds_oe = "______________________________________________________________"
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                yield

        dut = HyperRAM(HyperRamPads(), latency=7, latency_mode="variable")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_reg_write(self):
        def fpga_gen(dut):
            yield dut.reg_addr.eq(2)
            yield dut.reg_wr_data.eq(0x1234)
            yield
            yield dut.reg_wr.eq(1)
            yield
            yield dut.reg_wr.eq(0)
            for i in range(128):
                yield

        def hyperram_gen(dut):
            clk     = "_____--__--__--__--___________"
            cs_n    = "----________________----------"
            dq_oe   = "____----------------__________"
            dq_o    = "000060000100000012340000000000"
            rwds_oe = "______________________________"
            rwds_o  = "______________________________"
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(), with_csr=False)
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")