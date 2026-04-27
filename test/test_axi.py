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

# AXI4 driver helpers (used by AXISRAM tests) ------------------------------------------------------

def axi_aw_send(axi, addr, burst_len=0, burst_type=BURST_INCR, size=2, id=0):
    yield axi.aw.valid.eq(1)
    yield axi.aw.addr.eq(addr)
    yield axi.aw.burst.eq(burst_type)
    yield axi.aw.len.eq(burst_len)
    yield axi.aw.size.eq(size)
    yield axi.aw.id.eq(id)
    yield
    while (yield axi.aw.ready) == 0:
        yield
    yield axi.aw.valid.eq(0)

def axi_w_send(axi, data, last):
    yield axi.w.valid.eq(1)
    yield axi.w.data.eq(data)
    yield axi.w.strb.eq(2**(axi.data_width//8) - 1)
    yield axi.w.last.eq(int(last))
    yield
    while (yield axi.w.ready) == 0:
        yield
    yield axi.w.valid.eq(0)

def axi_b_recv(axi):
    yield axi.b.ready.eq(1)
    while (yield axi.b.valid) == 0:
        yield
    resp = (yield axi.b.resp)
    yield axi.b.ready.eq(0)
    yield
    return resp

def axi_ar_send(axi, addr, burst_len=0, burst_type=BURST_INCR, size=2, id=0):
    yield axi.ar.valid.eq(1)
    yield axi.ar.addr.eq(addr)
    yield axi.ar.burst.eq(burst_type)
    yield axi.ar.len.eq(burst_len)
    yield axi.ar.size.eq(size)
    yield axi.ar.id.eq(id)
    yield
    while (yield axi.ar.ready) == 0:
        yield
    yield axi.ar.valid.eq(0)

def axi_r_recv_one(axi):
    yield axi.r.ready.eq(1)
    while (yield axi.r.valid) == 0:
        yield
    data = (yield axi.r.data)
    resp = (yield axi.r.resp)
    last = (yield axi.r.last)
    yield axi.r.ready.eq(0)
    yield
    return data, resp, last

def axi_write_single(axi, addr, data, size=2):
    yield from axi_aw_send(axi, addr, size=size)
    yield from axi_w_send(axi, data, last=True)
    return (yield from axi_b_recv(axi))

def axi_read_single(axi, addr, size=2):
    yield from axi_ar_send(axi, addr, size=size)
    data, resp, _ = yield from axi_r_recv_one(axi)
    return data, resp

def axi_write_burst(axi, addr, beats, burst_type=BURST_INCR, size=2):
    yield from axi_aw_send(axi, addr, burst_len=len(beats) - 1, burst_type=burst_type, size=size)
    for i, beat in enumerate(beats):
        yield from axi_w_send(axi, beat, last=(i == len(beats) - 1))
    return (yield from axi_b_recv(axi))

def axi_read_burst(axi, addr, length, burst_type=BURST_INCR, size=2):
    yield from axi_ar_send(axi, addr, burst_len=length - 1, burst_type=burst_type, size=size)
    datas = []
    for _ in range(length):
        data, resp, _last = yield from axi_r_recv_one(axi)
        if resp != RESP_OKAY:
            return None
        datas.append(data)
    return datas

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

    # AXISRAM helper: builds a DUT with a 32-bit AXI bus and runs the supplied generator.
    def _axisram_run(self, generator, size=64*4, init=None, data_width=32):
        class DUT(LiteXModule):
            def __init__(self, size, init):
                self.axi  = AXIInterface(data_width=data_width, address_width=32, id_width=4)
                self.sram = AXISRAM(size, init=init, bus=self.axi)
                self.errors = 0
        prng = random.Random(0)
        if init is None:
            init = [prng.randrange(2**data_width) for _ in range(size//(data_width//8))]
        dut = DUT(size=size, init=init)
        run_simulation(dut, [generator(dut, init)])
        return dut

    def test_axi_sram(self):
        # Smoke test: single-beat init readback, single-beat writes, then one INCR-16 burst.
        def gen(dut, ref_init):
            prng = random.Random(42)
            # Read each init cell back single-beat.
            for word_addr, ref in enumerate(ref_init):
                data, resp = yield from axi_read_single(dut.axi, word_addr * 4)
                if resp != RESP_OKAY or data != ref:
                    dut.errors += 1
            # Single-beat overwrite, single-beat readback.
            new_values = [prng.randrange(2**32) for _ in ref_init]
            for word_addr, value in enumerate(new_values):
                resp = yield from axi_write_single(dut.axi, word_addr * 4, value)
                if resp != RESP_OKAY:
                    dut.errors += 1
            for word_addr, value in enumerate(new_values):
                data, resp = yield from axi_read_single(dut.axi, word_addr * 4)
                if resp != RESP_OKAY or data != value:
                    dut.errors += 1
            # 16-beat INCR burst at a clean address.
            base   = 0x80
            beats  = [prng.randrange(2**32) for _ in range(16)]
            resp   = yield from axi_write_burst(dut.axi, base, beats)
            if resp != RESP_OKAY:
                dut.errors += 1
            datas  = yield from axi_read_burst(dut.axi, base, 16)
            if datas != beats:
                dut.errors += 1

        dut = self._axisram_run(gen, size=64*4)
        self.assertEqual(dut.errors, 0)

    def test_axi_sram_burst_lengths(self):
        # Sweep INCR burst length across all supported sizes.  AXI4 allows len=0..255 (1..256 beats);
        # cache controllers and DMAs typically use lengths matching their cache-line / payload size,
        # so the interesting points are 1, 2, 4, 8, 16, 32, 64, 128, 256.
        lengths = [1, 2, 4, 8, 16, 32, 64, 128, 256]
        size_words = max(lengths) * 2  # leave headroom past the longest burst

        def gen(dut, _ref_init):
            prng = random.Random(123)
            base = 0
            for n in lengths:
                beats = [prng.randrange(2**32) for _ in range(n)]
                resp  = yield from axi_write_burst(dut.axi, base, beats)
                if resp != RESP_OKAY:
                    dut.errors += 1
                read = yield from axi_read_burst(dut.axi, base, n)
                if read != beats:
                    dut.errors += 1
                base += n * 4

        dut = self._axisram_run(gen, size=size_words * 4)
        self.assertEqual(dut.errors, 0)

    def test_axi_sram_wrap_burst(self):
        # WRAP bursts are how cache-line refills are typically issued (AXI4-allowed lengths: 2/4/8/16,
        # start address aligned to size).  After issuing a WRAP-N burst at addr X, the data must land
        # at the wrapped physical addresses.  We verify by writing in WRAP order then reading back
        # single-beat from each unwrapped address.
        def gen(dut, _ref_init):
            prng = random.Random(7)
            for wrap_len in [2, 4, 8, 16]:
                # 4 bytes per beat, total burst block = wrap_len * 4 bytes.
                block_bytes = wrap_len * 4
                # Pick a start that's not at the bottom of the wrap block to actually exercise wrap.
                base_block  = wrap_len * 4 * 4   # well-spaced per length
                start_off   = (wrap_len // 2) * 4
                start_addr  = base_block + start_off

                beats = [prng.randrange(2**32) for _ in range(wrap_len)]
                resp  = yield from axi_write_burst(dut.axi, start_addr, beats, burst_type=BURST_WRAP)
                if resp != RESP_OKAY:
                    dut.errors += 1

                # Compute expected memory contents: WRAP start + i, modulo block_bytes within the block.
                expected = [None] * wrap_len
                for i, beat in enumerate(beats):
                    off_within_block = (start_off + i*4) % block_bytes
                    expected[off_within_block // 4] = beat

                # Verify by single-beat reads from each block address.
                for i, want in enumerate(expected):
                    addr = base_block + i*4
                    data, resp = yield from axi_read_single(dut.axi, addr)
                    if resp != RESP_OKAY or data != want:
                        dut.errors += 1

                # Also verify a WRAP read returns the same beats we wrote, in WRAP order.
                read = yield from axi_read_burst(dut.axi, start_addr, wrap_len, burst_type=BURST_WRAP)
                if read != beats:
                    dut.errors += 1

        dut = self._axisram_run(gen, size=4096)
        self.assertEqual(dut.errors, 0)

    def test_axi_sram_back_to_back(self):
        # Run many alternating writes and reads of varied burst types and lengths to flush out FSM
        # bugs in the AXI2AXILite bridge (state not reset between bursts, AW/AR contention, etc.).
        def gen(dut, _ref_init):
            prng     = random.Random(31337)
            mem_size = 1024  # bytes
            # Software model of the SRAM that we keep in sync with each write so reads can be checked.
            model    = [0] * (mem_size // 4)

            for _ in range(40):
                op_is_write = prng.randrange(2)
                length      = prng.choice([1, 2, 4, 8, 16])
                base_word   = prng.randrange((mem_size // 4) - length + 1)
                base_addr   = base_word * 4

                if op_is_write:
                    beats = [prng.randrange(2**32) for _ in range(length)]
                    resp  = yield from axi_write_burst(dut.axi, base_addr, beats)
                    if resp != RESP_OKAY:
                        dut.errors += 1
                    for i, beat in enumerate(beats):
                        model[base_word + i] = beat
                else:
                    read = yield from axi_read_burst(dut.axi, base_addr, length)
                    expect = model[base_word:base_word + length]
                    if read != expect:
                        dut.errors += 1

        # Pre-fill the SRAM with zeros so the model matches.
        dut = self._axisram_run(gen, size=1024, init=[0] * 256)
        self.assertEqual(dut.errors, 0)

    def test_axi_sram_64bit(self):
        # Same shape as the basic test but on a 64-bit AXI bus; exercises wider data, wider strobe,
        # and the AXILiteSRAM internal port being instantiated at width 64.
        def gen(dut, ref_init):
            prng = random.Random(8)
            # Single-beat readback of init.
            for word_addr, ref in enumerate(ref_init):
                data, resp = yield from axi_read_single(dut.axi, word_addr * 8, size=3)
                if resp != RESP_OKAY or data != ref:
                    dut.errors += 1
            # 8-beat INCR burst at a clean address.
            base  = 0x80
            beats = [prng.randrange(2**64) for _ in range(8)]
            resp  = yield from axi_write_burst(dut.axi, base, beats, size=3)
            if resp != RESP_OKAY:
                dut.errors += 1
            read  = yield from axi_read_burst(dut.axi, base, 8, size=3)
            if read != beats:
                dut.errors += 1

        dut = self._axisram_run(gen, size=64 * 8, data_width=64)
        self.assertEqual(dut.errors, 0)
