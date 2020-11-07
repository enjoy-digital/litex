#
# This file is part of LiteX.
#
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *

from litex.soc.interconnect.axi import *
from litex.soc.interconnect import wishbone, csr_bus

# Helpers ------------------------------------------------------------------------------------------

def _int_or_call(int_or_func):
    if callable(int_or_func):
        return int_or_func()
    return int_or_func

@passive
def timeout_generator(ticks):
    import os
    for i in range(ticks):
        if os.environ.get("TIMEOUT_DEBUG", "") == "1":
            print("tick {}".format(i))
        yield
    raise TimeoutError("Timeout after %d ticks" % ticks)

class AXILiteChecker:
    def __init__(self, ready_latency=0, response_latency=0, rdata_generator=None):
        self.ready_latency = ready_latency
        self.response_latency = response_latency
        self.rdata_generator = rdata_generator or (lambda adr: 0xbaadc0de)
        self.writes = []  # (addr, data, strb)
        self.reads = []  # (addr, data)

    def delay(self, latency):
        for _ in range(_int_or_call(latency)):
            yield

    def handle_write(self, axi_lite):
        # aw
        while not (yield axi_lite.aw.valid):
            yield
        yield from self.delay(self.ready_latency)
        addr = (yield axi_lite.aw.addr)
        yield axi_lite.aw.ready.eq(1)
        yield
        yield axi_lite.aw.ready.eq(0)
        while not (yield axi_lite.w.valid):
            yield
        yield from self.delay(self.ready_latency)
        # w
        data = (yield axi_lite.w.data)
        strb = (yield axi_lite.w.strb)
        yield axi_lite.w.ready.eq(1)
        yield
        yield axi_lite.w.ready.eq(0)
        yield from self.delay(self.response_latency)
        # b
        yield axi_lite.b.valid.eq(1)
        yield axi_lite.b.resp.eq(RESP_OKAY)
        yield
        while not (yield axi_lite.b.ready):
            yield
        yield axi_lite.b.valid.eq(0)
        self.writes.append((addr, data, strb))

    def handle_read(self, axi_lite):
        # ar
        while not (yield axi_lite.ar.valid):
            yield
        yield from self.delay(self.ready_latency)
        addr = (yield axi_lite.ar.addr)
        yield axi_lite.ar.ready.eq(1)
        yield
        yield axi_lite.ar.ready.eq(0)
        yield from self.delay(self.response_latency)
        # r
        data = self.rdata_generator(addr)
        yield axi_lite.r.valid.eq(1)
        yield axi_lite.r.resp.eq(RESP_OKAY)
        yield axi_lite.r.data.eq(data)
        yield
        while not (yield axi_lite.r.ready):
            yield
        yield axi_lite.r.valid.eq(0)
        yield axi_lite.r.data.eq(0)
        self.reads.append((addr, data))

    @passive
    def handler(self, axi_lite):
        while True:
            if (yield axi_lite.aw.valid):
                yield from self.handle_write(axi_lite)
            if (yield axi_lite.ar.valid):
                yield from self.handle_read(axi_lite)
            yield

    @passive
    def _write_handler(self, axi_lite):
        while True:
            yield from self.handle_write(axi_lite)
            yield

    @passive
    def _read_handler(self, axi_lite):
        while True:
            yield from self.handle_read(axi_lite)
            yield

    def parallel_handlers(self, axi_lite):
        return self._write_handler(axi_lite), self._read_handler(axi_lite)

class AXILitePatternGenerator:
    def __init__(self, axi_lite, pattern, delay=0):
        # patter: (rw, addr, data)
        self.axi_lite = axi_lite
        self.pattern = pattern
        self.delay = delay
        self.errors = 0
        self.read_errors = []
        self.resp_errors = {"w": 0, "r": 0}

    def handler(self):
        for rw, addr, data in self.pattern:
            assert rw in ["w", "r"]
            if rw == "w":
                strb = 2**len(self.axi_lite.w.strb) - 1
                resp = (yield from self.axi_lite.write(addr, data, strb))
            else:
                rdata, resp = (yield from self.axi_lite.read(addr))
                if rdata != data:
                    self.read_errors.append((rdata, data))
                    self.errors += 1
            if resp != RESP_OKAY:
                self.resp_errors[rw] += 1
                self.errors += 1
            for _ in range(_int_or_call(self.delay)):
                yield
        for _ in range(16):
            yield

# TestAXILite --------------------------------------------------------------------------------------

class TestAXILite(unittest.TestCase):
    def test_wishbone2axi2wishbone(self):
        class DUT(Module):
            def __init__(self):
                self.wishbone = wishbone.Interface(data_width=32, adr_width=30)

                # # #

                axi = AXILiteInterface(data_width=32, address_width=32)
                wb  = wishbone.Interface(data_width=32, adr_width=30)

                wishbone2axi = Wishbone2AXILite(self.wishbone, axi)
                axi2wishbone = AXILite2Wishbone(axi, wb)
                self.submodules += wishbone2axi, axi2wishbone

                sram = wishbone.SRAM(1024, init=[0x12345678, 0xa55aa55a])
                self.submodules += sram
                self.comb += wb.connect(sram.bus)

        def generator(dut):
            dut.errors = 0
            if (yield from dut.wishbone.read(0)) != 0x12345678:
                dut.errors += 1
            if (yield from dut.wishbone.read(1)) != 0xa55aa55a:
                dut.errors += 1
            for i in range(32):
                yield from dut.wishbone.write(i, i)
            for i in range(32):
                if (yield from dut.wishbone.read(i)) != i:
                    dut.errors += 1

        dut = DUT()
        run_simulation(dut, [generator(dut)])
        self.assertEqual(dut.errors, 0)

    def test_axilite2axi2mem(self):
        class DUT(Module):
            def __init__(self, mem_bus="wishbone"):
                self.axi_lite = AXILiteInterface()

                axi = AXIInterface()
                self.submodules.axil2axi = AXILite2AXI(self.axi_lite, axi)

                interface_cls, converter_cls, sram_cls = {
                    "wishbone": (wishbone.Interface, AXI2Wishbone, wishbone.SRAM),
                    "axi_lite": (AXILiteInterface,   AXI2AXILite,  AXILiteSRAM),
                }[mem_bus]

                bus_kwargs = {"adr_width" : 30} if mem_bus == "wishbone" else {}
                bus = interface_cls(**bus_kwargs)
                self.submodules += converter_cls(axi, bus)
                sram = sram_cls(1024, init=[0x12345678, 0xa55aa55a])
                self.submodules += sram
                self.comb += bus.connect(sram.bus)

        def generator(axi_lite, datas, resps):
            data, resp = (yield from axi_lite.read(0x00))
            resps.append((resp, RESP_OKAY))
            datas.append((data, 0x12345678))
            data, resp = (yield from axi_lite.read(0x04))
            resps.append((resp, RESP_OKAY))
            datas.append((data, 0xa55aa55a))
            for i in range(32):
                resp = (yield from axi_lite.write(4*i, i))
                resps.append((resp, RESP_OKAY))
            for i in range(32):
                data, resp = (yield from axi_lite.read(4*i))
                resps.append((resp, RESP_OKAY))
                datas.append((data, i))

        for mem_bus in ["wishbone", "axi_lite"]:
            with self.subTest(mem_bus=mem_bus):
                # to have more verbose error messages store errors in list((actual, expected))
                datas = []
                resps = []

                def actual_expected(results):  # split into (list(actual), list(expected))
                    return list(zip(*results))

                dut = DUT(mem_bus)
                run_simulation(dut, [generator(dut.axi_lite, datas, resps)])
                self.assertEqual(*actual_expected(resps))
                msg = "\n".join("0x{:08x} vs 0x{:08x}".format(actual, expected) for actual, expected in datas)
                self.assertEqual(*actual_expected(datas), msg="actual vs expected:\n" + msg)

    def test_axilite2csr(self):
        @passive
        def csr_mem_handler(csr, mem):
            while True:
                adr = (yield csr.adr)
                yield csr.dat_r.eq(mem[adr])
                if (yield csr.we):
                    mem[adr] = (yield csr.dat_w)
                yield

        class DUT(Module):
            def __init__(self):
                self.axi_lite = AXILiteInterface()
                self.csr = csr_bus.Interface()
                self.submodules.axilite2csr = AXILite2CSR(self.axi_lite, self.csr)
                self.errors = 0

        prng = random.Random(42)
        mem_ref = [prng.randrange(255) for i in range(100)]

        def generator(dut):
            dut.errors = 0

            for adr, ref in enumerate(mem_ref):
                adr = adr << 2
                data, resp = (yield from dut.axi_lite.read(adr))
                self.assertEqual(resp, 0b00)
                if data != ref:
                    dut.errors += 1

            write_data = [prng.randrange(255) for _ in mem_ref]

            for adr, wdata in enumerate(write_data):
                adr = adr << 2
                resp = (yield from dut.axi_lite.write(adr, wdata))
                self.assertEqual(resp, 0b00)
                rdata, resp = (yield from dut.axi_lite.read(adr))
                self.assertEqual(resp, 0b00)
                if rdata != wdata:
                    dut.errors += 1

        dut = DUT()
        mem = [v for v in mem_ref]
        run_simulation(dut, [generator(dut), csr_mem_handler(dut.csr, mem)])
        self.assertEqual(dut.errors, 0)

    def test_axilite_sram(self):
        class DUT(Module):
            def __init__(self, size, init):
                self.axi_lite = AXILiteInterface()
                self.submodules.sram = AXILiteSRAM(size, init=init, bus=self.axi_lite)
                self.errors = 0

        def generator(dut, ref_init):
            for adr, ref in enumerate(ref_init):
                adr = adr << 2
                data, resp = (yield from dut.axi_lite.read(adr))
                self.assertEqual(resp, 0b00)
                if data != ref:
                    dut.errors += 1

            write_data = [prng.randrange(255) for _ in ref_init]

            for adr, wdata in enumerate(write_data):
                adr = adr << 2
                resp = (yield from dut.axi_lite.write(adr, wdata))
                self.assertEqual(resp, 0b00)
                rdata, resp = (yield from dut.axi_lite.read(adr))
                self.assertEqual(resp, 0b00)
                if rdata != wdata:
                    dut.errors += 1

        prng = random.Random(42)
        init = [prng.randrange(2**32) for i in range(100)]

        dut = DUT(size=len(init)*4, init=[v for v in init])
        run_simulation(dut, [generator(dut, init)])
        self.assertEqual(dut.errors, 0)

    def converter_test(self, width_from, width_to, parallel_rw=False,
                       write_pattern=None, write_expected=None,
                       read_pattern=None, read_expected=None):
        assert not (write_pattern is None and read_pattern is None)

        if write_pattern is None:
            write_pattern = []
            write_expected = []
        elif len(write_pattern[0]) == 2:
            # add w.strb
            write_pattern = [(adr, data, 2**(width_from//8)-1) for adr, data in write_pattern]

        if read_pattern is None:
            read_pattern = []
            read_expected = []

        class DUT(Module):
            def __init__(self, width_from, width_to):
                self.master = AXILiteInterface(data_width=width_from)
                self.slave = AXILiteInterface(data_width=width_to)
                self.submodules.converter = AXILiteConverter(self.master, self.slave)

        prng = random.Random(42)

        def write_generator(axi_lite):
            for addr, data, strb in write_pattern or []:
                resp = (yield from axi_lite.write(addr, data, strb))
                self.assertEqual(resp, RESP_OKAY)
                for _ in range(prng.randrange(3)):
                    yield
            for _ in range(16):
                yield

        def read_generator(axi_lite):
            for addr, refdata in read_pattern or []:
                data, resp = (yield from axi_lite.read(addr))
                self.assertEqual(resp, RESP_OKAY)
                self.assertEqual(data, refdata)
                for _ in range(prng.randrange(3)):
                    yield
            for _ in range(4):
                yield

        def sequential_generator(axi_lite):
            yield from write_generator(axi_lite)
            yield from read_generator(axi_lite)

        def rdata_generator(adr):
            for a, v in read_expected:
                if a == adr:
                    return v
            return 0xbaadc0de

        _latency = 0
        def latency():
            nonlocal _latency
            _latency = (_latency + 1) % 3
            return _latency

        dut = DUT(width_from=width_from, width_to=width_to)
        checker = AXILiteChecker(ready_latency=latency, rdata_generator=rdata_generator)
        if parallel_rw:
            generators = [write_generator(dut.master), read_generator(dut.master)]
        else:
            generators = [sequential_generator(dut.master)]
        generators += checker.parallel_handlers(dut.slave)
        run_simulation(dut, generators)
        self.assertEqual(checker.writes, write_expected)
        self.assertEqual(checker.reads, read_expected)

    def test_axilite_down_converter_32to16(self):
        write_pattern = [
            (0x00000000, 0x22221111),
            (0x00000004, 0x44443333),
            (0x00000008, 0x66665555),
            (0x00000100, 0x88887777),
        ]
        write_expected = [
            (0x00000000, 0x1111, 0b11),
            (0x00000002, 0x2222, 0b11),
            (0x00000004, 0x3333, 0b11),
            (0x00000006, 0x4444, 0b11),
            (0x00000008, 0x5555, 0b11),
            (0x0000000a, 0x6666, 0b11),
            (0x00000100, 0x7777, 0b11),
            (0x00000102, 0x8888, 0b11),
        ]
        read_pattern = write_pattern
        read_expected = [(adr, data) for (adr, data, _) in write_expected]
        for parallel in [False, True]:
            with self.subTest(parallel=parallel):
                self.converter_test(width_from=32, width_to=16, parallel_rw=parallel,
                                    write_pattern=write_pattern, write_expected=write_expected,
                                    read_pattern=read_pattern, read_expected=read_expected)

    def test_axilite_down_converter_32to8(self):
        write_pattern = [
            (0x00000000, 0x44332211),
            (0x00000004, 0x88776655),
        ]
        write_expected = [
            (0x00000000, 0x11, 0b1),
            (0x00000001, 0x22, 0b1),
            (0x00000002, 0x33, 0b1),
            (0x00000003, 0x44, 0b1),
            (0x00000004, 0x55, 0b1),
            (0x00000005, 0x66, 0b1),
            (0x00000006, 0x77, 0b1),
            (0x00000007, 0x88, 0b1),
        ]
        read_pattern = write_pattern
        read_expected = [(adr, data) for (adr, data, _) in write_expected]
        for parallel in [False, True]:
            with self.subTest(parallel=parallel):
                self.converter_test(width_from=32, width_to=8, parallel_rw=parallel,
                                    write_pattern=write_pattern, write_expected=write_expected,
                                    read_pattern=read_pattern, read_expected=read_expected)

    def test_axilite_down_converter_64to32(self):
        write_pattern = [
            (0x00000000, 0x2222222211111111),
            (0x00000008, 0x4444444433333333),
        ]
        write_expected = [
            (0x00000000, 0x11111111, 0b1111),
            (0x00000004, 0x22222222, 0b1111),
            (0x00000008, 0x33333333, 0b1111),
            (0x0000000c, 0x44444444, 0b1111),
        ]
        read_pattern = write_pattern
        read_expected = [(adr, data) for (adr, data, _) in write_expected]
        for parallel in [False, True]:
            with self.subTest(parallel=parallel):
                self.converter_test(width_from=64, width_to=32, parallel_rw=parallel,
                                    write_pattern=write_pattern, write_expected=write_expected,
                                    read_pattern=read_pattern, read_expected=read_expected)

    def test_axilite_down_converter_strb(self):
        write_pattern = [
            (0x00000000, 0x22221111, 0b1100),
            (0x00000004, 0x44443333, 0b1111),
            (0x00000008, 0x66665555, 0b1011),
            (0x00000100, 0x88887777, 0b0011),
        ]
        write_expected = [
            (0x00000002, 0x2222, 0b11),
            (0x00000004, 0x3333, 0b11),
            (0x00000006, 0x4444, 0b11),
            (0x00000008, 0x5555, 0b11),
            (0x0000000a, 0x6666, 0b10),
            (0x00000100, 0x7777, 0b11),
        ]
        self.converter_test(width_from=32, width_to=16,
                            write_pattern=write_pattern, write_expected=write_expected)

    def test_axilite_up_converter_16to32(self):
        write_pattern = [
            (0x00000000, 0x1111),
            (0x00000002, 0x2222),
            (0x00000006, 0x3333),
            (0x00000004, 0x4444),
            (0x00000102, 0x5555),
        ]
        write_expected = [
            (0x00000000, 0x00001111, 0b0011),
            (0x00000000, 0x22220000, 0b1100),
            (0x00000004, 0x33330000, 0b1100),
            (0x00000004, 0x00004444, 0b0011),
            (0x00000100, 0x55550000, 0b1100),
        ]
        read_pattern = write_pattern
        read_expected = [
            (0x00000000, 0x22221111),
            (0x00000000, 0x22221111),
            (0x00000004, 0x33334444),
            (0x00000004, 0x33334444),
            (0x00000100, 0x55550000),
        ]
        for parallel in [False, True]:
            with self.subTest(parallel=parallel):
                self.converter_test(width_from=16, width_to=32, parallel_rw=parallel,
                                    write_pattern=write_pattern, write_expected=write_expected,
                                    read_pattern=read_pattern, read_expected=read_expected)

    def test_axilite_up_converter_8to32(self):
        write_pattern = [
            (0x00000000, 0x11),
            (0x00000001, 0x22),
            (0x00000003, 0x33),
            (0x00000002, 0x44),
            (0x00000101, 0x55),
        ]
        write_expected = [
            (0x00000000, 0x00000011, 0b0001),
            (0x00000000, 0x00002200, 0b0010),
            (0x00000000, 0x33000000, 0b1000),
            (0x00000000, 0x00440000, 0b0100),
            (0x00000100, 0x00005500, 0b0010),
        ]
        read_pattern = write_pattern
        read_expected = [
            (0x00000000, 0x33442211),
            (0x00000000, 0x33442211),
            (0x00000000, 0x33442211),
            (0x00000000, 0x33442211),
            (0x00000100, 0x00005500),
        ]
        for parallel in [False, True]:
            with self.subTest(parallel=parallel):
                self.converter_test(width_from=8, width_to=32, parallel_rw=parallel,
                                    write_pattern=write_pattern, write_expected=write_expected,
                                    read_pattern=read_pattern, read_expected=read_expected)

    def test_axilite_up_converter_strb(self):
        write_pattern = [
            (0x00000000, 0x1111, 0b10),
            (0x00000002, 0x2222, 0b11),
            (0x00000006, 0x3333, 0b11),
            (0x00000004, 0x4444, 0b01),
            (0x00000102, 0x5555, 0b01),
        ]
        write_expected = [
            (0x00000000, 0x00001111, 0b0010),
            (0x00000000, 0x22220000, 0b1100),
            (0x00000004, 0x33330000, 0b1100),
            (0x00000004, 0x00004444, 0b0001),
            (0x00000100, 0x55550000, 0b0100),
        ]
        self.converter_test(width_from=16, width_to=32,
                            write_pattern=write_pattern, write_expected=write_expected)

# TestAXILiteInterconnet ---------------------------------------------------------------------------

class TestAXILiteInterconnect(unittest.TestCase):
    def test_interconnect_p2p(self):
        class DUT(Module):
            def __init__(self):
                self.master = master = AXILiteInterface()
                self.slave  = slave  = AXILiteInterface()
                self.submodules.interconnect = AXILiteInterconnectPointToPoint(master, slave)

        pattern = [
            ("w", 0x00000004, 0x11111111),
            ("w", 0x0000000c, 0x22222222),
            ("r", 0x00000010, 0x33333333),
            ("r", 0x00000018, 0x44444444),
        ]

        def rdata_generator(adr):
            for rw, a, v in pattern:
                if rw == "r" and a == adr:
                    return v
            return 0xbaadc0de

        dut = DUT()
        checker = AXILiteChecker(rdata_generator=rdata_generator)
        generators = [
            AXILitePatternGenerator(dut.master, pattern).handler(),
            checker.handler(dut.slave),
        ]
        run_simulation(dut, generators)
        self.assertEqual(checker.writes, [(addr, data, 0b1111) for rw, addr, data in pattern if rw == "w"])
        self.assertEqual(checker.reads, [(addr, data) for rw, addr, data in pattern if rw == "r"])

    def test_timeout(self):
        class DUT(Module):
            def __init__(self):
                self.master = master = AXILiteInterface()
                self.slave  = slave  = AXILiteInterface()
                self.submodules.interconnect = AXILiteInterconnectPointToPoint(master, slave)
                self.submodules.timeout = AXILiteTimeout(master, 16)

        def generator(axi_lite):
            resp = (yield from axi_lite.write(0x00001000, 0x11111111))
            self.assertEqual(resp, RESP_OKAY)
            resp = (yield from axi_lite.write(0x00002000, 0x22222222))
            self.assertEqual(resp, RESP_SLVERR)
            data, resp = (yield from axi_lite.read(0x00003000))
            self.assertEqual(resp, RESP_SLVERR)
            self.assertEqual(data, 0xffffffff)
            yield

        def checker(axi_lite):
            for _ in range(16):
                yield
            yield axi_lite.aw.ready.eq(1)
            yield axi_lite.w.ready.eq(1)
            yield
            yield axi_lite.aw.ready.eq(0)
            yield axi_lite.w.ready.eq(0)
            yield axi_lite.b.valid.eq(1)
            yield
            while not (yield axi_lite.b.ready):
                yield
            yield axi_lite.b.valid.eq(0)

        dut = DUT()
        generators = [
            generator(dut.master),
            checker(dut.slave),
            timeout_generator(300),
        ]
        run_simulation(dut, generators)

    def test_arbiter_order(self):
        class DUT(Module):
            def __init__(self, n_masters):
                self.masters = [AXILiteInterface() for _ in range(n_masters)]
                self.slave   = AXILiteInterface()
                self.submodules.arbiter = AXILiteArbiter(self.masters, self.slave)

        def generator(n, axi_lite, delay=0):
            def gen(i):
                return 100*n + i

            for i in range(4):
                resp = (yield from axi_lite.write(gen(i), gen(i)))
                self.assertEqual(resp, RESP_OKAY)
                for _ in range(delay):
                    yield
            for i in range(4):
                data, resp = (yield from axi_lite.read(gen(i)))
                self.assertEqual(resp, RESP_OKAY)
                for _ in range(delay):
                    yield
            for _ in range(8):
                yield

        n_masters = 3

        # with no delay each master will do all transfers at once
        with self.subTest(delay=0):
            dut = DUT(n_masters)
            checker = AXILiteChecker()
            generators = [generator(i, master, delay=0) for i, master in enumerate(dut.masters)]
            generators += [timeout_generator(300), checker.handler(dut.slave)]
            run_simulation(dut, generators)
            order = [0, 1, 2, 3, 100, 101, 102, 103, 200, 201, 202, 203]
            self.assertEqual([addr for addr, data, strb in checker.writes], order)
            self.assertEqual([addr for addr, data in checker.reads], order)

        # with some delay, the round-robin arbiter will iterate over masters
        with self.subTest(delay=1):
            dut = DUT(n_masters)
            checker = AXILiteChecker()
            generators = [generator(i, master, delay=1) for i, master in enumerate(dut.masters)]
            generators += [timeout_generator(300), checker.handler(dut.slave)]
            run_simulation(dut, generators)
            order = [0, 100, 200, 1, 101, 201, 2, 102, 202, 3, 103, 203]
            self.assertEqual([addr for addr, data, strb in checker.writes], order)
            self.assertEqual([addr for addr, data in checker.reads], order)

    def test_arbiter_holds_grant_until_response(self):
        class DUT(Module):
            def __init__(self, n_masters):
                self.masters = [AXILiteInterface() for _ in range(n_masters)]
                self.slave   = AXILiteInterface()
                self.submodules.arbiter = AXILiteArbiter(self.masters, self.slave)

        def generator(n, axi_lite, delay=0):
            def gen(i):
                return 100*n + i

            for i in range(4):
                resp = (yield from axi_lite.write(gen(i), gen(i)))
                self.assertEqual(resp, RESP_OKAY)
                for _ in range(delay):
                    yield
            for i in range(4):
                data, resp = (yield from axi_lite.read(gen(i)))
                self.assertEqual(resp, RESP_OKAY)
                for _ in range(delay):
                    yield
            for _ in range(8):
                yield

        n_masters = 3

        # with no delay each master will do all transfers at once
        with self.subTest(delay=0):
            dut = DUT(n_masters)
            checker = AXILiteChecker(response_latency=lambda: 3)
            generators = [generator(i, master, delay=0) for i, master in enumerate(dut.masters)]
            generators += [timeout_generator(300), checker.handler(dut.slave)]
            run_simulation(dut, generators)
            order = [0, 1, 2, 3, 100, 101, 102, 103, 200, 201, 202, 203]
            self.assertEqual([addr for addr, data, strb in checker.writes], order)
            self.assertEqual([addr for addr, data in checker.reads], order)

        # with some delay, the round-robin arbiter will iterate over masters
        with self.subTest(delay=1):
            dut = DUT(n_masters)
            checker = AXILiteChecker(response_latency=lambda: 3)
            generators = [generator(i, master, delay=1) for i, master in enumerate(dut.masters)]
            generators += [timeout_generator(300), checker.handler(dut.slave)]
            run_simulation(dut, generators)
            order = [0, 100, 200, 1, 101, 201, 2, 102, 202, 3, 103, 203]
            self.assertEqual([addr for addr, data, strb in checker.writes], order)
            self.assertEqual([addr for addr, data in checker.reads], order)

    def address_decoder(self, i, size=0x100, python=False):
        # bytes to 32-bit words aligned
        _size   = (size) >> 2
        _origin = (size * i) >> 2
        if python:  # for python integers
            shift = log2_int(_size)
            return lambda a: ((a >> shift) == (_origin >> shift))
        # for migen signals
        return lambda a: (a[log2_int(_size):] == (_origin >> log2_int(_size)))

    def decoder_test(self, n_slaves, pattern, generator_delay=0):
        class DUT(Module):
            def __init__(self, decoders):
                self.master = AXILiteInterface()
                self.slaves = [AXILiteInterface() for _ in range(len(decoders))]
                slaves = list(zip(decoders, self.slaves))
                self.submodules.decoder = AXILiteDecoder(self.master, slaves)

        def rdata_generator(adr):
            for rw, a, v in pattern:
                if rw == "r" and a == adr:
                    return v
            return 0xbaadc0de

        dut = DUT([self.address_decoder(i) for i in range(n_slaves)])
        checkers = [AXILiteChecker(rdata_generator=rdata_generator) for _ in dut.slaves]

        generators = [AXILitePatternGenerator(dut.master, pattern, delay=generator_delay).handler()]
        generators += [checker.handler(slave) for (slave, checker) in zip(dut.slaves, checkers)]
        generators += [timeout_generator(300)]
        run_simulation(dut, generators)

        return checkers

    def test_decoder_write(self):
        for delay in [0, 1, 0]:
            with self.subTest(delay=delay):
                slaves = self.decoder_test(n_slaves=3, pattern=[
                    ("w", 0x010, 1),
                    ("w", 0x110, 2),
                    ("w", 0x210, 3),
                    ("w", 0x011, 1),
                    ("w", 0x012, 1),
                    ("w", 0x111, 2),
                    ("w", 0x112, 2),
                    ("w", 0x211, 3),
                    ("w", 0x212, 3),
                ], generator_delay=delay)

                def addr(checker_list):
                    return [entry[0] for entry in checker_list]

                self.assertEqual(addr(slaves[0].writes), [0x010, 0x011, 0x012])
                self.assertEqual(addr(slaves[1].writes), [0x110, 0x111, 0x112])
                self.assertEqual(addr(slaves[2].writes), [0x210, 0x211, 0x212])
                for slave in slaves:
                    self.assertEqual(slave.reads, [])

    def test_decoder_read(self):
        for delay in [0, 1]:
            with self.subTest(delay=delay):
                slaves = self.decoder_test(n_slaves=3, pattern=[
                    ("r", 0x010, 1),
                    ("r", 0x110, 2),
                    ("r", 0x210, 3),
                    ("r", 0x011, 1),
                    ("r", 0x012, 1),
                    ("r", 0x111, 2),
                    ("r", 0x112, 2),
                    ("r", 0x211, 3),
                    ("r", 0x212, 3),
                ], generator_delay=delay)

                def addr(checker_list):
                    return [entry[0] for entry in checker_list]

                self.assertEqual(addr(slaves[0].reads), [0x010, 0x011, 0x012])
                self.assertEqual(addr(slaves[1].reads), [0x110, 0x111, 0x112])
                self.assertEqual(addr(slaves[2].reads), [0x210, 0x211, 0x212])
                for slave in slaves:
                    self.assertEqual(slave.writes, [])

    def test_decoder_read_write(self):
        for delay in [0, 1]:
            with self.subTest(delay=delay):
                slaves = self.decoder_test(n_slaves=3, pattern=[
                    ("w", 0x010, 1),
                    ("w", 0x110, 2),
                    ("r", 0x111, 2),
                    ("r", 0x011, 1),
                    ("r", 0x211, 3),
                    ("w", 0x210, 3),
                ], generator_delay=delay)

                def addr(checker_list):
                    return [entry[0] for entry in checker_list]

                self.assertEqual(addr(slaves[0].writes), [0x010])
                self.assertEqual(addr(slaves[0].reads),  [0x011])
                self.assertEqual(addr(slaves[1].writes), [0x110])
                self.assertEqual(addr(slaves[1].reads),  [0x111])
                self.assertEqual(addr(slaves[2].writes), [0x210])
                self.assertEqual(addr(slaves[2].reads),  [0x211])

    def test_decoder_stall(self):
        with self.assertRaises(TimeoutError):
            self.decoder_test(n_slaves=3, pattern=[
                ("w", 0x300, 1),
            ])
        with self.assertRaises(TimeoutError):
            self.decoder_test(n_slaves=3, pattern=[
                ("r", 0x300, 1),
            ])

    def interconnect_test(self, master_patterns, slave_decoders,
                                 master_delay=0, slave_ready_latency=0, slave_response_latency=0,
                                 disconnected_slaves=None, timeout=300, interconnect=AXILiteInterconnectShared,
                                 **kwargs):
        # number of masters/slaves is defined by the number of patterns/decoders
        # master_patterns: list of patterns per master, pattern = list(tuple(rw, addr, data))
        # slave_decoders: list of address decoders per slave
        # delay/latency: control the speed of masters/slaves
        # disconnected_slaves: list of slave numbers that shouldn't respond to any transactions
        class DUT(Module):
            def __init__(self, n_masters, decoders, **kwargs):
                self.masters = [AXILiteInterface(name="master") for _ in range(n_masters)]
                self.slaves  = [AXILiteInterface(name="slave") for _ in range(len(decoders))]
                slaves = list(zip(decoders, self.slaves))
                self.submodules.interconnect = interconnect(self.masters, slaves, **kwargs)

        class ReadDataGenerator:
            # Generates data based on decoded addresses and data defined in master_patterns
            def __init__(self, patterns):
                self.mem = {}
                for pattern in patterns:
                    for rw, addr, val in pattern:
                        if rw == "r":
                            assert addr not in self.mem
                            self.mem[addr] = val

            def getter(self, n):
                # on miss will give default data depending on slave n
                return lambda addr: self.mem.get(addr, 0xbaad0000 + n)

        def new_checker(rdata_generator):
            return AXILiteChecker(ready_latency=slave_ready_latency,
                                  response_latency=slave_response_latency,
                                  rdata_generator=rdata_generator)

        # perpare test
        dut = DUT(len(master_patterns), slave_decoders, **kwargs)
        rdata_generator = ReadDataGenerator(master_patterns)
        checkers = [new_checker(rdata_generator.getter(i)) for i, _ in enumerate(master_patterns)]
        pattern_generators = [AXILitePatternGenerator(dut.masters[i], pattern, delay=master_delay)
                              for i, pattern in enumerate(master_patterns)]

        # run simulator
        generators = [gen.handler() for gen in pattern_generators]
        generators += [checker.handler(slave)
                       for i, (slave, checker) in enumerate(zip(dut.slaves, checkers))
                       if i not in (disconnected_slaves or [])]
        generators += [timeout_generator(timeout)]
        run_simulation(dut, generators)

        return pattern_generators, checkers

    def test_interconnect_shared_basic(self):
        master_patterns = [
            [("w", 0x000, 0), ("w", 0x101, 0), ("w", 0x202, 0)],
            [("w", 0x010, 0), ("w", 0x111, 0), ("w", 0x112, 0)],
            [("w", 0x220, 0), ("w", 0x221, 0), ("w", 0x222, 0)],
        ]
        slave_decoders = [self.address_decoder(i) for i in range(3)]

        generators, checkers = self.interconnect_test(master_patterns, slave_decoders,
                                                      master_delay=1)

        for gen in generators:
            self.assertEqual(gen.errors, 0)

        def addr(checker_list):
            return [entry[0] for entry in checker_list]

        self.assertEqual(addr(checkers[0].writes), [0x000, 0x010])
        self.assertEqual(addr(checkers[1].writes), [0x101, 0x111, 0x112])
        self.assertEqual(addr(checkers[2].writes), [0x220, 0x221, 0x202, 0x222])
        self.assertEqual(addr(checkers[0].reads), [])
        self.assertEqual(addr(checkers[1].reads), [])
        self.assertEqual(addr(checkers[2].reads), [])

    def interconnect_stress_test(self, timeout=1000, **kwargs):
        prng = random.Random(42)

        n_masters = 3
        n_slaves = 3
        pattern_length = 64
        slave_region_size = 0x10000000
        # for testing purpose each master will access only its own region of a slave
        master_region_size = 0x1000
        assert n_masters*master_region_size < slave_region_size

        def gen_pattern(n, length):
            assert length < master_region_size
            for i_access in range(length):
                rw = "w" if prng.randint(0, 1) == 0 else "r"
                i_slave = prng.randrange(n_slaves)
                addr = i_slave*slave_region_size + n*master_region_size + i_access
                data = addr
                yield rw, addr, data

        master_patterns   = [list(gen_pattern(i, pattern_length)) for i in range(n_masters)]
        slave_decoders    = [self.address_decoder(i, size=slave_region_size) for i in range(n_slaves)]
        slave_decoders_py = [self.address_decoder(i, size=slave_region_size, python=True)
                             for i in range(n_slaves)]

        generators, checkers = self.interconnect_test(master_patterns, slave_decoders,
                                                      timeout=timeout, **kwargs)

        for gen in generators:
            read_errors = ["  0x{:08x} vs 0x{:08x}".format(v, ref) for v, ref in gen.read_errors]
            msg = "\ngen.resp_errors = {}\ngen.read_errors = \n{}".format(
                gen.resp_errors, "\n".join(read_errors))
            if not kwargs.get("disconnected_slaves", None):
                self.assertEqual(gen.errors, 0, msg=msg)
            else:  # when some slaves are disconnected we should have some errors
                self.assertNotEqual(gen.errors, 0, msg=msg)

        # make sure all the accesses at slave side are in correct address region
        for i_slave, (checker, decoder) in enumerate(zip(checkers, slave_decoders_py)):
            for addr in (entry[0] for entry in checker.writes + checker.reads):
                # compensate for the fact that decoders work on word-aligned addresses
                self.assertNotEqual(decoder(addr >> 2), 0)

    def test_interconnect_shared_stress_no_delay(self):
        self.interconnect_stress_test(timeout=1000,
                                      master_delay=0,
                                      slave_ready_latency=0,
                                      slave_response_latency=0)

    def test_interconnect_shared_stress_rand_short(self):
        prng = random.Random(42)
        rand = lambda: prng.randrange(4)
        self.interconnect_stress_test(timeout=2000,
                                      master_delay=rand,
                                      slave_ready_latency=rand,
                                      slave_response_latency=rand)

    def test_interconnect_shared_stress_rand_long(self):
        prng = random.Random(42)
        rand = lambda: prng.randrange(16)
        self.interconnect_stress_test(timeout=4000,
                                      master_delay=rand,
                                      slave_ready_latency=rand,
                                      slave_response_latency=rand)

    def test_interconnect_shared_stress_timeout(self):
        self.interconnect_stress_test(timeout=4000,
                                      disconnected_slaves=[1],
                                      timeout_cycles=50)

    def test_crossbar_stress_no_delay(self):
        self.interconnect_stress_test(timeout=1000,
                                      master_delay=0,
                                      slave_ready_latency=0,
                                      slave_response_latency=0,
                                      interconnect=AXILiteCrossbar)

    def test_crossbar_stress_rand(self):
        prng = random.Random(42)
        rand = lambda: prng.randrange(4)
        self.interconnect_stress_test(timeout=2000,
                                      master_delay=rand,
                                      slave_ready_latency=rand,
                                      slave_response_latency=rand,
                                      interconnect=AXILiteCrossbar)
