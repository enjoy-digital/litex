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
    def __init__(self, read_cycles=2, write_cycles=3):
        self.pads = _AsyncSRAMPads()
        self.bus  = wishbone.Interface(data_width=32)
        self.submodules.sram = AsyncSRAM(
            pads         = self.pads,
            bus          = self.bus,
            read_cycles  = read_cycles,
            write_cycles = write_cycles)


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


if __name__ == "__main__":
    unittest.main()
