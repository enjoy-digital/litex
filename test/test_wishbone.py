#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import pytest

from migen import *

from litex.gen import *
from litex.soc.interconnect import wishbone
from litex.soc.integration.soc_core import SoCRegion

from .common import run_simulation_case


pytestmark = pytest.mark.unit


def _addressing_div(addressing):
    return {
        "byte": 1,
        "word": 4,
    }[addressing]


def _run_remap_test(addressing, writes, expected_addresses, remapper_kwargs, settle_cycles=0):
    adr_div = _addressing_div(addressing)

    class DUT(LiteXModule):
        def __init__(self):
            self.master = wishbone.Interface(data_width=32, address_width=32, addressing=addressing)
            self.slave  = wishbone.Interface(data_width=32, address_width=32, addressing=addressing)
            self.remapper = wishbone.Remapper(self.master, self.slave, **remapper_kwargs)

    def generator(dut):
        for address in writes:
            yield from dut.master.write(address // adr_div, 0)

    def checker(dut):
        yield dut.slave.ack.eq(1)
        while (yield dut.slave.stb) == 0:
            yield
        for address in expected_addresses:
            assert (yield dut.slave.adr) == address // adr_div
            yield
        for _ in range(settle_cycles):
            yield

    dut = DUT()
    run_simulation_case(dut, [generator(dut), checker(dut)])


def test_upconverter_16_32():
    class DUT(LiteXModule):
        def __init__(self):
            self.wb16 = wishbone.Interface(data_width=16, address_width=32, addressing="word")
            wb32 = wishbone.Interface(data_width=32, address_width=32, addressing="word")
            self.submodules += wishbone.UpConverter(self.wb16, wb32)
            self.submodules += wishbone.SRAM(32, bus=wb32)

    def generator(dut):
        yield from dut.wb16.write(0x0000, 0x1234)
        yield from dut.wb16.write(0x0001, 0x5678)
        yield from dut.wb16.write(0x0002, 0xdead)
        yield from dut.wb16.write(0x0003, 0xbeef)
        assert (yield from dut.wb16.read(0x0000)) == 0x1234
        assert (yield from dut.wb16.read(0x0001)) == 0x5678
        assert (yield from dut.wb16.read(0x0002)) == 0xdead
        assert (yield from dut.wb16.read(0x0003)) == 0xbeef

    dut = DUT()
    run_simulation_case(dut, generator(dut))


def test_converter_32_64_32():
    class DUT(LiteXModule):
        def __init__(self):
            self.wb32 = wishbone.Interface(data_width=32, address_width=32, addressing="word")
            wb64 = wishbone.Interface(data_width=64, address_width=32, addressing="word")
            wb32 = wishbone.Interface(data_width=32, address_width=32, addressing="word")
            self.submodules += wishbone.UpConverter(self.wb32, wb64)
            self.submodules += wishbone.DownConverter(wb64, wb32)
            self.submodules += wishbone.SRAM(32, bus=wb32)

    def generator(dut):
        yield from dut.wb32.write(0x0000, 0x12345678)
        yield from dut.wb32.write(0x0001, 0xdeadbeef)
        assert (yield from dut.wb32.read(0x0000)) == 0x12345678
        assert (yield from dut.wb32.read(0x0001)) == 0xdeadbeef

    dut = DUT()
    run_simulation_case(dut, generator(dut))


@pytest.mark.parametrize(
    ("cti", "bte"),
    [
        (wishbone.CTI_BURST_INCREMENTING, None),
        (wishbone.CTI_BURST_INCREMENTING, 0b01),
        (wishbone.CTI_BURST_CONSTANT, None),
    ],
    ids=["incrementing", "wrap", "constant"],
)
def test_sram_burst_modes(cti, bte):
    writes = [
        (0x0001 if bte is not None else 0x0000, 0x01234567, cti),
        (0x0002 if bte is not None else 0x0001, 0x89abcdef, cti),
        (0x0003 if bte is not None else 0x0002, 0xdeadbeef, cti),
        (0x0000 if bte is not None else 0x0003, 0xc0ffee00, wishbone.CTI_BURST_END),
    ]

    class DUT(LiteXModule):
        def __init__(self):
            self.wb = wishbone.Interface(data_width=32, address_width=32, addressing="word", bursting=True)
            self.submodules += wishbone.SRAM(32, bus=self.wb)

    def generator(dut):
        for address, data, current_cti in writes:
            kwargs = {"cti": current_cti}
            if bte is not None:
                kwargs["bte"] = bte
            yield from dut.wb.write(address, data, **kwargs)

        for address, data, current_cti in writes:
            kwargs = {"cti": current_cti}
            if bte is not None:
                kwargs["bte"] = bte
            assert (yield from dut.wb.read(address, **kwargs)) == data

    dut = DUT()
    run_simulation_case(dut, generator(dut))


def test_origin_remap_byte_legacy():
    _run_remap_test(
        addressing="byte",
        writes=[
            0x0000_0000,
            0x0000_0004,
            0x0000_0008,
            0x0000_000c,
            0x1000_0000,
            0x1000_0004,
            0x1000_0008,
            0x1000_000c,
        ],
        expected_addresses=[
            0x0001_0000,
            0x0001_0004,
            0x0001_0008,
            0x0001_000c,
            0x0001_0000,
            0x0001_0004,
            0x0001_0008,
            0x0001_000c,
        ],
        remapper_kwargs={
            "origin": 0x0001_0000,
            "size": 0x1000_0000,
        },
    )


@pytest.mark.parametrize("addressing", ["byte", "word"])
def test_origin_remap(addressing):
    _run_remap_test(
        addressing=addressing,
        writes=[
            0x0000_0000,
            0x0000_0004,
            0x0000_0008,
            0x0000_000c,
            0x1000_0000,
            0x1000_0004,
            0x1000_0008,
            0x1000_000c,
        ],
        expected_addresses=[
            0x0001_0000,
            0x0001_0004,
            0x0001_0008,
            0x0001_000c,
            0x0001_0000,
            0x0001_0004,
            0x0001_0008,
            0x0001_000c,
        ],
        remapper_kwargs={
            "origin": 0x0001_0000,
            "size": 0x1000_0000,
        },
    )


@pytest.mark.parametrize("addressing", ["byte", "word"])
def test_region_remap(addressing):
    _run_remap_test(
        addressing=addressing,
        writes=[
            0x0000_0000,
            0x0001_0004,
            0x0002_0008,
            0x0003_000c,
        ],
        expected_addresses=[
            0x0000_0000,
            0x1000_0004,
            0x2000_0008,
            0x3000_000c,
        ],
        remapper_kwargs={
            "src_regions": [
                SoCRegion(origin=0x0000_0000, size=0x1000),
                SoCRegion(origin=0x0001_0000, size=0x1000),
                SoCRegion(origin=0x0002_0000, size=0x1000),
                SoCRegion(origin=0x0003_0000, size=0x1000),
            ],
            "dst_regions": [
                SoCRegion(origin=0x0000_0000, size=0x1000),
                SoCRegion(origin=0x1000_0000, size=0x1000),
                SoCRegion(origin=0x2000_0000, size=0x1000),
                SoCRegion(origin=0x3000_0000, size=0x1000),
            ],
        },
    )


@pytest.mark.parametrize("addressing", ["byte", "word"])
def test_origin_region_remap(addressing):
    _run_remap_test(
        addressing=addressing,
        writes=[
            0x6000_0000,
            0x6001_0000,
            0x6001_0040,
        ],
        expected_addresses=[
            0xf000_0000,
            0x8100_0000,
            0x2000_0000,
        ],
        remapper_kwargs={
            "origin": 0x0000_0000,
            "size": 0x2000_0000,
            "src_regions": [
                SoCRegion(origin=0x0000_0000, size=65536),
                SoCRegion(origin=0x0001_0000, size=64),
                SoCRegion(origin=0x0001_0040, size=8),
            ],
            "dst_regions": [
                SoCRegion(origin=0xf000_0000, size=65536),
                SoCRegion(origin=0x8100_0000, size=64),
                SoCRegion(origin=0x2000_0000, size=8),
            ],
        },
        settle_cycles=128,
    )
