#
# This file is part of LiteX.
#
# Copyright (c) 2023 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.interconnect import wishbone, avalon

# Helpers ------------------------------------------------------------------------------------------

def apply_byteenable(current, value, byteenable, byte_lanes):
    result = current
    for byte in range(byte_lanes):
        if (byteenable >> byte) & 0x1:
            mask   = 0xff << (8*byte)
            result = (result & ~mask) | (value & mask)
    return result


@passive
def delayed_wishbone_memory_handler(bus, memory, latencies):
    latency_index = 0

    yield bus.ack.eq(0)
    yield bus.err.eq(0)
    yield bus.dat_r.eq(0)

    while True:
        if (yield bus.cyc) and (yield bus.stb):
            adr     = (yield bus.adr)
            we      = (yield bus.we)
            sel     = (yield bus.sel)
            dat_w   = (yield bus.dat_w)
            latency = latencies[latency_index % len(latencies)]
            latency_index += 1

            if not we:
                yield bus.dat_r.eq(memory.get(adr, 0))

            for _ in range(latency):
                yield

            if we:
                memory[adr] = apply_byteenable(memory.get(adr, 0), dat_w, sel, len(bus.sel))
            else:
                yield bus.dat_r.eq(memory.get(adr, 0))

            yield bus.ack.eq(1)
            yield
            yield bus.ack.eq(0)

        yield

# TestWishbone -------------------------------------------------------------------------------------

class TestAvalon2Wishbone(unittest.TestCase):
    def burst_latency_test(self, avoid_combinatorial_loop):
        latencies = [0, 2, 1, 3, 0, 1]
        base      = 0x10
        values    = [
            0x01234567,
            0x89abcdef,
            0xdeadbeef,
            0xc0ffee00,
            0x76543210,
            0x55aa55aa,
        ]

        def generator(dut):
            yield from dut.avl.bus_write(base, values)
            yield
            self.assertEqual((yield from dut.avl.bus_read(base, burstcount=len(values))), values[0])
            self.assertEqual((yield dut.avl.readdatavalid), 1)
            for expected in values[1:]:
                self.assertEqual((yield from dut.avl.continue_read_burst()), expected)
                self.assertEqual((yield dut.avl.readdatavalid), 1)

            yield
            self.assertEqual((yield from dut.avl.bus_read(base + 2)), values[2])
            yield from dut.avl.bus_write(base + 1, 0x11223344, byteenable=0b0011)
            self.assertEqual((yield from dut.avl.bus_read(base + 1)), 0x89ab3344)

        class DUT(Module):
            def __init__(self):
                self.a2w = avalon.AvalonMM2Wishbone(avoid_combinatorial_loop=avoid_combinatorial_loop)
                self.avl = self.a2w.a2w_avl
                self.submodules += self.a2w

        dut = DUT()
        memory = {}
        run_simulation(dut, [generator(dut), delayed_wishbone_memory_handler(dut.a2w.a2w_wb, memory, latencies)])

    def test_sram(self):
        def generator(dut):
            yield from dut.avl.bus_write(0x0000, 0x01234567)
            yield from dut.avl.bus_write(0x0001, 0x89abcdef)
            yield from dut.avl.bus_write(0x0002, 0xdeadbeef)
            yield from dut.avl.bus_write(0x0003, 0xc0ffee00)
            yield from dut.avl.bus_write(0x0004, 0x76543210)
            yield
            self.assertEqual((yield from dut.avl.bus_read(0x0000)), 0x01234567)
            self.assertEqual((yield from dut.avl.bus_read(0x0001)), 0x89abcdef)
            self.assertEqual((yield from dut.avl.bus_read(0x0002)), 0xdeadbeef)
            self.assertEqual((yield from dut.avl.bus_read(0x0003)), 0xc0ffee00)
            self.assertEqual((yield from dut.avl.bus_read(0x0004)), 0x76543210)

        class DUT(Module):
            def __init__(self):
                a2w = avalon.AvalonMM2Wishbone()
                self.avl = a2w.a2w_avl
                wishbone_mem = wishbone.SRAM(32, bus=a2w.a2w_wb)
                self.submodules += a2w
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut)) #, vcd_name="avalon.vcd")

    def test_sram_burst(self):
        def generator(dut):
            yield from dut.avl.bus_write(0x0, [0x01234567, 0x89abcdef, 0xdeadbeef, 0xc0ffee00, 0x76543210])
            yield
            self.assertEqual((yield from dut.avl.bus_read(0x0000, burstcount=5)), 0x01234567)
            self.assertEqual((yield dut.avl.readdatavalid), 1)
            self.assertEqual((yield from dut.avl.continue_read_burst()), 0x89abcdef)
            self.assertEqual((yield dut.avl.readdatavalid), 1)
            self.assertEqual((yield from dut.avl.continue_read_burst()), 0xdeadbeef)
            self.assertEqual((yield dut.avl.readdatavalid), 1)
            self.assertEqual((yield from dut.avl.continue_read_burst()), 0xc0ffee00)
            self.assertEqual((yield dut.avl.readdatavalid), 1)
            self.assertEqual((yield from dut.avl.continue_read_burst()), 0x76543210)
            yield
            yield
            yield
            yield
            self.assertEqual((yield from dut.avl.bus_read(0x0000)), 0x01234567)
            self.assertEqual((yield from dut.avl.bus_read(0x0001)), 0x89abcdef)
            self.assertEqual((yield from dut.avl.bus_read(0x0002)), 0xdeadbeef)
            self.assertEqual((yield from dut.avl.bus_read(0x0003)), 0xc0ffee00)
            self.assertEqual((yield from dut.avl.bus_read(0x0004)), 0x76543210)
            yield
            yield

        class DUT(Module):
            def __init__(self):
                a2w = avalon.AvalonMM2Wishbone()
                self.avl = a2w.a2w_avl
                wishbone_mem = wishbone.SRAM(32, bus=a2w.a2w_wb)
                self.submodules += a2w
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut)) #, vcd_name="avalon_burst.vcd")

    def test_burst_variable_latency(self):
        self.burst_latency_test(avoid_combinatorial_loop=False)

    def test_burst_variable_latency_avoid_combinatorial_loop(self):
        self.burst_latency_test(avoid_combinatorial_loop=True)
