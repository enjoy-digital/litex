#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import random

import pytest
from migen import If, Memory, Signal
from migen.fhdl.simplify import FullMemoryWE
from migen.sim import run_simulation

from litex.gen import LiteXModule
from litex.soc.interconnect import wishbone


def initial_word(address):
    return (0x12345678 ^ (address*0x01020305)) & 0xffffffff


class CacheDUT(LiteXModule):
    def __init__(self, width=128, reverse=False, bursting=False, latency=1, full_we=False,
        refill_bypass=False):
        self.master = master = wishbone.Interface(data_width=32, address_width=16)
        self.slave = slave = wishbone.Interface(data_width=width, address_width=16)
        cache = wishbone.Cache(64, master, slave, reverse=reverse,
            with_bursting=bursting, with_refill_bypass=refill_bypass)
        self.cache = FullMemoryWE()(cache) if full_we else cache
        ratio = width//32
        init = [sum(initial_word(index*ratio + lane) << (32*(ratio-1-lane if reverse else lane))
                    for lane in range(ratio)) for index in range(512)]
        memory = Memory(width, len(init), init=init)
        port = memory.get_port(write_capable=True, we_granularity=8)
        self.specials += memory, port
        count = Signal(max=latency+1)
        self.comb += [
            port.adr.eq(slave.adr),
            port.dat_w.eq(slave.dat_w),
            slave.dat_r.eq(port.dat_r),
            slave.ack.eq(slave.cyc & slave.stb & (count == latency)),
        ]
        for byte in range(width//8):
            self.comb += port.we[byte].eq(slave.ack & slave.we & slave.sel[byte])
        self.sync += If(~slave.cyc | ~slave.stb | slave.ack,
            count.eq(0)
        ).Else(
            count.eq(count + 1)
        )


def transfer(bus, beats, stalls=None, bte=0):
    """Each beat is (word address, write data or None, byte select, CTI)."""
    values, gaps = [], []
    yield bus.cyc.eq(1)
    yield bus.bte.eq(bte)
    for index, (address, data, select, cti) in enumerate(beats):
        if stalls and index in stalls:
            yield bus.stb.eq(0)
            # The address is unspecified while stalled; exercise RAM-index tracking.
            yield bus.adr.eq(address ^ 32)
            for _ in range(stalls[index]):
                yield
                assert not (yield bus.ack)
        yield bus.stb.eq(1)
        yield bus.adr.eq(address)
        yield bus.we.eq(data is not None)
        yield bus.dat_w.eq(data or 0)
        yield bus.sel.eq(select)
        yield bus.cti.eq(cti)
        elapsed = 0
        while True:
            yield
            elapsed += 1
            assert elapsed < 100, "cache transaction timed out"
            assert not (yield bus.err)
            if (yield bus.ack):
                values.append((yield bus.dat_r))
                gaps.append(elapsed)
                break
    yield bus.cyc.eq(0)
    yield bus.stb.eq(0)
    yield bus.we.eq(0)
    yield bus.cti.eq(wishbone.CTI_BURST_NONE)
    yield
    assert not (yield bus.ack)
    return values, gaps


def read_beats(addresses, cti=wishbone.CTI_BURST_INCREMENTING):
    return [(address, None, 15, cti if index != len(addresses)-1 else wishbone.CTI_BURST_END)
            for index, address in enumerate(addresses)]


@pytest.mark.parametrize("width", [32, 64, 128, 256])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("bursting", [False, True])
@pytest.mark.parametrize("full_we", [False, True])
def test_same_line_burst_hits(width, reverse, bursting, full_we):
    dut = CacheDUT(width, reverse, bursting, full_we=full_we)
    addresses = list(range(128, 128 + width//32))

    def generator():
        yield from transfer(dut.master, read_beats([128]))
        values, gaps = yield from transfer(dut.master, read_beats(addresses))
        assert values == [initial_word(address) for address in addresses]
        assert gaps[1:] == [1 if bursting else 2]*(len(addresses)-1)

    run_simulation(dut, generator())


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("latency", [1, 4])
@pytest.mark.parametrize("bte", [0, 1, 2, 3])
def test_burst_boundaries_wraps_and_stalls(reverse, latency, bte):
    dut = CacheDUT(reverse=reverse, bursting=True, latency=latency)
    # Cross RAM indices and change tag while retaining the same cache index.
    # The address presented by the master is authoritative, including wrapping.
    addresses = [130, 131, 128, 129] if bte else [130, 131, 132, 133]
    addresses += [192, 193, 194, 195, 128, 129]

    def generator():
        values, _ = yield from transfer(dut.master, read_beats(addresses), stalls={3: 2, 7: 1}, bte=bte)
        assert values == [initial_word(address) for address in addresses]
        values, gaps = yield from transfer(dut.master, read_beats([129]*4, wishbone.CTI_BURST_CONSTANT))
        assert values == [initial_word(129)]*4
        assert gaps[1:] == [1]*3
        # A classic cycle after a terminated burst must not reuse a live-lane acknowledgement.
        values, _ = yield from transfer(dut.master, [(200, None, 15, wishbone.CTI_BURST_NONE)])
        assert values == [initial_word(200)]

    run_simulation(dut, generator())


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("full_we", [False, True])
@pytest.mark.parametrize("refill_bypass", [False, True])
def test_burst_read_write_transition_and_dirty_eviction(reverse, full_we, refill_bypass):
    dut = CacheDUT(reverse=reverse, bursting=True, full_we=full_we, refill_bypass=refill_bypass)
    expected = (initial_word(129) & 0xffff00ff) | 0x0000aa00
    beats = [
        (128, None, 15, wishbone.CTI_BURST_INCREMENTING),
        (129, 0x0000aa00, 2, wishbone.CTI_BURST_INCREMENTING),
        (129, None, 15, wishbone.CTI_BURST_END),
    ]

    def generator():
        values, _ = yield from transfer(dut.master, beats)
        assert values[0] == initial_word(128)
        assert values[2] == expected
        # Evict to backing memory, then refill and check every byte/lane.
        yield from transfer(dut.master, read_beats([192]))
        values, _ = yield from transfer(dut.master, read_beats([128, 129, 130, 131]))
        assert values == [initial_word(128), expected, initial_word(130), initial_word(131)]

    run_simulation(dut, generator())


def test_cycle_end_terminates_live_burst():
    dut = CacheDUT(bursting=True)

    def generator():
        # End CYC after an acknowledged incrementing beat without sending END.
        yield from transfer(dut.master, [(128, None, 15, wishbone.CTI_BURST_INCREMENTING)])
        for _ in range(3):
            yield
            assert not (yield dut.master.ack)
        values, _ = yield from transfer(dut.master, read_beats([193, 194, 195]))
        assert values == [initial_word(address) for address in [193, 194, 195]]

    run_simulation(dut, generator())


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("refill_bypass", [False, True])
def test_random_cache_traffic(reverse, refill_bypass):
    dut = CacheDUT(reverse=reverse, bursting=True, latency=3, refill_bypass=refill_bypass)
    rng = random.Random(42)
    expected = {address: initial_word(address) for address in range(128, 320)}

    def generator():
        for _ in range(80):
            address = rng.randrange(128, 304)
            addresses = list(range(address, address + rng.randrange(1, 9)))
            beats, writes = [], []
            for index, address in enumerate(addresses):
                writing = rng.randrange(3) == 0
                data = rng.getrandbits(32) if writing else None
                select = rng.randrange(16)
                cti = wishbone.CTI_BURST_INCREMENTING if index != len(addresses)-1 else wishbone.CTI_BURST_END
                beats.append((address, data, select, cti))
                writes.append(writing)
                if writing:
                    mask = sum(255 << (8*byte) for byte in range(4) if select & (1 << byte))
                    expected[address] = (expected[address] & ~mask) | (data & mask)
            values, _ = yield from transfer(dut.master, beats, stalls={1: 1})
            for address, value, writing in zip(addresses, values, writes):
                if not writing:
                    assert value == expected[address]
        for address, expected_value in expected.items():
            values, _ = yield from transfer(dut.master, read_beats([address]))
            assert values == [expected_value]

    run_simulation(dut, generator())


@pytest.mark.parametrize("width", [32, 64, 128, 256])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("latency", [1, 4])
@pytest.mark.parametrize("bursting", [False, True])
def test_refill_bypass_saves_one_cycle(width, reverse, latency, bursting):
    measurements = []
    for enabled in [False, True]:
        dut = CacheDUT(width, reverse, bursting, latency, full_we=True, refill_bypass=enabled)
        reads, writes = [], []

        def generator():
            for lane in range(width//32):
                # Leave one tag between targets so a dirty victim from an
                # earlier iteration is not part of a later expected clean line.
                address = 128 + 128*lane + lane
                # Force a dirty victim in the same index before this read miss.
                _, gaps = yield from transfer(dut.master,
                    [(address ^ 64, 0xaabbccdd, 5, wishbone.CTI_BURST_NONE)])
                writes.append(gaps[0])
                line = address & ~(width//32 - 1)
                addresses = [line + ((lane + i) % (width//32)) for i in range(width//32)]
                values, gaps = yield from transfer(dut.master, read_beats(addresses))
                assert values == [initial_word(address) for address in addresses]
                reads.append(gaps[0])
                # A following same-line beat sees the newly filled RAM contents.
                assert gaps[1:] == [1 if bursting else 2]*(len(addresses)-1)

        run_simulation(dut, generator())
        measurements.append((reads, writes))
    assert measurements[1][0] == [cycles-1 for cycles in measurements[0][0]]
    assert measurements[1][1] == measurements[0][1]


@pytest.mark.parametrize("width", [32, 64, 128])
@pytest.mark.parametrize("reverse", [False, True])
def test_wide_master_refill_and_narrow_slave_fallback(width, reverse):
    first_reads = []
    for enabled in [False, True]:
        dut = LiteXModule()
        dut.master = wishbone.Interface(data_width=64, address_width=16)
        dut.slave = wishbone.Interface(data_width=width, address_width=16)
        dut.cache = wishbone.Cache(64, dut.master, dut.slave, reverse=reverse,
            with_bursting=True, with_refill_bypass=enabled)
        dut.memory = wishbone.SRAM(8192, bus=dut.slave)

        def generator():
            values, gaps = yield from transfer(dut.master, read_beats([128]))
            assert values == [0]
            first_reads.append(gaps[0])
            yield from transfer(dut.master, [(128, 0x1122334455667788, 255, wishbone.CTI_BURST_NONE)])
            yield from transfer(dut.master, [(128, 0xaabbccddeeff0011, 0x18, wishbone.CTI_BURST_NONE)])
            yield from transfer(dut.master, read_beats([192]))
            values, _ = yield from transfer(dut.master, read_beats([128]))
            assert values == [0x112233ddee667788]

        run_simulation(dut, generator())
    assert first_reads[1] == first_reads[0] - int(width >= 64)
