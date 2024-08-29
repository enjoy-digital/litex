#
# This file is part of LiteX
#
# Copyright (c) 2019-2024 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2024 MoTeC <www.motec.com.au>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.hyperbus import HyperRAM

def c2bool(c):
    return {"-": 1, "_": 0}[c]


class Pads: pass

class HyperRamPads:
    def __init__(self, dw=8):
        self.clk   = Signal()
        self.rst_n = Signal()
        self.cs_n  = Signal()
        self.dq    = Record([("oe", 1), ("o", dw),     ("i", dw)])
        self.rwds  = Record([("oe", 1), ("o", dw//8),  ("i", dw//8)])

class TestHyperRAM(unittest.TestCase):
    def test_hyperram_syntax(self):
        pads = Record([("clk", 1), ("rst_n", 1), ("cs_n", 1), ("dq", 8), ("rwds", 1)])
        hyperram = HyperRAM(pads)

        pads = Record([("clk_p", 1), ("clk_n", 1), ("rst_n", 1), ("cs_n", 1), ("dq", 8), ("rwds", 1)])
        hyperram = HyperRAM(pads)

    def test_hyperram_write_latency_5_2x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "----__________________________________________________________------"
            dq_oe   = "______------------____________________________________--------______"
            dq_o    = "0000002000048d0000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "______________________________________________________--------______"
            rwds_o  = "________________________________________________________----________"
            yield
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]),   (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]),  (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                if (yield dut.pads.dq.oe):
                    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield

        dut = HyperRAM(HyperRamPads(dw=8), latency=5, latency_mode="fixed")
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")

    def test_hyperram_write_latency_5_2x_sys2x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "________________--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "_------------__________________________________________________________------"
            dq_oe   = "_______________------------____________________________________--------______"
            dq_o    = "0000000000000002000048d0000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "_______________________________________________________________--------______"
            rwds_o  = "_________________________________________________________________----________"
            for i in range(len(clk)):
                self.assertEqual(c2bool(clk[i]), (yield dut.pads.clk))
                self.assertEqual(c2bool(cs_n[i]), (yield dut.pads.cs_n))
                self.assertEqual(c2bool(dq_oe[i]), (yield dut.pads.dq.oe))
                #if (yield dut.pads.dq.oe):
                #    self.assertEqual(int(dq_o[2*(i//2):2*(i//2)+2], 16), (yield dut.pads.dq.o))
                self.assertEqual(c2bool(rwds_oe[i]), (yield dut.pads.rwds.oe))
                self.assertEqual(c2bool(rwds_o[i]), (yield dut.pads.rwds.o))
                yield
            for i in range(128):
                yield

        dut = HyperRAM(HyperRamPads(), latency=5, latency_mode="fixed", clk_ratio="2:1")
        generators = {
            "sys"   : fpga_gen(dut),
            "sys2x" : hyperram_gen(dut),
        }
        clocks = {
            "sys"   : 4,
            "sys2x" : 2,
        }
        run_simulation(dut, generators, clocks, vcd_name="sim.vcd")

    def test_hyperram_write_latency_6_2x(self):
        def fpga_gen(dut):
            yield from dut.bus.write(0x1234, 0xdeadbeef, sel=0b1001)
            yield

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "----__________________________________________________________________------"
            dq_oe   = "______------------____________________________________________--------______"
            dq_o    = "0000002000048d000000000000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "______________________________________________________________--------______"
            rwds_o  = "________________________________________________________________----________"
            yield
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
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "----__________________________________________________________________________------"
            dq_oe   = "______------------____________________________________________________--------______"
            dq_o    = "0000002000048d00000000000000000000000000000000000000000000000000000000deadbeef000000"
            rwds_oe = "______________________________________________________________________--------______"
            rwds_o  = "________________________________________________________________________----________"
            yield
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
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--_______"
            cs_n    = "----______________________________________________------"
            dq_oe   = "______------------________________________--------______"
            dq_o    = "0000002000048d0000000000000000000000000000deadbeef000000"
            rwds_oe = "__________________________________________--------______"
            rwds_o  = "____________________________________________----________"
            yield
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

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_____"
            cs_n    = "----______________________________________________________________________________----"
            dq_oe   = "______------------____________________________________________________________________"
            dq_o    = "000000a000048d000000000000000000000000000000000000000000000000000000000000000000000000"
            dq_i    = "000000000000000000000000000000000000000000000000000000deadbeefcafefade0000000000000000"
            rwds_oe = "______________________________________________________________________________________"
            rwds_i  = "______________________________________________________--__--__--__--__________________"
            yield
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                yield dut.pads.rwds.i.eq(c2bool(rwds_i[i]))
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

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_____"
            cs_n    = "----______________________________________________________________________________________----"
            dq_oe   = "______------------____________________________________________________________________________"
            dq_o    = "000000a000048d00000000000000000000000000000000000000000000000000000000000000000000000000000000"
            dq_i    = "00000000000000000000000000000000000000000000000000000000000000deadbeefcafefade0000000000000000"
            rwds_oe = "______________________________________________________________________________________________"
            rwds_i  = "______________________________________________________________--__--__--__--__________________"
            yield
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                yield dut.pads.rwds.i.eq(c2bool(rwds_i[i]))
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


        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__--_____"
            cs_n    = "----______________________________________________________________________________________________----"
            dq_oe   = "______------------____________________________________________________________________________________"
            dq_o    = "000000a000048d0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
            dq_i    = "0000000000000000000000000000000000000000000000000000000000000000000000deadbeefcafefade0000000000000000"
            rwds_oe = "______________________________________________________________________________________________________"
            rwds_i  = "______________________________________________________________________--__--__--__--__________________"
            yield
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                yield dut.pads.rwds.i.eq(c2bool(rwds_i[i]))
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

        def hyperram_gen(dut):
            clk     = "_______--__--__--__--__--__--__--__--__--__--__--__--__--__--__--__-______"
            cs_n    = "----________________________________________________________________------"
            dq_oe   = "______------------________________________________________________________"
            dq_o    = "000000a000048d000000000000000000000000000000000000000000000000000000000000"
            dq_i    = "0000000000000000000000000000000000000000deadbeefcafefade000000000000000000"
            rwds_oe = "__________________________________________________________________________"
            rwds_i  = "________________________________________--__--__--__--____________________"
            yield
            for i in range(len(clk)):
                yield dut.pads.dq.i.eq(int(dq_i[2*(i//2):2*(i//2)+2], 16))
                yield dut.pads.rwds.i.eq(c2bool(rwds_i[i]))
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
            yield dut.core.reg.adr.eq(2)
            yield dut.core.reg.dat_w.eq(0x1234)
            yield
            yield dut.core.reg.stb.eq(1)
            yield dut.core.reg.we.eq(1)
            while (yield dut.core.reg.ack) == 0:
                yield
            yield dut.core.reg.stb.eq(0)

        def hyperram_gen(dut):
            clk     = "___________--__--__--__--___________"
            cs_n    = "--------__________________----------"
            dq_oe   = "__________----------------__________"
            dq_o    = "000000000060000100000012340000000000"
            rwds_oe = "____________________________________"
            rwds_o  = "____________________________________"
            yield
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
        run_simulation(dut, [fpga_gen(dut), hyperram_gen(dut)], vcd_name="sim.vcd")#