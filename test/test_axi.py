#
# This file is part of LiteX.
#
# Copyright (c) 2019-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import pytest

from migen import *

from litex.gen import *
from litex.soc.interconnect.axi import *
from litex.soc.interconnect import wishbone

from .common import run_simulation_case, seeded_prng


pytestmark = pytest.mark.unit


class Burst:
    def __init__(self, addr, type=BURST_FIXED, len=0, size=0):
        self.addr = addr
        self.type = type
        self.len  = len
        self.size = size

    def to_beats(self):
        beats = []
        burst_length = self.len + 1
        burst_size   = 2**self.size
        for i in range(burst_length):
            if self.type == BURST_INCR:
                offset = i * burst_size
                beats.append(Beat(self.addr + offset))
            elif self.type == BURST_WRAP:
                assert burst_length in [2, 4, 8, 16]
                assert (self.addr % burst_size) == 0
                burst_base   = self.addr - self.addr % (burst_length * burst_size)
                burst_offset = self.addr % (burst_length * burst_size)
                burst_addr   = burst_base + (burst_offset + i * burst_size) % (burst_length * burst_size)
                beats.append(Beat(burst_addr))
            else:
                beats.append(Beat(self.addr))
        return beats


class Beat:
    def __init__(self, addr):
        self.addr = addr


class Access(Burst):
    def __init__(self, addr, data, id, **kwargs):
        Burst.__init__(self, addr, **kwargs)
        self.data = data
        self.id   = id


class Write(Access):
    pass


class Read(Access):
    pass


def _build_test_bursts():
    prng = seeded_prng()
    bursts = []
    for _ in range(32):
        bursts.append(Burst(prng.randrange(2**32), BURST_FIXED, prng.randrange(255), log2_int(32//8)))
        bursts.append(Burst(prng.randrange(2**32), BURST_INCR,  prng.randrange(255), log2_int(32//8)))
    bursts.append(Burst(4, BURST_WRAP, 4 - 1, log2_int(2)))
    bursts.append(Burst(0x80000160, BURST_WRAP, 0x3, 0b100))
    return bursts


def test_burst2beat():
    errors = {"count": 0}

    def bursts_generator(ax, bursts, valid_rand=50):
        prng = seeded_prng()
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
        yield ax.ready.eq(0)
        prng = seeded_prng()
        for beat in beats:
            while ((yield ax.valid) and (yield ax.ready)) == 0:
                yield ax.ready.eq(int(prng.randrange(100) > ready_rand))
                yield
            if (yield ax.addr) != beat.addr:
                errors["count"] += 1
            yield

    ax_burst = AXIStreamInterface(layout=ax_description(32), id_width=32)
    ax_beat  = AXIStreamInterface(layout=ax_description(32), id_width=32)
    dut      = AXIBurst2Beat(ax_burst, ax_beat)

    bursts = _build_test_bursts()
    beats = []
    for burst in bursts:
        beats.extend(burst.to_beats())

    run_simulation_case(dut, [
        bursts_generator(ax_burst, bursts),
        beats_checker(ax_beat, beats),
    ])
    assert errors["count"] == 0


def run_axi2wishbone_case(
    naccesses=16,
    simultaneous_writes_reads=False,
    id_rand_enable=False,
    len_rand_enable=False,
    data_rand_enable=False,
    aw_valid_random=0,
    w_valid_random=0,
    ar_valid_random=0,
    r_valid_random=0,
    w_ready_random=0,
    b_ready_random=0,
    r_ready_random=0,
):
    metrics = {
        "writes_id_errors": 0,
        "reads_data_errors": 0,
        "reads_id_errors": 0,
        "reads_last_errors": 0,
    }

    class DUT(Module):
        def __init__(self):
            self.axi      = AXIInterface(data_width=32, address_width=32, id_width=8)
            self.wishbone = wishbone.Interface(data_width=32, adr_width=30, addressing="word")

            self.submodules += AXI2Wishbone(self.axi, self.wishbone)
            self.submodules += wishbone.SRAM(1024, bus=self.wishbone)

    def writes_cmd_generator(axi_port, writes):
        prng = seeded_prng()
        for write in writes:
            while prng.randrange(100) < aw_valid_random:
                yield
            yield axi_port.aw.valid.eq(1)
            yield axi_port.aw.addr.eq(write.addr << 2)
            yield axi_port.aw.burst.eq(write.type)
            yield axi_port.aw.len.eq(write.len)
            yield axi_port.aw.size.eq(write.size)
            yield axi_port.aw.id.eq(write.id)
            yield
            while (yield axi_port.aw.ready) == 0:
                yield
            yield axi_port.aw.valid.eq(0)

    def writes_data_generator(axi_port, writes):
        prng = seeded_prng()
        yield axi_port.w.strb.eq(2**(len(axi_port.w.data)//8) - 1)
        for write in writes:
            for i, data in enumerate(write.data):
                while prng.randrange(100) < w_valid_random:
                    yield
                yield axi_port.w.valid.eq(1)
                yield axi_port.w.last.eq(int(i == (len(write.data) - 1)))
                yield axi_port.w.data.eq(data)
                yield
                while (yield axi_port.w.ready) == 0:
                    yield
                yield axi_port.w.valid.eq(0)
        axi_port.reads_enable = True

    def writes_response_generator(axi_port, writes):
        prng = seeded_prng()
        for write in writes:
            yield axi_port.b.ready.eq(0)
            yield
            while (yield axi_port.b.valid) == 0:
                yield
            while prng.randrange(100) < b_ready_random:
                yield
            yield axi_port.b.ready.eq(1)
            yield
            if (yield axi_port.b.id) != write.id:
                metrics["writes_id_errors"] += 1

    def reads_cmd_generator(axi_port, reads):
        prng = seeded_prng()
        while not axi_port.reads_enable:
            yield
        for read in reads:
            while prng.randrange(100) < ar_valid_random:
                yield
            yield axi_port.ar.valid.eq(1)
            yield axi_port.ar.addr.eq(read.addr << 2)
            yield axi_port.ar.burst.eq(read.type)
            yield axi_port.ar.len.eq(read.len)
            yield axi_port.ar.size.eq(read.size)
            yield axi_port.ar.id.eq(read.id)
            yield
            while (yield axi_port.ar.ready) == 0:
                yield
            yield axi_port.ar.valid.eq(0)

    def reads_response_data_generator(axi_port, reads):
        prng = seeded_prng()
        while not axi_port.reads_enable:
            yield
        for read in reads:
            for i, data in enumerate(read.data):
                yield axi_port.r.ready.eq(0)
                yield
                while (yield axi_port.r.valid) == 0:
                    yield
                while prng.randrange(100) < r_ready_random:
                    yield
                yield axi_port.r.ready.eq(1)
                yield
                if (yield axi_port.r.data) != data:
                    metrics["reads_data_errors"] += 1
                if (yield axi_port.r.id) != read.id:
                    metrics["reads_id_errors"] += 1
                expected_last = int(i == (len(read.data) - 1))
                if (yield axi_port.r.last) != expected_last:
                    metrics["reads_last_errors"] += 1

    dut = DUT()

    prng   = seeded_prng()
    writes = []
    offset = 1
    for i in range(naccesses):
        _id   = prng.randrange(2**8) if id_rand_enable else i
        _len  = prng.randrange(32)   if len_rand_enable else i
        _data = [prng.randrange(2**32) if data_rand_enable else j for j in range(_len + 1)]
        writes.append(Write(offset, _data, _id, type=BURST_INCR, len=_len, size=log2_int(32//8)))
        offset += _len + 1
    reads = writes

    dut.axi.reads_enable = simultaneous_writes_reads
    run_simulation_case(dut, [
        writes_cmd_generator(dut.axi, writes),
        writes_data_generator(dut.axi, writes),
        writes_response_generator(dut.axi, writes),
        reads_cmd_generator(dut.axi, reads),
        reads_response_data_generator(dut.axi, reads),
    ])

    assert metrics["writes_id_errors"] == 0
    assert metrics["reads_data_errors"] == 0
    assert metrics["reads_id_errors"] == 0
    assert metrics["reads_last_errors"] == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"simultaneous_writes_reads": False}, id="no-random"),
        pytest.param({
            "simultaneous_writes_reads": False,
            "id_rand_enable": True,
            "len_rand_enable": True,
            "data_rand_enable": True,
        }, id="random-bursts"),
        pytest.param({"w_ready_random": 90}, id="random-w-ready"),
        pytest.param({"b_ready_random": 90}, id="random-b-ready"),
        pytest.param({"r_ready_random": 90}, id="random-r-ready"),
        pytest.param({"aw_valid_random": 90}, id="random-aw-valid"),
        pytest.param({"w_valid_random": 90}, id="random-w-valid"),
        pytest.param({"ar_valid_random": 90}, id="random-ar-valid"),
        pytest.param({"r_valid_random": 90}, id="random-r-valid"),
        pytest.param({
            "simultaneous_writes_reads": False,
            "id_rand_enable": True,
            "len_rand_enable": True,
            "aw_valid_random": 50,
            "w_ready_random": 50,
            "b_ready_random": 50,
            "w_valid_random": 50,
            "ar_valid_random": 90,
            "r_valid_random": 90,
            "r_ready_random": 90,
        }, id="random-all"),
    ],
)
def test_axi2wishbone_variants(kwargs):
    run_axi2wishbone_case(**kwargs)


def test_axi_down_converter():
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

        mem_content = 0
        for i in range(axi_port.data_width // dut.mem.bus.data_width):
            mem_content |= (yield dut.mem.mem[addr + i]) << (i * dut.mem.bus.data_width)
        assert rd == mem_content, (hex(rd), hex(mem_content))

    def write_generator(dut):
        axi_port = dut.axi_master
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

        mem_content = 0
        for i in range(axi_port.data_width // dut.mem.bus.data_width):
            mem_content |= (yield dut.mem.mem[addr + i]) << (i * dut.mem.bus.data_width)
        assert data == mem_content, (hex(data), hex(mem_content))

    dut = DUT(64, 32)
    run_simulation_case(dut, [read_generator(dut), write_generator(dut)])
