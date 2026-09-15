#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import random
import unittest
from collections import deque

from migen import *
from migen.sim import passive

from litex.gen import *
from litex.soc.interconnect import ahb, wishbone
from litex.soc.cores.cpu.gowin_ae350.core import AE350RAMBridge
from litedram.common import LiteDRAMNativePort

from test.interconnect.test_ahb_burst import burst, transfer
from test.soc import test_cpu_gowin_ae350 as cpu_tests


class DUT(LiteXModule):
    def __init__(self):
        self.ahb = ahb.AHBInterface(data_width=64)
        self.wb = wishbone.Interface(data_width=64, address_width=32)
        self.port = LiteDRAMNativePort(mode="both", data_width=256, address_width=27)
        self.bridge = AE350RAMBridge(self.ahb, self.wb, self.port, 0x4000_0000, 0x2000_0000)
        self.sram = wishbone.SRAM(4096, bus=self.wb)
        self.memory = {}
        self.commands = []
        self.cycles = 0

    @passive
    def memory_model(self):
        rng = random.Random(7)
        writes = deque()
        reads = deque()
        response = None
        while True:
            port = self.port
            if (yield port.cmd.valid) and (yield port.cmd.ready):
                address = (yield port.cmd.addr)
                write = (yield port.cmd.we)
                self.commands.append((write, address))
                if write:
                    writes.append(address)
                else:
                    reads.append((self.cycles + 7, address))
            if (yield port.wdata.valid) and (yield port.wdata.ready):
                assert writes, "Native write data without a command"
                address = writes.popleft()
                mask = (yield port.wdata.we)
                data = (yield port.wdata.data)
                old = self.memory.get(address, 0)
                for byte in range(32):
                    if mask & (1 << byte):
                        old = (old & ~(255 << (8*byte))) | (data & (255 << (8*byte)))
                self.memory[address] = old
            if response is not None and (yield port.rdata.ready):
                response = None
            if response is None and reads and reads[0][0] <= self.cycles:
                _, address = reads.popleft()
                response = self.memory.get(address, 0)
            yield port.rdata.valid.eq(response is not None)
            yield port.rdata.data.eq(response or 0)
            yield port.cmd.ready.eq(rng.randrange(4) != 0)
            yield port.wdata.ready.eq(bool(writes) and rng.randrange(4) != 0)
            self.cycles += 1
            yield


class TestGowinAE350Native(unittest.TestCase):
    def test_cache_line_write_does_not_read_allocate(self):
        dut = DUT()
        values = [0x1111222233334444 + i for i in range(4)]
        def gen():
            yield from transfer(dut, burst(0x4000_0010, values, 3, 2))
            for _ in range(40):
                yield
            self.assertEqual(dut.commands, [(1, 0)])
            result = yield from transfer(dut, burst(0x4000_0010, [None]*4, 3, 2))
            self.assertEqual(result, [(v, 0) for v in values])
            self.assertEqual(dut.commands, [(1, 0), (0, 0)])
        run_simulation(dut, [gen(), dut.memory_model()])

    def test_partial_writes_and_sram_routing(self):
        dut = DUT()
        def gen():
            phases = [
                (0x4000_0004, 0xdeadbeef << 32, 2, 0, 2),
                (0x0000_0100, 0x12345678,       2, 0, 2),
                (0x4000_0002, 0xabcd << 16,     1, 0, 2),
                (0x0000_0100, None,            2, 0, 2),
                (0x4000_0000, None,            3, 0, 2),
            ]
            result = yield from transfer(dut, phases)
            self.assertTrue(all(resp == 0 for _, resp in result))
            self.assertEqual(result[-2][0] & 0xffffffff, 0x12345678)
            self.assertEqual(result[-1][0], 0xdeadbeefabcd0000)
            # An address above the actual DDR region must still take the fabric path.
            result = yield from transfer(dut, [(0x6000_0100, None, 3, 0, 2)])
            self.assertEqual(result[0][0], 0x12345678)
        run_simulation(dut, [gen(), dut.memory_model()])

    def test_completed_burst_does_not_cache_another_masters_data(self):
        dut = DUT()
        def gen():
            yield from transfer(dut, burst(0x4000_0000, [None]*4, 3, 2))
            dut.memory[0] = 0x12345678
            result = yield from transfer(dut, burst(0x4000_0000, [None]*4, 3, 2))
            self.assertEqual(result[0][0], 0x12345678)
        run_simulation(dut, [gen(), dut.memory_model()])

    def test_rejects_noncoherent_fabric_l2(self):
        soc = cpu_tests.TestGowinAE350().make_soc()
        soc.cpu.native_memory = True
        from litex.soc.integration.soc import SoCRegion
        soc.bus.add_region("main_ram", SoCRegion(origin=0x4000_0000, size=0x2000_0000))
        soc.cpu.add_memory_buses(address_width=32, data_width=256)
        soc.add_config("L2_SIZE", 8192)
        with self.assertRaisesRegex(ValueError, "use --l2-size=0"):
            soc.cpu.do_finalize()
