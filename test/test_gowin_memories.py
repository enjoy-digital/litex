#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen.fhdl.verilog import convert

from litex.build.gowin.gowin import _gowin_async_read_memories

# Gowin Memories -----------------------------------------------------------------------------------

class TestGowinMemories(unittest.TestCase):
    def verilog(self):
        class DUT(Module):
            def __init__(self):
                self.clock_domains.cd_sys = ClockDomain()
                self.adr  = Signal(4)
                self.dat  = Signal(8)
                self.o1   = Signal(8)
                self.o2   = Signal(8)
                self.o3   = Signal(8)
                # Asynchronous read.
                mem1 = Memory(8, 16)
                wp1  = mem1.get_port(write_capable=True)
                rp1  = mem1.get_port(async_read=True)
                # Synchronous read.
                mem2 = Memory(8, 16)
                wp2  = mem2.get_port(write_capable=True)
                rp2  = mem2.get_port()
                # Asynchronous read, initialized (ROM).
                mem3 = Memory(8, 16, init=list(range(16)))
                rp3  = mem3.get_port(async_read=True)
                self.specials += mem1, wp1, rp1, mem2, wp2, rp2, mem3, rp3
                self.comb += [
                    wp1.adr.eq(self.adr), wp1.dat_w.eq(self.dat), wp1.we.eq(1), rp1.adr.eq(~self.adr),
                    wp2.adr.eq(self.adr), wp2.dat_w.eq(self.dat), wp2.we.eq(1), rp2.adr.eq(~self.adr),
                    rp3.adr.eq(self.adr),
                    self.o1.eq(rp1.dat_r), self.o2.eq(rp2.dat_r), self.o3.eq(rp3.dat_r),
                ]
        dut = DUT()
        return str(convert(dut, ios={dut.cd_sys.clk, dut.cd_sys.rst, dut.adr, dut.dat, dut.o1, dut.o2, dut.o3}, name="top"))

    def test_async_read_memories(self):
        v = self.verilog()
        v, names = _gowin_async_read_memories(v)
        self.assertEqual(len(names), 2)
        self.assertEqual(v.count('syn_ramstyle = "distributed_ram"'), 2)
        # Idempotent: memories with a syn_ramstyle are kept.
        v2, names2 = _gowin_async_read_memories(v)
        self.assertEqual(names2, [])
        self.assertEqual(v2, v)
