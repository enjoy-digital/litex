#
# This file is part of LiteX.
#
# Copyright (c) 2019-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *

from litex.gen import *

from litex.soc.interconnect.axi import *
from litex.soc.interconnect import wishbone

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

class AXIChecker:
    def __init__(self, ready_latency=0, response_latency=0, rdata_generator=None):
        self.ready_latency    = ready_latency
        self.response_latency = response_latency
        self.rdata_generator  = rdata_generator or (lambda addr: 0xbaadc0de)
        self.writes           = [] # (addr, data, strb, id)
        self.reads            = [] # (addr, data, id)

    def delay(self, latency):
        for _ in range(_int_or_call(latency)):
            yield

    def handle_write(self, axi):
        while not (yield axi.aw.valid):
            yield
        yield from self.delay(self.ready_latency)
        addr       = (yield axi.aw.addr)
        burst_type = (yield axi.aw.burst)
        burst_len  = (yield axi.aw.len)
        burst_size = (yield axi.aw.size)
        write_id   = (yield axi.aw.id)
        yield axi.aw.ready.eq(1)
        yield
        yield axi.aw.ready.eq(0)

        payloads = []
        while len(payloads) < (burst_len + 1):
            while not (yield axi.w.valid):
                yield
            yield from self.delay(self.ready_latency)
            payloads.append(((yield axi.w.data), (yield axi.w.strb)))
            last = (yield axi.w.last)
            yield axi.w.ready.eq(1)
            yield
            yield axi.w.ready.eq(0)
            if last:
                break

        assert len(payloads) == burst_len + 1
        for beat, (data, strb) in zip(Burst(addr, burst_type, burst_len, burst_size).to_beats(), payloads):
            self.writes.append((beat.addr, data, strb, write_id))

        yield from self.delay(self.response_latency)
        yield axi.b.valid.eq(1)
        yield axi.b.id.eq(write_id)
        yield axi.b.resp.eq(RESP_OKAY)
        yield
        while not (yield axi.b.ready):
            yield
        yield axi.b.valid.eq(0)
        yield axi.b.id.eq(0)

    def handle_read(self, axi):
        while not (yield axi.ar.valid):
            yield
        yield from self.delay(self.ready_latency)
        addr       = (yield axi.ar.addr)
        burst_type = (yield axi.ar.burst)
        burst_len  = (yield axi.ar.len)
        burst_size = (yield axi.ar.size)
        read_id    = (yield axi.ar.id)
        yield axi.ar.ready.eq(1)
        yield
        yield axi.ar.ready.eq(0)

        yield from self.delay(self.response_latency)
        beats = Burst(addr, burst_type, burst_len, burst_size).to_beats()
        for i, beat in enumerate(beats):
            yield axi.r.valid.eq(1)
            yield axi.r.id.eq(read_id)
            yield axi.r.resp.eq(RESP_OKAY)
            yield axi.r.data.eq(self.rdata_generator(beat.addr))
            yield axi.r.last.eq(i == (len(beats) - 1))
            yield
            while not (yield axi.r.ready):
                yield
            self.reads.append((beat.addr, self.rdata_generator(beat.addr), read_id))

        yield axi.r.valid.eq(0)
        yield axi.r.id.eq(0)
        yield axi.r.data.eq(0)
        yield axi.r.last.eq(0)

    @passive
    def _write_handler(self, axi):
        while True:
            yield from self.handle_write(axi)
            yield

    @passive
    def _read_handler(self, axi):
        while True:
            yield from self.handle_read(axi)
            yield

    def parallel_handlers(self, axi):
        return self._write_handler(axi), self._read_handler(axi)

class AXIPatternGenerator:
    def __init__(self, axi, pattern, delay=0, id_base=0):
        # pattern: (rw, addr, data[, id])
        self.axi         = axi
        self.pattern     = pattern
        self.delay       = delay
        self.id_base     = id_base
        self.errors      = 0
        self.id_errors   = 0
        self.last_errors = 0
        self.read_errors = []
        self.resp_errors = {"w": 0, "r": 0}

    def write(self, addr, data, req_id, strb=None):
        axi = self.axi
        if strb is None:
            strb = 2**len(axi.w.strb) - 1

        yield axi.aw.valid.eq(1)
        yield axi.aw.addr.eq(addr)
        yield axi.aw.burst.eq(BURST_INCR)
        yield axi.aw.len.eq(0)
        yield axi.aw.size.eq(log2_int(axi.data_width//8))
        yield axi.aw.id.eq(req_id)
        yield
        while (yield axi.aw.ready) == 0:
            yield
        yield axi.aw.valid.eq(0)

        yield axi.w.valid.eq(1)
        yield axi.w.data.eq(data)
        yield axi.w.strb.eq(strb)
        yield axi.w.last.eq(1)
        yield
        while (yield axi.w.ready) == 0:
            yield
        yield axi.w.valid.eq(0)

        yield axi.b.ready.eq(1)
        yield
        while (yield axi.b.valid) == 0:
            yield
        resp = (yield axi.b.resp)
        bid  = (yield axi.b.id)
        yield axi.b.ready.eq(0)
        yield
        return resp, bid

    def read(self, addr, req_id):
        axi = self.axi

        yield axi.ar.valid.eq(1)
        yield axi.ar.addr.eq(addr)
        yield axi.ar.burst.eq(BURST_INCR)
        yield axi.ar.len.eq(0)
        yield axi.ar.size.eq(log2_int(axi.data_width//8))
        yield axi.ar.id.eq(req_id)
        yield
        while (yield axi.ar.ready) == 0:
            yield
        yield axi.ar.valid.eq(0)

        yield axi.r.ready.eq(1)
        yield
        while (yield axi.r.valid) == 0:
            yield
        data = (yield axi.r.data)
        resp = (yield axi.r.resp)
        rid  = (yield axi.r.id)
        last = (yield axi.r.last)
        yield axi.r.ready.eq(0)
        yield
        return data, resp, rid, last

    def handler(self):
        for i, entry in enumerate(self.pattern):
            rw, addr, data = entry[:3]
            req_id = entry[3] if len(entry) > 3 else (self.id_base + i)
            assert rw in ["w", "r"]
            if rw == "w":
                resp, rsp_id = (yield from self.write(addr, data, req_id))
            else:
                rdata, resp, rsp_id, last = (yield from self.read(addr, req_id))
                if rdata != data:
                    self.read_errors.append((rdata, data))
                    self.errors += 1
                if last != 1:
                    self.last_errors += 1
                    self.errors += 1
            if resp != RESP_OKAY:
                self.resp_errors[rw] += 1
                self.errors += 1
            if rsp_id != req_id:
                self.id_errors += 1
                self.errors += 1
            for _ in range(_int_or_call(self.delay)):
                yield
        for _ in range(16):
            yield

# Software Models ----------------------------------------------------------------------------------

class Burst:
    def __init__(self, addr, type=BURST_FIXED, len=0, size=0):
        self.addr = addr
        self.type = type
        self.len  = len
        self.size = size

    def to_beats(self):
        r = []
        burst_length = self.len + 1
        burst_size   = 2**self.size
        for i in range(burst_length):
            if self.type == BURST_INCR:
                offset = i*2**(self.size)
                r += [Beat(self.addr + offset)]
            elif self.type == BURST_WRAP:
                assert burst_length in [2, 4, 8, 16]
                assert (self.addr % burst_size) == 0
                burst_base   = self.addr - self.addr % (burst_length * burst_size)
                burst_offset = self.addr % (burst_length * burst_size)
                burst_addr   = burst_base + (burst_offset + i*burst_size) % (burst_length * burst_size)
                #print("0x{:08x}".format(burst_addr))
                r += [Beat(burst_addr)]
            else:
                r += [Beat(self.addr)]
        return r


class Beat:
    def __init__(self, addr):
        self.addr = addr


class Access(Burst):
    def __init__(self, addr, data, id, **kwargs):
        Burst.__init__(self, addr, **kwargs)
        self.data = data
        self.id   = id


class Write(Access): pass

class Read(Access): pass

# TestAXI ------------------------------------------------------------------------------------------

class TestAXI(unittest.TestCase):
    def test_burst2beat(self):
        def bursts_generator(ax, bursts, valid_rand=50):
            prng = random.Random(42)
            for burst in bursts:
                yield ax.valid.eq(1)
                yield ax.addr.eq(burst.addr)
                yield ax.burst.eq(burst.type)
                yield ax.len.eq(burst.len)
                yield ax.size.eq(burst.size)
                while (yield ax.ready) == 0:
                    yield
                yield ax.valid.eq(0)
                while prng.randrange(100) < valid_rand:
                    yield
                yield

        @passive
        def beats_checker(ax, beats, ready_rand=50):
            self.errors = 0
            yield ax.ready.eq(0)
            prng = random.Random(42)
            for beat in beats:
                while ((yield ax.valid) and (yield ax.ready)) == 0:
                    if prng.randrange(100) > ready_rand:
                        yield ax.ready.eq(1)
                    else:
                        yield ax.ready.eq(0)
                    yield
                ax_addr = (yield ax.addr)
                #print("0x{:08x}".format(ax_addr))
                if ax_addr != beat.addr:
                    self.errors += 1
                yield

        # DUT
        ax_burst = AXIStreamInterface(layout=ax_description(32), id_width=32)
        ax_beat  = AXIStreamInterface(layout=ax_description(32), id_width=32)
        dut      =  AXIBurst2Beat(ax_burst, ax_beat)

        # Generate DUT input (bursts).
        prng = random.Random(42)
        bursts = []
        for i in range(32):
            bursts.append(Burst(prng.randrange(2**32), BURST_FIXED, prng.randrange(255), log2_int(32//8)))
            bursts.append(Burst(prng.randrange(2**32), BURST_INCR, prng.randrange(255), log2_int(32//8)))
        bursts.append(Burst(4, BURST_WRAP, 4-1, log2_int(2)))
        bursts.append(Burst(0x80000160, BURST_WRAP, 0x3, 0b100))

        # Generate expected DUT output (beats for reference).
        beats = []
        for burst in bursts:
            beats += burst.to_beats()

        # Simulation
        generators = [
            bursts_generator(ax_burst, bursts),
            beats_checker(ax_beat, beats)
        ]
        run_simulation(dut, generators)
        self.assertEqual(self.errors, 0)


    def _test_axi2wishbone(self,
        naccesses=16, simultaneous_writes_reads=False,
        # Random: 0: min (no random), 100: max.
        # Burst randomness.
        id_rand_enable   = False,
        len_rand_enable  = False,
        data_rand_enable = False,
        # Flow valid randomness.
        aw_valid_random  = 0,
        w_valid_random   = 0,
        ar_valid_random  = 0,
        r_valid_random   = 0,
        # Flow ready randomness.
        w_ready_random   = 0,
        b_ready_random   = 0,
        r_ready_random   = 0
        ):

        def writes_cmd_generator(axi_port, writes):
            prng = random.Random(42)
            for write in writes:
                while prng.randrange(100) < aw_valid_random:
                    yield
                # Send command.
                yield axi_port.aw.valid.eq(1)
                yield axi_port.aw.addr.eq(write.addr<<2)
                yield axi_port.aw.burst.eq(write.type)
                yield axi_port.aw.len.eq(write.len)
                yield axi_port.aw.size.eq(write.size)
                yield axi_port.aw.id.eq(write.id)
                yield
                while (yield axi_port.aw.ready) == 0:
                    yield
                yield axi_port.aw.valid.eq(0)

        def writes_data_generator(axi_port, writes):
            prng = random.Random(42)
            yield axi_port.w.strb.eq(2**(len(axi_port.w.data)//8) - 1)
            for write in writes:
                for i, data in enumerate(write.data):
                    while prng.randrange(100) < w_valid_random:
                        yield
                    # Send data.
                    yield axi_port.w.valid.eq(1)
                    if (i == (len(write.data) - 1)):
                        yield axi_port.w.last.eq(1)
                    else:
                        yield axi_port.w.last.eq(0)
                    yield axi_port.w.data.eq(data)
                    yield
                    while (yield axi_port.w.ready) == 0:
                        yield
                    yield axi_port.w.valid.eq(0)
            axi_port.reads_enable = True

        def writes_response_generator(axi_port, writes):
            prng = random.Random(42)
            self.writes_id_errors = 0
            for write in writes:
                # wait response
                yield axi_port.b.ready.eq(0)
                yield
                while (yield axi_port.b.valid) == 0:
                    yield
                while prng.randrange(100) < b_ready_random:
                    yield
                yield axi_port.b.ready.eq(1)
                yield
                if (yield axi_port.b.id) != write.id:
                    self.writes_id_errors += 1

        def reads_cmd_generator(axi_port, reads):
            prng = random.Random(42)
            while not axi_port.reads_enable:
                yield
            for read in reads:
                while prng.randrange(100) < ar_valid_random:
                    yield
                # Send command.
                yield axi_port.ar.valid.eq(1)
                yield axi_port.ar.addr.eq(read.addr<<2)
                yield axi_port.ar.burst.eq(read.type)
                yield axi_port.ar.len.eq(read.len)
                yield axi_port.ar.size.eq(read.size)
                yield axi_port.ar.id.eq(read.id)
                yield
                while (yield axi_port.ar.ready) == 0:
                    yield
                yield axi_port.ar.valid.eq(0)

        def reads_response_data_generator(axi_port, reads):
            prng = random.Random(42)
            self.reads_data_errors = 0
            self.reads_id_errors   = 0
            self.reads_last_errors = 0
            while not axi_port.reads_enable:
                yield
            for read in reads:
                for i, data in enumerate(read.data):
                    # Wait data / response.
                    yield axi_port.r.ready.eq(0)
                    yield
                    while (yield axi_port.r.valid) == 0:
                        yield
                    while prng.randrange(100) < r_ready_random:
                        yield
                    yield axi_port.r.ready.eq(1)
                    yield
                    if (yield axi_port.r.data) != data:
                        self.reads_data_errors += 1
                    if (yield axi_port.r.id) != read.id:
                        self.reads_id_errors += 1
                    if i == (len(read.data) - 1):
                        if (yield axi_port.r.last) != 1:
                            self.reads_last_errors += 1
                    else:
                        if (yield axi_port.r.last) != 0:
                            self.reads_last_errors += 1

        # DUT
        class DUT(Module):
            def __init__(self):
                self.axi      = AXIInterface(data_width=32, address_width=32, id_width=8)
                self.wishbone = wishbone.Interface(data_width=32, adr_width=30, addressing="word")

                axi2wishbone = AXI2Wishbone(self.axi, self.wishbone)
                self.submodules += axi2wishbone

                wishbone_mem = wishbone.SRAM(1024, bus=self.wishbone)
                self.submodules += wishbone_mem

        dut = DUT()

        # Generate writes/reads.
        prng   = random.Random(42)
        writes = []
        offset = 1
        for i in range(naccesses):
            _id   = prng.randrange(2**8) if id_rand_enable else i
            _len  = prng.randrange(32) if len_rand_enable else i
            _data = [prng.randrange(2**32) if data_rand_enable else j for j in range(_len + 1)]
            writes.append(Write(offset, _data, _id, type=BURST_INCR, len=_len, size=log2_int(32//8)))
            offset += _len + 1
        # Dummy reads to ensure datas have been written before the effective reads start.
        dummy_reads = [Read(1023, [0], 0, type=BURST_FIXED, len=0, size=log2_int(32//8)) for _ in range(32)]
        reads = writes

        # Simulation
        if simultaneous_writes_reads:
            dut.axi.reads_enable = True
        else:
            dut.axi.reads_enable = False # Will be set by writes_data_generator.
        generators = [
            writes_cmd_generator(dut.axi, writes),
            writes_data_generator(dut.axi, writes),
            writes_response_generator(dut.axi, writes),
            reads_cmd_generator(dut.axi, reads),
            reads_response_data_generator(dut.axi, reads)
        ]
        run_simulation(dut, generators)
        self.assertEqual(self.writes_id_errors,  0)
        self.assertEqual(self.reads_data_errors, 0)
        self.assertEqual(self.reads_id_errors,   0)
        self.assertEqual(self.reads_last_errors, 0)

    # Test with no randomness.
    def test_axi2wishbone_writes_then_reads_no_random(self):
        self._test_axi2wishbone(simultaneous_writes_reads=False)

    # Test randomness one parameter at a time.
    def test_axi2wishbone_writes_then_reads_random_bursts(self):
        self._test_axi2wishbone(
            simultaneous_writes_reads = False,
            id_rand_enable   = True,
            len_rand_enable  = True,
            data_rand_enable = True)

    def test_axi2wishbone_random_w_ready(self):
        self._test_axi2wishbone(w_ready_random=90)

    def test_axi2wishbone_random_b_ready(self):
        self._test_axi2wishbone(b_ready_random=90)

    def test_axi2wishbone_random_r_ready(self):
        self._test_axi2wishbone(r_ready_random=90)

    def test_axi2wishbone_random_aw_valid(self):
        self._test_axi2wishbone(aw_valid_random=90)

    def test_axi2wishbone_random_w_valid(self):
        self._test_axi2wishbone(w_valid_random=90)

    def test_axi2wishbone_random_ar_valid(self):
        self._test_axi2wishbone(ar_valid_random=90)

    def test_axi2wishbone_random_r_valid(self):
        self._test_axi2wishbone(r_valid_random=90)

    # Now let's stress things a bit... :)
    def test_axi2wishbone_random_all(self):
        self._test_axi2wishbone(
            simultaneous_writes_reads = False,
            id_rand_enable  = True,
            len_rand_enable = True,
            aw_valid_random = 50,
            w_ready_random  = 50,
            b_ready_random  = 50,
            w_valid_random  = 50,
            ar_valid_random = 90,
            r_valid_random  = 90,
            r_ready_random  = 90
        )

    def test_axi_down_converter(self):
        class DUT(LiteXModule):
            def __init__(self, dw_from=64, dw_to=32):
                self.axi_master = AXIInterface(data_width=dw_from)
                axi_slave       = AXIInterface(data_width=dw_to)
                wb_slave        = wishbone.Interface(data_width=dw_to, address_width=axi_slave.address_width, addressing="word")
                self.converter = AXIConverter(self.axi_master, axi_slave)
                self.axi2wb    = AXI2Wishbone(axi_slave, wb_slave)
                self.mem       = wishbone.SRAM(1024, bus=wb_slave, init=range(256))

        def read_generator(dut):
            axi_port = dut.axi_master

            # AXI Read.
            addr = 0x34
            yield axi_port.ar.addr.eq(addr * 4)
            yield axi_port.ar.valid.eq(1)
            yield axi_port.ar.burst.eq(0b1)
            yield axi_port.ar.len.eq(0)
            yield axi_port.ar.size.eq(0b011)
            yield axi_port.r.ready.eq(1)
            yield
            while (yield axi_port.r.valid) == 0:
                yield
            rd = (yield axi_port.r.data)

            # Check Mem Content.
            mem_content = 0
            i = 0
            while i < axi_port.data_width // dut.mem.bus.data_width:
                mem_content |= (yield dut.mem.mem[addr + i]) << (i * dut.mem.bus.data_width)
                i += 1
            assert rd == mem_content, (hex(rd), hex(mem_content))

        def write_generator(dut):
            axi_port = dut.axi_master

            # AXI Write.
            addr = 0x24
            data = 0x98761244
            yield axi_port.aw.addr.eq(addr * 4)
            yield axi_port.aw.valid.eq(1)
            yield axi_port.aw.burst.eq(0b1)
            yield axi_port.aw.len.eq(0)
            yield axi_port.aw.size.eq(0b011)
            yield axi_port.w.strb.eq(0b111111111)
            yield axi_port.w.data.eq(data)
            yield axi_port.w.valid.eq(1)
            yield axi_port.w.last.eq(1)
            yield
            while (yield axi_port.aw.ready) == 0:
                yield
            yield axi_port.aw.valid.eq(0)
            while (yield axi_port.w.ready) == 0:
                yield
            yield axi_port.w.valid.eq(0)

            # Check Mem Content.
            mem_content = 0
            i = 0
            while i < axi_port.data_width // dut.mem.bus.data_width:
                mem_content |= (yield dut.mem.mem[addr + i]) << (i * dut.mem.bus.data_width)
                i += 1
            assert data == mem_content, (hex(data), hex(mem_content))

        dut = DUT(64, 32)
        run_simulation(dut, [read_generator(dut), write_generator(dut)], vcd_name="sim.vcd")

    def test_timeout(self):
        class DUT(Module):
            def __init__(self):
                self.master = master = AXIInterface(id_width=8)
                self.slave  = slave  = AXIInterface(id_width=8)
                self.submodules.interconnect = AXIInterconnectPointToPoint(master, slave)
                self.submodules.timeout = AXITimeout(master, 16)

        def generator(axi):
            pattern = AXIPatternGenerator(axi, [])

            resp, rsp_id = (yield from pattern.write(0x00001000, 0x11111111, req_id=0x12))
            self.assertEqual(resp, RESP_SLVERR)
            self.assertEqual(rsp_id, 0x12)

            data, resp, rsp_id, last = (yield from pattern.read(0x00002000, req_id=0x34))
            self.assertEqual(resp, RESP_SLVERR)
            self.assertEqual(rsp_id, 0x34)
            self.assertEqual(last, 1)
            self.assertEqual(data, 0xffffffff)

        dut = DUT()
        generators = [
            generator(dut.master),
            timeout_generator(300),
        ]
        run_simulation(dut, generators)

    def address_decoder(self, i, size=0x100, python=False):
        # bytes to 32-bit words aligned
        _size   = (size) >> 2
        _origin = (size * i) >> 2
        if python:
            shift = log2_int(_size)
            return lambda a: ((a >> shift) == (_origin >> shift))
        return lambda a: (a[log2_int(_size):] == (_origin >> log2_int(_size)))

    def interconnect_test(self, master_patterns, slave_decoders,
                                master_delay=0, slave_ready_latency=0, slave_response_latency=0,
                                disconnected_slaves=None, timeout=300, interconnect=AXIInterconnectShared,
                                **kwargs):
        class DUT(Module):
            def __init__(self, n_masters, decoders, **kwargs):
                self.masters = [AXIInterface(id_width=8, name="master") for _ in range(n_masters)]
                self.slaves  = [AXIInterface(id_width=8, name="slave")  for _ in range(len(decoders))]
                slaves = list(zip(decoders, self.slaves))
                self.submodules.interconnect = interconnect(self.masters, slaves, **kwargs)

        class ReadDataGenerator:
            def __init__(self, patterns):
                self.mem = {}
                for pattern in patterns:
                    for rw, addr, val, *rest in pattern:
                        if rw == "r":
                            assert addr not in self.mem
                            self.mem[addr] = val

            def getter(self, n):
                return lambda addr: self.mem.get(addr, 0xbaad0000 + n)

        def new_checker(rdata_generator):
            return AXIChecker(
                ready_latency    = slave_ready_latency,
                response_latency = slave_response_latency,
                rdata_generator  = rdata_generator,
            )

        dut = DUT(len(master_patterns), slave_decoders, **kwargs)
        rdata_generator = ReadDataGenerator(master_patterns)
        checkers = [new_checker(rdata_generator.getter(i)) for i, _ in enumerate(dut.slaves)]
        pattern_generators = [
            AXIPatternGenerator(dut.masters[i], pattern, delay=master_delay, id_base=i << 4)
            for i, pattern in enumerate(master_patterns)
        ]

        generators  = [gen.handler() for gen in pattern_generators]
        for i, (slave, checker) in enumerate(zip(dut.slaves, checkers)):
            if i in (disconnected_slaves or []):
                continue
            generators += list(checker.parallel_handlers(slave))
        generators += [timeout_generator(timeout)]
        run_simulation(dut, generators)
        return pattern_generators, checkers

    def test_interconnect_shared_stress_rand(self):
        prng = random.Random(42)

        n_masters = 3
        n_slaves = 3
        pattern_length = 32
        slave_region_size = 0x1000
        master_region_size = 0x100
        assert n_masters * master_region_size < slave_region_size

        def gen_pattern(n, length):
            assert 4*length <= master_region_size
            for i_access in range(length):
                rw = "w" if prng.randint(0, 1) == 0 else "r"
                i_slave = prng.randrange(n_slaves)
                addr = i_slave*slave_region_size + n*master_region_size + 4*i_access
                data = addr
                yield rw, addr, data

        master_patterns   = [list(gen_pattern(i, pattern_length)) for i in range(n_masters)]
        slave_decoders    = [self.address_decoder(i, size=slave_region_size) for i in range(n_slaves)]
        slave_decoders_py = [self.address_decoder(i, size=slave_region_size, python=True)
                             for i in range(n_slaves)]

        generators, checkers = self.interconnect_test(master_patterns, slave_decoders,
                                                      timeout=2000,
                                                      master_delay=1,
                                                      slave_ready_latency=lambda: prng.randrange(3),
                                                      slave_response_latency=lambda: prng.randrange(3))

        for gen in generators:
            read_errors = ["  0x{:08x} vs 0x{:08x}".format(v, ref) for v, ref in gen.read_errors]
            msg = "\n".join([
                "gen.resp_errors = {}".format(gen.resp_errors),
                "gen.id_errors   = {}".format(gen.id_errors),
                "gen.last_errors = {}".format(gen.last_errors),
                "gen.read_errors = ",
                "\n".join(read_errors),
            ])
            self.assertEqual(gen.errors, 0, msg=msg)

        for checker, decoder in zip(checkers, slave_decoders_py):
            for addr in [entry[0] for entry in checker.writes + checker.reads]:
                self.assertNotEqual(decoder(addr >> 2), 0)

    def test_crossbar_timeout(self):
        slave_region_size = 0x100
        master_patterns = [
            [("w", 0x000, 0x10), ("w", 0x100, 0x11), ("r", 0x200, 0x200)],
            [("r", 0x004, 0x004), ("r", 0x104, 0x104), ("w", 0x204, 0x204)],
            [("w", 0x008, 0x008), ("r", 0x108, 0x108), ("w", 0x208, 0x208)],
        ]
        slave_decoders    = [self.address_decoder(i, size=slave_region_size) for i in range(3)]
        slave_decoders_py = [self.address_decoder(i, size=slave_region_size, python=True) for i in range(3)]

        generators, checkers = self.interconnect_test(master_patterns, slave_decoders,
                                                      disconnected_slaves=[1],
                                                      timeout=1000,
                                                      interconnect=AXICrossbar,
                                                      timeout_cycles=128)

        for gen in generators:
            self.assertEqual(gen.resp_errors["w"] + gen.resp_errors["r"], 1)
            self.assertEqual(gen.id_errors, 0)

        for i, (checker, decoder) in enumerate(zip(checkers, slave_decoders_py)):
            if i == 1:
                self.assertEqual(checker.writes, [])
                self.assertEqual(checker.reads, [])
                continue
            for addr in [entry[0] for entry in checker.writes + checker.reads]:
                self.assertNotEqual(decoder(addr >> 2), 0)
