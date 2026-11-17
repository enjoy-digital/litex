#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *
from migen.fhdl.specials import Tristate

from litex.soc.cores.ram.async_sram import AsyncSRAM
from litex.soc.interconnect import wishbone


# Helpers ------------------------------------------------------------------------------------------

class _AsyncSRAMPads:
    def __init__(self, address_width=19, data_width=8):
        self.ce  = Signal(reset=1)
        self.oe  = Signal(reset=1)
        self.we  = Signal(reset=1)
        self.adr = Signal(address_width)
        self.dat = Signal(data_width)


class _IgnoreTristate:
    @staticmethod
    def lower(t):
        return Module()


class _DUT(Module):
    def __init__(self, read_cycles=2, write_cycles=3, setup_cycles=0, hold_cycles=0):
        self.pads = _AsyncSRAMPads()
        self.bus  = wishbone.Interface(data_width=32)
        self.submodules.sram = AsyncSRAM(
            pads         = self.pads,
            bus          = self.bus,
            read_cycles  = read_cycles,
            write_cycles = write_cycles,
            setup_cycles = setup_cycles,
            hold_cycles  = hold_cycles)


def _byte_addr(word_addr, byte):
    return 4*word_addr + byte


def _word_from_memory(memory, word_addr):
    value = 0
    for byte in range(4):
        value |= memory.get(_byte_addr(word_addr, byte), 0) << (8*byte)
    return value


def _async_sram_model(testcase, dut, memory, read_log=None, write_log=None):
    @passive
    def model():
        while True:
            ce_n = (yield dut.pads.ce)
            oe_n = (yield dut.pads.oe)
            we_n = (yield dut.pads.we)
            adr  = (yield dut.pads.adr)

            if ce_n == 0 and we_n == 0:
                testcase.assertEqual((yield dut.sram.dat_oe), 1)
                data = (yield dut.sram.dat_o)
                memory[adr] = data
                if write_log is not None:
                    write_log.append((adr, data))

            if ce_n == 0 and oe_n == 0 and we_n == 1:
                if read_log is not None:
                    read_log.append(adr)
                yield dut.sram.dat_i.eq(memory.get(adr, 0))
            else:
                yield dut.sram.dat_i.eq(0)

            yield

    return model()


# 16-bit Helpers -----------------------------------------------------------------------------------

class _AsyncSRAM16Pads:
    def __init__(self, address_width=18, byte_enables="lb_n/ub_n"):
        self.ce_n = Signal(reset=1)
        self.oe_n = Signal(reset=1)
        self.we_n = Signal(reset=1)
        self.a    = Signal(address_width)
        self.dq   = Signal(16)
        if byte_enables == "lb_n/ub_n":
            self.lb_n = Signal(reset=1)
            self.ub_n = Signal(reset=1)
        if byte_enables == "be_n":
            self.be_n = Signal(2, reset=0b11)


class _AsyncSRAM16Model(Module):
    """16-bit asynchronous SRAM: combinatorial read, write while WE is low, byte enables."""
    def __init__(self, pads, sram, depth=64):
        self.mem = mem = Memory(16, depth)
        rp = mem.get_port(async_read=True)
        wp = mem.get_port(write_capable=True, we_granularity=8)
        self.specials += mem, rp, wp

        # # #

        be_n  = pads.be_n if hasattr(pads, "be_n") else Cat(pads.lb_n, pads.ub_n)
        read  = Signal()
        write = Signal()
        self.comb += [
            read.eq( ~pads.ce_n & ~pads.oe_n &  pads.we_n),
            write.eq(~pads.ce_n & ~pads.we_n),
            rp.adr.eq(pads.a),
            wp.adr.eq(pads.a),
            # Junk on the bytes that are not driven by the SRAM, and written when not driven.
            sram.dat_i[:8].eq(Mux(read & ~be_n[0], rp.dat_r[:8], 0x5a)),
            sram.dat_i[8:].eq(Mux(read & ~be_n[1], rp.dat_r[8:], 0xa5)),
            wp.dat_w.eq(Mux(sram.dat_oe, sram.dat_o, 0xdead)),
            wp.we.eq(Replicate(write, 2) & ~be_n),
        ]


class _DUT16(Module):
    def __init__(self, byte_enables="lb_n/ub_n", **kwargs):
        self.pads = _AsyncSRAM16Pads(byte_enables=byte_enables)
        self.submodules.sram  = AsyncSRAM(pads=self.pads, **kwargs)
        self.submodules.model = _AsyncSRAM16Model(self.pads, self.sram)
        self.bus = self.sram.bus


@passive
def _pads_monitor(dut, log):
    # Pads of each cycle with CE low: (a, oe_n, we_n, lb_n, ub_n, dat_oe).
    while True:
        if (yield dut.pads.ce_n) == 0:
            log.append((
                (yield dut.pads.a),
                (yield dut.pads.oe_n),
                (yield dut.pads.we_n),
                (yield dut.pads.lb_n),
                (yield dut.pads.ub_n),
                (yield dut.sram.dat_oe),
            ))
        yield


# Tests --------------------------------------------------------------------------------------------

class TestAsyncSRAM(unittest.TestCase):
    def run_dut(self, dut, generator, memory=None, read_log=None, write_log=None):
        if memory is None:
            memory = {}
        run_simulation(dut, [
            generator(),
            _async_sram_model(self, dut, memory, read_log, write_log),
        ], special_overrides={Tristate: _IgnoreTristate})

    def test_instantiation(self):
        dut = _DUT()
        self.assertEqual(dut.bus.data_width, 32)
        self.assertEqual(len(dut.pads.dat), 8)
        self.assertEqual(len(dut.pads.adr), 19)

    def test_full_word_write_and_readback(self):
        dut = _DUT()
        memory = {}
        word_addr = 4

        def generator():
            yield from dut.bus.write(word_addr, 0x78563412)
            self.assertEqual(memory[_byte_addr(word_addr, 0)], 0x12)
            self.assertEqual(memory[_byte_addr(word_addr, 1)], 0x34)
            self.assertEqual(memory[_byte_addr(word_addr, 2)], 0x56)
            self.assertEqual(memory[_byte_addr(word_addr, 3)], 0x78)
            self.assertEqual((yield from dut.bus.read(word_addr)), 0x78563412)

        self.run_dut(dut, generator, memory)

    def test_byte_select_write_preserves_unselected_bytes(self):
        dut = _DUT()
        memory = {}
        word_addr = 7
        for byte, value in enumerate([0xaa, 0xbb, 0xcc, 0xdd]):
            memory[_byte_addr(word_addr, byte)] = value

        def generator():
            yield from dut.bus.write(word_addr, 0x11223344, sel=0b1010)
            self.assertEqual(memory[_byte_addr(word_addr, 0)], 0xaa)
            self.assertEqual(memory[_byte_addr(word_addr, 1)], 0x33)
            self.assertEqual(memory[_byte_addr(word_addr, 2)], 0xcc)
            self.assertEqual(memory[_byte_addr(word_addr, 3)], 0x11)
            self.assertEqual((yield from dut.bus.read(word_addr)), 0x11cc33aa)

        self.run_dut(dut, generator, memory)

    def test_read_byte_address_sequence(self):
        dut = _DUT(read_cycles=2)
        memory = {}
        read_log = []
        word_addr = 9
        for byte, value in enumerate([0xde, 0xad, 0xbe, 0xef]):
            memory[_byte_addr(word_addr, byte)] = value

        def generator():
            self.assertEqual((yield from dut.bus.read(word_addr)), 0xefbeadde)

        self.run_dut(dut, generator, memory, read_log=read_log)
        self.assertEqual(read_log, [
            _byte_addr(word_addr, 0), _byte_addr(word_addr, 0),
            _byte_addr(word_addr, 1), _byte_addr(word_addr, 1),
            _byte_addr(word_addr, 2), _byte_addr(word_addr, 2),
            _byte_addr(word_addr, 3), _byte_addr(word_addr, 3),
        ])

    def test_write_select_controls_byte_strobes(self):
        dut = _DUT(write_cycles=3)
        memory = {}
        write_log = []
        word_addr = 2

        def generator():
            yield from dut.bus.write(word_addr, 0xa1b2c3d4, sel=0b0101)

        self.run_dut(dut, generator, memory, write_log=write_log)
        self.assertEqual(write_log, [
            (_byte_addr(word_addr, 0), 0xd4),
            (_byte_addr(word_addr, 0), 0xd4),
            (_byte_addr(word_addr, 0), 0xd4),
            (_byte_addr(word_addr, 2), 0xb2),
            (_byte_addr(word_addr, 2), 0xb2),
            (_byte_addr(word_addr, 2), 0xb2),
        ])
        self.assertEqual(_word_from_memory(memory, word_addr), 0x00b200d4)

    # 16-bit SRAM.

    def run_dut16(self, dut, generator, log=None):
        generators = [generator()]
        if log is not None:
            generators.append(_pads_monitor(dut, log))
        run_simulation(dut, generators, special_overrides={Tristate: _IgnoreTristate})

    def test_16bit_full_word_write_and_readback(self):
        for byte_enables in ["lb_n/ub_n", "be_n"]:
            with self.subTest(byte_enables=byte_enables):
                dut = _DUT16(byte_enables=byte_enables)

                def generator():
                    yield from dut.bus.write(4, 0x78563412)
                    yield from dut.bus.write(5, 0xdeadbeef)
                    self.assertEqual((yield dut.model.mem[8]),  0x3412)
                    self.assertEqual((yield dut.model.mem[9]),  0x7856)
                    self.assertEqual((yield dut.model.mem[10]), 0xbeef)
                    self.assertEqual((yield dut.model.mem[11]), 0xdead)
                    self.assertEqual((yield from dut.bus.read(4)), 0x78563412)
                    self.assertEqual((yield from dut.bus.read(5)), 0xdeadbeef)

                self.run_dut16(dut, generator)

    def test_16bit_byte_select_write_preserves_unselected_bytes(self):
        for setup_cycles, hold_cycles in [(0, 0), (1, 1)]:
            dut = _DUT16(setup_cycles=setup_cycles, hold_cycles=hold_cycles)

            def generator():
                for sel in range(16):
                    with self.subTest(setup_cycles=setup_cycles, sel=sel):
                        yield from dut.bus.write(sel, 0xaabbccdd)
                        yield from dut.bus.write(sel, 0x11223344, sel=sel)
                        expected = 0
                        for byte in range(4):
                            value     = 0x11223344 if (sel >> byte) & 1 else 0xaabbccdd
                            expected |= value & (0xff << (8*byte))
                        self.assertEqual((yield from dut.bus.read(sel)), expected)

            self.run_dut16(dut, generator)

    def test_16bit_back_to_back_accesses(self):
        # Wishbone accesses without idle cycle between them (C5G timings at 50MHz).
        dut  = _DUT16(read_cycles=1, write_cycles=1, setup_cycles=1, hold_cycles=1)
        data = [0x01020304*(n + 1) for n in range(8)]
        read = []

        def access(adr, we, dat_w=0):
            yield dut.bus.adr.eq(adr)
            yield dut.bus.dat_w.eq(dat_w)
            yield dut.bus.sel.eq(0b1111)
            yield dut.bus.we.eq(we)
            yield dut.bus.cyc.eq(1)
            yield dut.bus.stb.eq(1)
            yield
            cycles = 1
            while not (yield dut.bus.ack):
                yield
                cycles += 1
            self.assertEqual(cycles, 8)
            return (yield dut.bus.dat_r)

        def generator():
            for adr, value in enumerate(data):
                yield from access(adr, 1, value)
            for adr in range(len(data)):
                read.append((yield from access(adr, 0)))
                yield from access(adr, 1, ~data[adr] & 0xffffffff)
                read.append((yield from access(adr, 0)))
            yield dut.bus.cyc.eq(0)
            yield dut.bus.stb.eq(0)
            yield

        self.run_dut16(dut, generator)
        expected = []
        for value in data:
            expected += [value, ~value & 0xffffffff]
        self.assertEqual(read, expected)

    def test_16bit_setup_hold_cycles(self):
        # One setup, one access and one hold cycle for each 16-bit half, address stable.
        dut = _DUT16(read_cycles=1, write_cycles=1, setup_cycles=1, hold_cycles=1)
        log = []

        def generator():
            yield from dut.bus.write(3, 0xa1b2c3d4, sel=0b0111)
            yield from dut.bus.write(3, 0x00005566, sel=0b0010)
            self.assertEqual((yield from dut.bus.read(3)), 0x00b255d4)

        self.run_dut16(dut, generator, log)
        self.assertEqual(log, [
            # a, oe_n, we_n, lb_n, ub_n, dat_oe.
            # Write, sel=0b0111.
            (6, 1, 1, 0, 0, 1), (6, 1, 0, 0, 0, 1), (6, 1, 1, 0, 0, 1),
            (7, 1, 1, 0, 1, 1), (7, 1, 0, 0, 1, 1), (7, 1, 1, 0, 1, 1),
            # Write, sel=0b0010 (unselected high half skipped in one cycle, without strobe).
            (6, 1, 1, 1, 0, 1), (6, 1, 0, 1, 0, 1), (6, 1, 1, 1, 0, 1),
            (7, 1, 1, 0, 0, 0),
            # Read.
            (6, 1, 1, 0, 0, 0), (6, 0, 1, 0, 0, 0), (6, 1, 1, 0, 0, 0),
            (7, 1, 1, 0, 0, 0), (7, 0, 1, 0, 0, 0), (7, 1, 1, 0, 0, 0),
        ])

    def test_setup_hold_cycles_8bit(self):
        # Setup/hold cycles on a 8-bit SRAM: WE released between the bytes.
        dut = _DUT(read_cycles=2, write_cycles=1, setup_cycles=2, hold_cycles=1)
        memory    = {}
        write_log = []
        controls  = []

        @passive
        def monitor():
            while True:
                controls.append(((yield dut.pads.ce), (yield dut.pads.we), (yield dut.pads.adr)))
                yield

        def generator():
            yield from dut.bus.write(2, 0xa1b2c3d4)
            self.assertEqual((yield from dut.bus.read(2)), 0xa1b2c3d4)

        run_simulation(dut, [
            generator(),
            monitor(),
            _async_sram_model(self, dut, memory, write_log=write_log),
        ], special_overrides={Tristate: _IgnoreTristate})
        self.assertEqual(write_log, [(8, 0xd4), (9, 0xc3), (10, 0xb2), (11, 0xa1)])
        self.assertEqual([c for c in controls if c[0] == 0][:16], [
            (0,  1,  8), (0, 1,  8), (0, 0,  8), (0, 1,  8),
            (0,  1,  9), (0, 1,  9), (0, 0,  9), (0, 1,  9),
            (0,  1, 10), (0, 1, 10), (0, 0, 10), (0, 1, 10),
            (0,  1, 11), (0, 1, 11), (0, 0, 11), (0, 1, 11),
        ])

    def test_pads_checks(self):
        # 16-bit SRAM without byte enables.
        with self.assertRaisesRegex(ValueError, "be_n, lb_n/ub_n"):
            AsyncSRAM(pads=_AsyncSRAM16Pads(byte_enables=None))
        # Missing address pads.
        pads = _AsyncSRAMPads()
        del pads.adr
        with self.assertRaisesRegex(ValueError, "adr, a"):
            AsyncSRAM(pads=pads)
        # Negative setup/hold cycles.
        with self.assertRaisesRegex(ValueError, "setup_cycles"):
            AsyncSRAM(pads=_AsyncSRAMPads(), setup_cycles=-1)
        with self.assertRaisesRegex(ValueError, "hold_cycles"):
            AsyncSRAM(pads=_AsyncSRAMPads(), hold_cycles=-1)


if __name__ == "__main__":
    unittest.main()
