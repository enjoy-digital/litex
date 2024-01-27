#
# This file is part of LiteX.
#
# Copyright (c) 2022-2023 MoTeC
# Copyright (c) 2022-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *

from litex.gen.sim import *

from litex.soc.cores.spi.spi_mmap import SPIMaster

class TestSPIMMAP(unittest.TestCase):
    def test_spi_master(self):
        pads = Record([("clk", 1), ("cs_n", 4), ("mosi", 1), ("miso", 1)])
        dut  = SPIMaster(pads=pads, data_width=32, sys_clk_freq=int(100e6))
        def generator(dut):
            data = [
                0x12345678,
                0xdeadbeef,
            ]
            #data = [
            #    0x80000001,
            #    0x80000001,
            #]

            # Config: Mode0, Loopback, Sys-Clk/4
            yield dut.loopback.eq(1)
            yield dut.clk_divider.eq(4)
            yield dut.mode.eq(0)
            yield
            yield dut.mosi.eq(data[0])
            yield dut.cs.eq(0b0001)
            yield dut.length.eq(32)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            while (yield dut.done) == 0b0:
                yield
            yield dut.cs.eq(0b0000)
            for i in range(16):
                yield
            print(f"mosi_data : {(yield dut.miso):08x}")

            # Config: Mode3, Loopback, Sys-Clk/4.
            yield dut.loopback.eq(1)
            yield dut.clk_divider.eq(4)
            yield dut.mode.eq(3)
            yield
            yield dut.mosi.eq(data[0])
            yield dut.cs.eq(0b0001)
            yield dut.length.eq(32)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            while (yield dut.done) == 0b0:
                yield
            yield dut.cs.eq(0b0000)
            for i in range(16):
                yield
            print(f"mosi_data : {(yield dut.miso):08x}")

            # Config: Mode0, Loopback, Sys-Clk/8.
            yield dut.loopback.eq(1)
            yield dut.clk_divider.eq(8)
            yield dut.mode.eq(0)
            yield
            yield dut.mosi.eq(data[1])
            yield dut.cs.eq(0b0001)
            yield dut.length.eq(32)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            while (yield dut.done) == 0b0:
                yield
            yield dut.cs.eq(0b0000)
            for i in range(16):
                yield
            print(f"mosi_data : {(yield dut.miso):08x}")

            # Config: Mode3, Loopback, Sys-Clk/8.
            yield dut.loopback.eq(1)
            yield dut.clk_divider.eq(8)
            yield dut.mode.eq(3)
            yield
            yield dut.mosi.eq(data[1])
            yield dut.cs.eq(0b0001)
            yield dut.length.eq(32)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            while (yield dut.done) == 0b0:
                yield
            yield dut.cs.eq(0b0000)
            for i in range(16):
                yield
            print(f"mosi_data : {(yield dut.miso):08x}")

        run_simulation(dut, generator(dut), vcd_name="sim.vcd")
