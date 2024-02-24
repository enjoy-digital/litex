#
# This file is part of LiteX.
#
# Copyright (c) 2022-2023 MoTeC
# Copyright (c) 2022-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import inspect

from migen import Record

from litex.gen.sim import run_simulation

from litex.soc.cores.spi.spi_mmap import (
    SPIMaster,
    SPIMMAP,
    SPI_SLOT_BITORDER_LSB_FIRST,
    SPI_SLOT_BITORDER_MSB_FIRST,
    SPI_SLOT_LENGTH_16B,
    SPI_SLOT_LENGTH_32B,
    SPI_SLOT_LENGTH_8B,
    SPI_SLOT_MODE_0,
    SPI_SLOT_MODE_3,
)

verbose = None


def unittest_verbosity():
    """Return the verbosity setting of the currently running unittest
    program, or 0 if none is running.

    """
    frame = inspect.currentframe()
    while frame:
        self = frame.f_locals.get("self")
        if isinstance(self, unittest.TestProgram):
            return self.verbosity
        frame = frame.f_back
    return 0


def vprint(*args):
    global verbose
    if verbose is None:
        verbose = unittest_verbosity()
    if verbose > 1:
        print(*args)


class TestSPIMMAP(unittest.TestCase):
    def test_spi_master(self):
        pads = Record([("clk", 1), ("cs_n", 4), ("mosi", 1), ("miso", 1)])
        dut = SPIMaster(pads=pads, data_width=32, sys_clk_freq=int(100e6))

        def generator(dut):
            data = [
                0x12345678,
                0xDEADBEEF,
            ]
            # data = [
            #    0x80000001,
            #    0x80000001,
            # ]

            # Config: Mode0, Loopback, Sys-Clk/4
            yield dut.loopback.eq(1)
            yield dut.clk_divider.eq(4)
            yield dut.mode.eq(SPI_SLOT_MODE_0)
            yield
            yield dut.mosi.eq(data[0])
            yield dut.cs.eq(0b0001)
            yield dut.length.eq(32)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            while (yield dut.done) == 0b0:
                yield
            yield dut.cs.eq(0b0000)
            for i in range(16):
                yield
            print(f"mosi_data : {(yield dut.miso):08x}")

            # Config: Mode3, Loopback, Sys-Clk/4.
            yield dut.loopback.eq(1)
            yield dut.clk_divider.eq(4)
            yield dut.mode.eq(SPI_SLOT_MODE_3)
            yield
            yield dut.mosi.eq(data[0])
            yield dut.cs.eq(0b0001)
            yield dut.length.eq(32)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            while (yield dut.done) == 0b0:
                yield
            yield dut.cs.eq(0b0000)
            for i in range(16):
                yield
            print(f"mosi_data : {(yield dut.miso):08x}")

            # Config: Mode0, Loopback, Sys-Clk/8.
            yield dut.loopback.eq(1)
            yield dut.clk_divider.eq(8)
            yield dut.mode.eq(SPI_SLOT_MODE_0)
            yield
            yield dut.mosi.eq(data[1])
            yield dut.cs.eq(0b0001)
            yield dut.length.eq(32)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            while (yield dut.done) == 0b0:
                yield
            yield dut.cs.eq(0b0000)
            for i in range(16):
                yield
            print(f"mosi_data : {(yield dut.miso):08x}")

            # Config: Mode3, Loopback, Sys-Clk/8.
            yield dut.loopback.eq(1)
            yield dut.clk_divider.eq(8)
            yield dut.mode.eq(SPI_SLOT_MODE_3)
            yield
            yield dut.mosi.eq(data[1])
            yield dut.cs.eq(0b0001)
            yield dut.length.eq(32)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            while (yield dut.done) == 0b0:
                yield
            yield dut.cs.eq(0b0000)
            for i in range(16):
                yield
            print(f"mosi_data : {(yield dut.miso):08x}")

        run_simulation(dut, generator(dut), vcd_name="sim.vcd")

    def mmap_test(self, length, bitorder, data, vcd_name=None, sel_override=None):
        pads = Record([("clk", 1), ("cs_n", 4), ("mosi", 1), ("miso", 1)])
        dut = SPIMMAP(
            pads=pads,
            data_width=32,
            sys_clk_freq=int(100e6),  # only used for clock settle time!
            tx_fifo_depth=32,
            rx_fifo_depth=32,
        )

        def generator(dut):
            # Minimal setup - spi_mmap ctrl defaults are everything enabled and:
            # SPI_SLOT_MODE_3, SPI_SLOT_LENGTH_32B, SPI_SLOT_BITORDER_MSB_FIRST, loopback, divider=2,
            version = yield dut.ctrl._version.status
            vprint(f"version: {version}")
            vprint(f"slot_count: {(yield dut.ctrl.slot_count.status)}")
            # yield dut.ctrl.slot_control0.fields.enable.eq(1)
            # yield dut.ctrl.slot_control0.fields.mode.eq(SPI_SLOT_MODE_3)
            yield dut.ctrl.slot_control0.fields.length.eq(length)
            yield dut.ctrl.slot_control0.fields.bitorder.eq(bitorder)
            # yield dut.ctrl.slot_control0.fields.loopback.eq(1)
            # yield dut.ctrl.slot_control0.fields.divider.eq(2)
            # yield dut.ctrl.slot_control0.fields.enable.eq(1)
            if length == SPI_SLOT_LENGTH_32B:
                spi_length = 32
                sel = 0b1111
                width = 8
            if length == SPI_SLOT_LENGTH_16B:
                spi_length = 16
                sel = 0b0011
                width = 4
            if length == SPI_SLOT_LENGTH_8B:
                spi_length = 8
                sel = 0b0001
                width = 2
            if sel_override:
                sel = sel_override

            vprint(f"spi_length {spi_length} width {width} sel {sel:b} len(data) {len(data)}")

            dut_tx_status = dut.ctrl.tx_status.fields
            dut_rx_status = dut.ctrl.rx_status.fields
            self.assertEqual((yield dut_tx_status.empty), 1)
            self.assertEqual((yield dut_tx_status.full), 0)
            self.assertEqual((yield dut_tx_status.ongoing), 0)
            self.assertEqual((yield dut_tx_status.level), 0)
            self.assertEqual((yield dut_rx_status.empty), 1)
            self.assertEqual((yield dut_rx_status.full), 0)
            self.assertEqual((yield dut_rx_status.ongoing), 0)
            self.assertEqual((yield dut_rx_status.level), 0)
            for d in data:
                vprint(f"write {d:0{width}x}")
                yield from dut.tx_mmap.bus.write(0, d, sel)
            yield
            self.assertEqual((yield dut_tx_status.empty), 0)
            self.assertEqual((yield dut_tx_status.full), 0)
            self.assertEqual((yield dut_tx_status.ongoing), 1)
            self.assertGreater((yield dut_tx_status.level), 0)
            self.assertEqual((yield dut_rx_status.empty), 1)
            self.assertEqual((yield dut_rx_status.full), 0)
            self.assertEqual((yield dut_rx_status.ongoing), 1)
            self.assertEqual((yield dut_rx_status.level), 0)

            tx_empty = -1
            rx_empty = -1
            miso = -1
            mosi = -1
            while (yield dut_rx_status.ongoing) == 0b1 or (yield dut_rx_status.level) != len(data):
                if rx_empty != (rx_empty := (yield dut_rx_status.empty)):
                    vprint(f"rx_empty:{rx_empty}")
                if tx_empty != (tx_empty := (yield dut_tx_status.empty)):
                    vprint(f"tx_empty:{tx_empty}")
                if mosi != (mosi := (yield dut.tx_rx_engine.spi.mosi)):
                    vprint(f"mosi => {mosi:0{width}x}")
                if miso != (miso := (yield dut.tx_rx_engine.spi.miso)):
                    vprint(f"miso <= {miso:0{width}x}")
                yield

            yield
            for d in data:
                read = yield from dut.rx_mmap.bus.read(0)
                self.assertEqual(read, d, f"read {read:0{width}x} expect: {d:0{width}x}")

        run_simulation(dut, generator(dut), vcd_name=vcd_name)

    # 32 bit write to 32bit slot
    def test_spi_mmap_32_lsb(self):
        data = [0x12345678, 0x9ABCDEF0]
        self.mmap_test(SPI_SLOT_LENGTH_32B, SPI_SLOT_BITORDER_LSB_FIRST, data, "mmap_32_lsb.vcd")

    def test_spi_mmap_32_msb(self):
        data = [0x12345678, 0x9ABCDEF0]
        self.mmap_test(SPI_SLOT_LENGTH_32B, SPI_SLOT_BITORDER_MSB_FIRST, data, "mmap_32_msb.vcd")

    # 16 bit write to 16bit slot
    def test_spi_mmap_16_lsb(self):
        data = [0x1234, 0x5678, 0x9ABC, 0xDEF0]
        self.mmap_test(SPI_SLOT_LENGTH_16B, SPI_SLOT_BITORDER_LSB_FIRST, data, "mmap_16_lsb.vcd")

    def test_spi_mmap_16_msb(self):
        data = [0x1234, 0x5678, 0x9ABC, 0xDEF0]
        self.mmap_test(SPI_SLOT_LENGTH_16B, SPI_SLOT_BITORDER_MSB_FIRST, data, "mmap_16_msb.vcd")

    # 32 bit write to 16bit slot
    def test_spi_mmap_16_lsb_wb32(self):
        data = [0x1234, 0x5678, 0x9ABC, 0xDEF0]
        self.mmap_test(
            SPI_SLOT_LENGTH_16B,
            SPI_SLOT_BITORDER_LSB_FIRST,
            data,
            "mmap_16_lsb_wb32.vcd",
            sel_override=0b1111,
        )

    def test_spi_mmap_16_msb_wb32(self):
        data = [0x1234, 0x5678, 0x9ABC, 0xDEF0]
        self.mmap_test(
            SPI_SLOT_LENGTH_16B,
            SPI_SLOT_BITORDER_MSB_FIRST,
            data,
            "mmap_16_msb_wb32.vcd",
            sel_override=0b1111,
        )

    # 8 bit write to 8bit slot
    def test_spi_mmap_8_lsb(self):
        data = [0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0]
        self.mmap_test(SPI_SLOT_LENGTH_8B, SPI_SLOT_BITORDER_LSB_FIRST, data, "mmap_8_lsb.vcd")

    def test_spi_mmap_8_msb(self):
        data = [0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0]
        self.mmap_test(SPI_SLOT_LENGTH_8B, SPI_SLOT_BITORDER_MSB_FIRST, data, "mmap_8_msb.vcd")


if __name__ == "__main__":
    unittest.main()
