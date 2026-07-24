#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import inspect
import logging
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from types import SimpleNamespace

from migen import ClockDomain, Record, Signal
from migen.sim import run_simulation

from litex.soc.cores.dma import WishboneDMAReader
from litex.soc.cores.hyperbus import HyperRAM
from litex.soc.cores.video import video_data_layout, video_framebuffer_size
from litex.soc.interconnect import axi, stream, wishbone

from litex.soc.integration.soc import (
    LiteXSoC,
    SoC,
    SoCCore,
    SoCMini,
    SoCBusHandler,
    SoCCSRHandler,
    SoCCSRRegion,
    SoCError,
    SoCIORegion,
    SoCIRQHandler,
    SoCRegion,
    add_ip_address_constants,
    add_mac_address_constants,
    build_time,
    get_mem_data,
    mem_decoder,
    parse_video_timing_resolution,
    soc_core_argdict,
    soc_core_args,
    soc_mini_argdict,
    soc_mini_args,
)
from litex.soc.integration import soc_core


@contextmanager
def _assert_raises_soc_error(testcase):
    stderr = sys.stderr
    try:
        with testcase.assertRaises(SoCError):
            yield
    finally:
        sys.stderr = stderr


class _ConstantCollector:
    def __init__(self):
        self.constants = {}

    def add_constant(self, name, value=None, check_duplicate=True):
        self.constants[name] = value


class _FakePlatform:
    name   = "unit"
    device = "unit-test-device"

    def __init__(self):
        self.build_calls = []
        self.request_calls = []
        self.requests     = {}

    def build(self, soc, *args, **kwargs):
        self.build_calls.append((soc, args, kwargs))
        return "built"

    def request(self, name, number=None, loose=False):
        self.request_calls.append((name, number, loose))
        return self.requests.get((name, number), self.requests.get(name, None))


class _HyperRamPads:
    def __init__(self):
        self.clk   = Signal()
        self.rst_n = Signal()
        self.cs_n  = Signal()
        self.dq    = Record([("oe", 1), ("o", 8), ("i", 8)])
        self.rwds  = Record([("oe", 1), ("o", 1), ("i", 1)])


class _CRGWithReset:
    def __init__(self):
        self.rst = Signal(name="crg_rst")


class _CRGWithSysReset:
    def __init__(self):
        self.cd_sys = ClockDomain("sys")


class _CRGWithEfinityPLL:
    def __init__(self):
        self.rst = Signal(name="crg_rst")
        self.pll = SimpleNamespace(locked=Signal(name="pll_locked"))


def _make_bus_interface(interface_cls, data_width=32, address_width=32):
    return interface_cls(data_width=data_width, address_width=address_width)

class TestSoCCoreCompatibility(unittest.TestCase):
    def test_soc_core_reexports_canonical_soc_api(self):
        self.assertIs(soc_core.mem_decoder,      mem_decoder)
        self.assertIs(soc_core.get_mem_data,     get_mem_data)
        self.assertIs(soc_core.SoCCore,          SoCCore)
        self.assertIs(soc_core.SoCMini,          SoCMini)
        self.assertIs(soc_core.soc_core_args,    soc_core_args)
        self.assertIs(soc_core.soc_core_argdict, soc_core_argdict)
        self.assertIs(soc_core.soc_mini_args,    soc_mini_args)
        self.assertIs(soc_core.soc_mini_argdict, soc_mini_argdict)


class TestSoCAddressConstants(unittest.TestCase):
    def test_ip_address_constants_are_split_into_octets(self):
        soc = _ConstantCollector()

        add_ip_address_constants(soc, "LOCALIP", "192.168.1.50")

        self.assertEqual(soc.constants, {
            "LOCALIP1": 192,
            "LOCALIP2": 168,
            "LOCALIP3": 1,
            "LOCALIP4": 50,
        })

    def test_invalid_ip_address_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "four octets"):
            add_ip_address_constants(_ConstantCollector(), "IP", "192.168.1")
        with self.assertRaisesRegex(ValueError, "decimal integers"):
            add_ip_address_constants(_ConstantCollector(), "IP", "192.168.one.1")
        with self.assertRaisesRegex(ValueError, "between 0 and 255"):
            add_ip_address_constants(_ConstantCollector(), "IP", "192.168.1.256")

    def test_mac_address_constants_accept_string_and_integer_forms(self):
        from_string = _ConstantCollector()
        from_int    = _ConstantCollector()

        add_mac_address_constants(from_string, "MAC", "10:e2:d5:00:00:01")
        add_mac_address_constants(from_int, "MAC", 0x10e2d5000001)

        expected = {
            "MAC1": 0x10,
            "MAC2": 0xe2,
            "MAC3": 0xd5,
            "MAC4": 0x00,
            "MAC5": 0x00,
            "MAC6": 0x01,
        }
        self.assertEqual(from_string.constants, expected)
        self.assertEqual(from_int.constants,    expected)

    def test_invalid_mac_address_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "six octets"):
            add_mac_address_constants(_ConstantCollector(), "MAC", "10:e2:d5")
        with self.assertRaisesRegex(ValueError, "hexadecimal integers"):
            add_mac_address_constants(_ConstantCollector(), "MAC", "10:e2:d5:00:00:zz")
        with self.assertRaisesRegex(ValueError, "48 bits"):
            add_mac_address_constants(_ConstantCollector(), "MAC", 2**48)


class TestSoCVideoTiming(unittest.TestCase):
    def test_video_timing_resolution_parses_string_and_tuple_forms(self):
        self.assertEqual(parse_video_timing_resolution("800x600@60Hz"), ("800x600@60Hz", 800, 600))
        self.assertEqual(parse_video_timing_resolution(("1024x768@75Hz", "ignored")), ("1024x768@75Hz", 1024, 768))

    def test_invalid_video_timing_resolution_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "<hres>x<vres>@"):
            parse_video_timing_resolution("800@60Hz")
        with self.assertRaisesRegex(ValueError, "<hres>x<vres>@"):
            parse_video_timing_resolution("wide x high")
        with self.assertRaisesRegex(ValueError, "<hres>x<vres>@"):
            parse_video_timing_resolution(())


class TestSoCVideoFrameBuffer(unittest.TestCase):
    def test_default_region_is_placed_at_end_of_main_ram(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.bus.add_region("main_ram", SoCRegion(origin=0x40000000, size=0x04000000))

        region = soc._get_video_framebuffer_region("video_framebuffer", 0x0012c000)

        self.assertEqual(region.origin, 0x43e00000)
        self.assertEqual(region.size,   0x0012c000)
        self.assertTrue(region.linker)
        self.assertTrue(region.decode)

    def test_default_region_fits_small_main_ram(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.bus.add_region("main_ram", SoCRegion(origin=0x40000000, size=0x00800000))

        framebuffer_size = video_framebuffer_size(800, 600, "rgb888")
        region = soc._get_video_framebuffer_region("video_framebuffer", framebuffer_size)

        self.assertEqual(region.origin, 0x40600000)
        self.assertEqual(region.size,   framebuffer_size)
        self.assertLessEqual(region.origin + region.size, 0x40800000)
        self.assertTrue(region.linker)

    def test_default_region_requires_main_ram(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc._get_video_framebuffer_region("video_framebuffer", 0x0012c000)

    def test_explicit_base_overrides_mem_map(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.bus.add_region("main_ram", SoCRegion(origin=0x50000000, size=0x04000000))
        soc.mem_map["video_framebuffer"] = 0x50c00000

        region = soc._get_video_framebuffer_region(
            "video_framebuffer", 0x0012c000, base=0x51000000)

        self.assertEqual(region.origin, 0x51000000)

    def test_mem_map_base_is_used_when_explicit_base_is_absent(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.bus.add_region("main_ram", SoCRegion(origin=0x50000000, size=0x04000000))
        soc.mem_map["video_framebuffer"] = 0x50c00000

        region = soc._get_video_framebuffer_region("video_framebuffer", 0x0012c000)

        self.assertEqual(region.origin, 0x50c00000)

    def test_default_region_rejects_framebuffer_larger_than_main_ram(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.bus.add_region("main_ram", SoCRegion(origin=0x40000000, size=0x00100000))

        with _assert_raises_soc_error(self):
            soc._get_video_framebuffer_region("video_framebuffer", 0x00200000)

    def test_region_must_be_readable(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.bus.add_region("write_only", SoCRegion(
            origin = 0x20000000,
            size   = 0x00800000,
            mode   = "w",
        ))

        with _assert_raises_soc_error(self):
            soc._get_video_framebuffer_region(
                "video_framebuffer", 0x0012c000, region_name="write_only")

    def test_region_inherits_parent_attributes(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.bus.io_regions_check = False
        soc.bus.add_region("framebuffer_ram", SoCRegion(
            origin = 0x20000000,
            size   = 0x00800000,
            mode   = "rx",
            cached = False,
        ))

        region = soc._get_video_framebuffer_region(
            "video_framebuffer", 0x0012c000, region_name="framebuffer_ram")

        self.assertEqual(region.mode, "rx")
        self.assertFalse(region.cached)

    def test_system_bus_framebuffer_is_adapted_to_soc_bus_standard(self):
        cases = [
            ("wishbone", wishbone.Interface),
            ("axi-lite", axi.AXILiteInterface),
            ("axi",      axi.AXIInterface),
        ]

        for bus_standard, interface_cls in cases:
            with self.subTest(bus_standard=bus_standard):
                soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6, bus_standard=bus_standard)
                if bus_standard == "axi":
                    soc.bus.add_master("cpu", axi.AXIInterface(id_width=4))
                soc.bus.add_region("framebuffer_ram", SoCRegion(
                    origin = 0x20000000,
                    size   = 0x00800000,
                ))

                soc.add_video_framebuffer(
                    phy         = stream.Endpoint(video_data_layout),
                    timings     = "640x480@60Hz",
                    fifo_depth  = 64,
                    region_name = "framebuffer_ram",
                )

                port = soc.video_framebuffer.dma.bus
                self.assertIsInstance(port, wishbone.Interface)
                self.assertIsInstance(soc.bus.masters["video_framebuffer_dma"], interface_cls)
                self.assertEqual(port.mode, "r")
                self.assertEqual(soc.constants["VIDEO_FRAMEBUFFER_BASE"], 0x20600000)
                self.assertEqual(soc.bus.regions["video_framebuffer"].origin, 0x20600000)

    def test_missing_region_does_not_add_dma_master(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_video_framebuffer(
                phy         = stream.Endpoint(video_data_layout),
                timings     = "640x480@60Hz",
                region_name = "hyperram",
            )

        self.assertNotIn("video_framebuffer_dma", soc.bus.masters)
        self.assertNotIn("video_framebuffer", soc.bus.regions)

    def test_invalid_fifo_depth_does_not_add_dma_master(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.bus.add_region("main_ram", SoCRegion(origin=0x40000000, size=0x00800000))

        with _assert_raises_soc_error(self):
            soc.add_video_framebuffer(
                phy        = stream.Endpoint(video_data_layout),
                timings    = "640x480@60Hz",
                fifo_depth = 0,
            )

        self.assertNotIn("video_framebuffer_dma", soc.bus.masters)
        self.assertNotIn("video_framebuffer", soc.bus.regions)

    def test_secondary_region_does_not_use_native_sdram_port(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=100e6)
        soc.sdram = SimpleNamespace(crossbar=SimpleNamespace(
            get_port=lambda **kwargs: self.fail("Secondary memory used the SDRAM port.")))
        soc.bus.add_region("hyperram", SoCRegion(origin=0x20000000, size=0x00800000))

        soc.add_video_framebuffer(
            phy         = stream.Endpoint(video_data_layout),
            timings     = "640x480@60Hz",
            fifo_depth  = 64,
            region_name = "hyperram",
        )

        self.assertIsInstance(soc.video_framebuffer.dma, WishboneDMAReader)
        self.assertIs(
            soc.video_framebuffer.dma.bus,
            soc.bus.masters["video_framebuffer_dma"],
        )
        self.assertEqual(soc.constants["VIDEO_FRAMEBUFFER_BASE"], 0x20600000)

    def test_explicit_wishbone_port_is_registered(self):
        soc  = LiteXSoC(_FakePlatform(), sys_clk_freq=100e6)
        port = wishbone.Interface(data_width=64, address_width=32, mode="r")
        soc.bus.add_region("main_ram", SoCRegion(origin=0x40000000, size=0x00800000))

        soc.add_video_framebuffer(
            phy        = stream.Endpoint(video_data_layout),
            timings    = "640x480@60Hz",
            fifo_depth = 64,
            dma_port   = port,
        )

        self.assertIs(soc.video_framebuffer.dma.bus, port)
        self.assertIsInstance(soc.bus.masters["video_framebuffer_dma"], wishbone.Interface)
        self.assertEqual(soc.bus.masters["video_framebuffer_dma"].data_width, soc.bus.data_width)

    def test_dedicated_dma_bus_is_preferred(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=100e6)
        soc.dma_bus = SoCBusHandler(standard="wishbone")
        soc.bus.add_region("main_ram", SoCRegion(origin=0x40000000, size=0x00800000))

        soc.add_video_framebuffer(
            phy        = stream.Endpoint(video_data_layout),
            timings    = "640x480@60Hz",
            fifo_depth = 64,
        )

        self.assertIn("video_framebuffer_dma", soc.dma_bus.masters)
        self.assertNotIn("video_framebuffer_dma", soc.bus.masters)

    def test_native_sdram_port_is_read_only(self):
        from litedram.common import LiteDRAMNativePort
        from litedram.frontend.dma import LiteDRAMDMAReader

        port  = LiteDRAMNativePort(mode="read", address_width=24, data_width=128)
        modes = []
        soc   = LiteXSoC(_FakePlatform(), sys_clk_freq=100e6)
        soc.sdram = SimpleNamespace(crossbar=SimpleNamespace(
            get_port=lambda mode: modes.append(mode) or port))
        soc.bus.add_region("main_ram", SoCRegion(origin=0x40000000, size=0x04000000))

        soc.add_video_framebuffer(
            phy        = stream.Endpoint(video_data_layout),
            timings    = "640x480@60Hz",
            fifo_depth = 64,
        )

        self.assertEqual(modes, ["read"])
        self.assertIsInstance(soc.video_framebuffer.dma, LiteDRAMDMAReader)
        self.assertNotIn("video_framebuffer_dma", soc.bus.masters)

    def test_explicit_base_must_be_port_aligned(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=100e6)
        soc.bus.add_region("main_ram", SoCRegion(origin=0x40000000, size=0x00800000))

        with _assert_raises_soc_error(self):
            soc.add_video_framebuffer(
                phy        = stream.Endpoint(video_data_layout),
                timings    = "640x480@60Hz",
                fifo_depth = 64,
                base       = 0x40000002,
            )

        self.assertNotIn("video_framebuffer_dma", soc.bus.masters)
        self.assertNotIn("video_framebuffer", soc.bus.regions)

class TestSoCResetRequests(unittest.TestCase):
    def test_soc_reset_request_registers_source(self):
        soc   = SoC(_FakePlatform(), sys_clk_freq=1e6)
        reset = Signal()

        soc.add_soc_reset_request(name="debug", reset=reset)

        self.assertEqual(soc.soc_reset_requests["debug"], (reset, None))

    def test_duplicate_soc_reset_request_is_rejected(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.add_soc_reset_request(name="debug", reset=Signal())

        with _assert_raises_soc_error(self):
            soc.add_soc_reset_request(name="debug", reset=Signal())

    def test_crg_reset_signal_prefers_explicit_crg_rst(self):
        soc     = SoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.crg = _CRGWithReset()

        self.assertIs(soc._get_crg_reset_signal(), soc.crg.rst)

    def test_crg_reset_signal_falls_back_to_sys_reset(self):
        soc     = SoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.crg = _CRGWithSysReset()

        self.assertIs(soc._get_crg_reset_signal(), soc.crg.cd_sys.rst)

    def test_crg_reset_signal_can_disable_sys_reset_fallback(self):
        soc     = SoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.crg = _CRGWithSysReset()

        self.assertIsNone(soc._get_crg_reset_signal(with_sys_reset_fallback=False))

    def test_crg_reset_hold_signal_uses_efinity_pll_lock(self):
        from litex.build.efinix.efinity import EfinityToolchain

        platform           = _FakePlatform()
        platform.toolchain = EfinityToolchain("/tmp/efinity")
        soc                = SoC(platform, sys_clk_freq=1e6)
        soc.crg            = _CRGWithEfinityPLL()

        self.assertIs(soc._get_crg_reset_hold_signal(), soc.crg.pll.locked)


class TestSoCRegion(unittest.TestCase):
    def test_region_size_is_rounded_to_power_of_two_for_decoding(self):
        region = SoCRegion(origin=0x1000, size=0x1800, mode="rx")

        self.assertEqual(region.size,      0x1800)
        self.assertEqual(region.size_pow2, 0x2000)
        self.assertTrue(region.is_rom)

    def test_writable_region_is_not_rom(self):
        region = SoCRegion(origin=0x1000, size=0x1000, mode="rwx")

        self.assertFalse(region.is_rom)

    def test_invalid_region_size_is_rejected(self):
        with self.assertRaises(SoCError):
            SoCRegion(origin=0, size="0x1000")
        with self.assertRaises(SoCError):
            SoCRegion(origin=0, size=0)
        with self.assertRaises(SoCError):
            SoCRegion(origin=0, size=True)


class TestSoCBusHandler(unittest.TestCase):
    def test_default_addressing_follows_bus_standard(self):
        self.assertEqual(SoCBusHandler(standard="wishbone").addressing, "word")
        self.assertEqual(SoCBusHandler(standard="axi-lite").addressing, "byte")
        self.assertEqual(SoCBusHandler(standard="axi").addressing, "byte")

    def test_axi_buses_reject_word_addressing(self):
        with _assert_raises_soc_error(self):
            SoCBusHandler(standard="axi-lite", addressing="word")
        with _assert_raises_soc_error(self):
            SoCBusHandler(standard="axi", addressing="word")

    def test_bus_arbiter_transaction_is_wishbone_only(self):
        self.assertEqual(SoCBusHandler(standard="wishbone").arbiter, "default")
        self.assertEqual(
            SoCBusHandler(
                standard = "wishbone",
                arbiter  = "transaction",
            ).arbiter,
            "transaction",
        )
        with _assert_raises_soc_error(self):
            SoCBusHandler(standard="axi-lite", arbiter="transaction")
        with _assert_raises_soc_error(self):
            SoCBusHandler(standard="axi", arbiter="transaction")

    def test_address_width_conversion_between_bus_standards(self):
        wishbone_bus = SoCBusHandler(standard="wishbone", data_width=32, address_width=32)
        wishbone_byte_bus = SoCBusHandler(
            standard      = "wishbone",
            data_width    = 32,
            address_width = 32,
            addressing    = "byte",
        )
        axi_bus      = SoCBusHandler(standard="axi",      data_width=64, address_width=32)

        self.assertEqual(wishbone_bus.get_address_width("wishbone"), 32)
        self.assertEqual(wishbone_bus.get_address_width("axi-lite"), 34)
        self.assertEqual(wishbone_bus.get_address_width("axi"),      34)
        self.assertEqual(wishbone_byte_bus.get_address_width("wishbone"), 30)
        self.assertEqual(wishbone_byte_bus.get_address_width("wishbone", addressing="byte"), 32)
        self.assertEqual(wishbone_byte_bus.get_address_width("axi"), 32)
        self.assertEqual(axi_bus.get_address_width("axi"),           32)
        self.assertEqual(axi_bus.get_address_width("wishbone"),      29)

    def test_regions_are_auto_allocated_after_existing_regions(self):
        bus = SoCBusHandler()

        bus.add_region("boot", SoCRegion(origin=0x0000, size=0x1000))
        bus.add_region("auto", SoCRegion(origin=None,   size=0x1000))

        self.assertEqual(bus.regions["auto"].origin, 0x1000)

    def test_duplicate_region_names_are_rejected(self):
        bus = SoCBusHandler()
        bus.add_region("boot", SoCRegion(origin=0x0000, size=0x1000))

        with _assert_raises_soc_error(self):
            bus.add_region("boot", SoCRegion(origin=0x1000, size=0x1000))

    def test_overlapping_regions_are_rejected(self):
        bus = SoCBusHandler()
        bus.add_region("boot", SoCRegion(origin=0x0000, size=0x1000))

        with _assert_raises_soc_error(self):
            bus.add_region("overlap", SoCRegion(origin=0x0800, size=0x1000))

    def test_failed_overlapping_region_add_does_not_mutate_regions(self):
        bus = SoCBusHandler()
        bus.add_region("boot", SoCRegion(origin=0x0000, size=0x1000))

        with _assert_raises_soc_error(self):
            bus.add_region("overlap", SoCRegion(origin=0x0800, size=0x1000))

        self.assertNotIn("overlap", bus.regions)
        bus.add_region("next", SoCRegion(origin=0x1000, size=0x1000))
        self.assertIn("next", bus.regions)

    def test_io_region_requires_uncached_bus_region(self):
        bus = SoCBusHandler()
        bus.add_region("io", SoCIORegion(origin=0x80000000, size=0x10000))
        bus.add_region("uart", SoCRegion(origin=0x80000000, size=0x100, cached=False))

        with _assert_raises_soc_error(self):
            bus.add_region("cached_uart", SoCRegion(origin=0x80000100, size=0x100, cached=True))

    def test_uncached_region_must_be_inside_io_region(self):
        bus = SoCBusHandler()

        with _assert_raises_soc_error(self):
            bus.add_region("uncached", SoCRegion(origin=0x20000000, size=0x1000, cached=False))

        self.assertNotIn("uncached", bus.regions)

    def test_uncached_region_can_be_auto_allocated_in_io_region(self):
        bus = SoCBusHandler()
        bus.add_region("io", SoCIORegion(origin=0x80000000, size=0x2000))

        bus.add_region("uart", SoCRegion(origin=None, size=0x1000, cached=False))

        self.assertEqual(bus.regions["uart"].origin, 0x80000000)
        self.assertFalse(bus.regions["uart"].cached)

    def test_uncached_auto_allocation_failure_does_not_mutate_regions(self):
        bus = SoCBusHandler()
        bus.add_region("io", SoCIORegion(origin=0x80000000, size=0x1000))

        with _assert_raises_soc_error(self):
            bus.add_region("too_big", SoCRegion(origin=None, size=0x2000, cached=False))

        self.assertNotIn("too_big", bus.regions)

    def test_failed_overlapping_io_region_add_does_not_mutate_io_regions(self):
        bus = SoCBusHandler()
        bus.add_region("io0", SoCIORegion(origin=0x80000000, size=0x10000))

        with _assert_raises_soc_error(self):
            bus.add_region("io1", SoCIORegion(origin=0x80008000, size=0x10000))

        self.assertNotIn("io1", bus.io_regions)
        bus.add_region("io2", SoCIORegion(origin=0x80010000, size=0x10000))
        self.assertIn("io2", bus.io_regions)

    def test_linker_region_overlaps_are_ignored_unless_requested(self):
        bus = SoCBusHandler()
        regions = {
            "boot"   : SoCRegion(origin=0x0000, size=0x1000, linker=True),
            "linker" : SoCRegion(origin=0x0800, size=0x1000),
        }

        self.assertIsNone(bus.check_regions_overlap(regions))
        self.assertEqual(bus.check_regions_overlap(regions, check_linker=True), ("boot", "linker"))

    def test_overlapping_slave_regions_reject_linker_overlay(self):
        bus = SoCBusHandler()
        bus.add_slave("ram", wishbone.Interface(), SoCRegion(
            origin = 0x00000000,
            size   = 0x1000,
        ))

        with _assert_raises_soc_error(self):
            bus.add_slave("alias", wishbone.Interface(), SoCRegion(
                origin = 0x00000000,
                size   = 0x1000,
                linker = True,
            ))

        self.assertNotIn("alias", bus.slaves)
        self.assertNotIn("alias", bus.regions)

    def test_auto_allocation_avoids_existing_linker_regions(self):
        bus = SoCBusHandler()
        bus.add_region("io", SoCIORegion(origin=0x80000000, size=0x10000))
        bus.add_region("ethmac", SoCRegion(origin=None, size=0x2000, cached=False, linker=True))
        bus.add_region("ethmac_rx", SoCRegion(
            origin = 0x80000000,
            size   = 0x1000,
            mode   = "r",
            cached = False,
        ))
        bus.add_region("ethmac_tx", SoCRegion(
            origin = 0x80001000,
            size   = 0x1000,
            cached = False,
        ))
        bus.add_region("ethmac1", SoCRegion(origin=None, size=0x2000, cached=False, linker=True))

        self.assertEqual(bus.regions["ethmac"].origin,  0x80000000)
        self.assertEqual(bus.regions["ethmac1"].origin, 0x80002000)

    def test_region_io_containment_uses_exact_boundaries(self):
        bus       = SoCBusHandler()
        io_region = SoCIORegion(origin=0x80000000, size=0x1000)
        bus.add_region("io", io_region)

        self.assertTrue(bus.check_region_is_io(SoCRegion(origin=0x80000f00, size=0x100, cached=False)))
        self.assertFalse(bus.check_region_is_io(SoCRegion(origin=0x80001000, size=0x100, cached=False)))

    def test_io_containment_accounts_for_rounded_decode_size(self):
        bus = SoCBusHandler()
        bus.add_region("io", SoCIORegion(origin=0x80000000, size=0x1800))

        with _assert_raises_soc_error(self):
            bus.add_region("device", SoCRegion(
                origin = 0x80000000,
                size   = 0x1800,
                cached = False,
            ))

        self.assertNotIn("device", bus.regions)

    def test_io_region_overlap_uses_exact_size(self):
        bus = SoCBusHandler()

        bus.add_region("io",       SoCIORegion(origin=0x1200_0000, size=0x6e00_0000))
        bus.add_region("main_ram", SoCRegion(  origin=0x8000_0000, size=0x2000_0000))

    def test_io_region_can_extend_beyond_bus_address_width(self):
        bus = SoCBusHandler(address_width=32)

        bus.add_region("io", SoCIORegion(origin=0xe000_0000, size=0xff_2000_0000))

        self.assertIn("io", bus.io_regions)

    def test_bus_region_must_fit_bus_address_width(self):
        bus = SoCBusHandler(address_width=32)

        with _assert_raises_soc_error(self):
            bus.add_region("too_high", SoCRegion(origin=0xf000_0000, size=0x2000_0000))

        self.assertNotIn("too_high", bus.regions)

    def test_partial_io_region_overlap_is_rejected(self):
        bus = SoCBusHandler()
        bus.add_region("io", SoCIORegion(origin=0x1200_0000, size=0x7000_0000))

        with _assert_raises_soc_error(self):
            bus.add_region("main_ram", SoCRegion(origin=0x8000_0000, size=0x2000_0000))

    def test_rocket_io_regions_do_not_overlap_main_ram(self):
        from litex.soc.cores.cpu.rocket.core import Rocket

        bus = SoCBusHandler()
        for n, (origin, size) in enumerate(Rocket.io_regions.items()):
            bus.add_region(f"io{n}", SoCIORegion(origin=origin, size=size))

        bus.add_region("clint",   SoCRegion(origin=0x0200_0000, size= 0x1_0000, cached=True, linker=True))
        bus.add_region("plic",    SoCRegion(origin=0x0c00_0000, size=0x40_0000, cached=True, linker=True))
        bus.add_region("rom",     SoCRegion(origin=0x1000_0000, size=0x02_0000, mode="rx"))
        bus.add_region("sram",    SoCRegion(origin=0x1100_0000, size=0x00_2000, mode="rwx"))
        bus.add_region("csr",     SoCRegion(origin=0x1200_0000, size=0x00_1000, cached=False))
        bus.add_region("ethmac",  SoCRegion(origin=0x3000_0000, size=0x00_2000, cached=False))
        bus.add_region("mmio_top", SoCRegion(origin=0x7fff_f000, size=0x00_1000, cached=False))
        bus.add_region("opensbi", SoCRegion(origin=0x8000_0000, size=0x20_0000, cached=True, linker=True))
        bus.add_region("main_ram", SoCRegion(origin=0x8000_0000, size=0x2000_0000, mode="rwx"))

    def test_region_decoder_rejects_misaligned_origin(self):
        bus = SoCBusHandler()

        with _assert_raises_soc_error(self):
            SoCRegion(origin=0x0800, size=0x1000).decoder(bus)

    def test_full_address_region_decoder_always_matches(self):
        bus     = SoCBusHandler()
        decoder = SoCRegion(origin=0x00000000, size=2**bus.address_width).decoder(bus)

        self.assertTrue(decoder(0))
        self.assertTrue(decoder(0xffffffff))

    def test_axi_slave_dst_region_remaps_external_address(self):
        bus       = SoCBusHandler(standard="axi", data_width=32, address_width=32)
        interface = axi.AXIInterface(data_width=32, address_width=32)

        bus.add_slave(
            "ps_io",
            interface,
            SoCRegion(origin=0x6000_0000, size=0x1000),
            dst_region=SoCRegion(origin=0xe000_0000, size=0x1000),
        )

        self.assertIsInstance(bus.slaves["ps_io"], axi.AXIInterface)
        self.assertIsNot(bus.slaves["ps_io"], interface)

        def generator():
            remaps = [
                (0x6000_0000, 0xe000_0000),
                (0x6000_0040, 0xe000_0040),
            ]
            for addr, expected in remaps:
                yield bus.slaves["ps_io"].aw.addr.eq(addr)
                yield bus.slaves["ps_io"].ar.addr.eq(addr)
                yield
                self.assertEqual((yield interface.aw.addr), expected)
                self.assertEqual((yield interface.ar.addr), expected)

        run_simulation(bus, generator())

    def test_slave_dst_region_uses_allocated_source_region(self):
        bus       = SoCBusHandler(standard="axi", data_width=32, address_width=32)
        interface = axi.AXIInterface(data_width=32, address_width=32)

        bus.add_region("boot", SoCRegion(origin=0x0000_0000, size=0x1000))
        bus.add_slave(
            "ps_io",
            interface,
            SoCRegion(origin=None, size=0x1000),
            dst_region=SoCRegion(origin=0xe000_0000, size=0x1000),
        )

        self.assertEqual(bus.regions["ps_io"].origin, 0x0000_1000)

        def generator():
            yield bus.slaves["ps_io"].aw.addr.eq(0x0000_1000)
            yield bus.slaves["ps_io"].ar.addr.eq(0x0000_1040)
            yield
            self.assertEqual((yield interface.aw.addr), 0xe000_0000)
            self.assertEqual((yield interface.ar.addr), 0xe000_0040)

        run_simulation(bus, generator())

    def test_slave_dst_region_rejects_ambiguous_mapping(self):
        bus = SoCBusHandler(standard="axi")

        with _assert_raises_soc_error(self):
            bus.add_slave(
                "ps_io",
                axi.AXIInterface(),
                SoCRegion(origin=0x6000_0000, size=0x1000),
                strip_origin=True,
                dst_region=SoCRegion(origin=0xe000_0000, size=0x1000),
            )

        self.assertNotIn("ps_io", bus.regions)
        self.assertNotIn("ps_io", bus.slaves)

    def test_slave_dst_region_origin_must_be_specified(self):
        bus = SoCBusHandler(standard="axi")

        with _assert_raises_soc_error(self):
            bus.add_slave(
                "ps_io",
                axi.AXIInterface(),
                SoCRegion(origin=0x6000_0000, size=0x1000),
                dst_region=SoCRegion(origin=None, size=0x1000),
            )

        self.assertNotIn("ps_io", bus.regions)
        self.assertNotIn("ps_io", bus.slaves)

    def test_slave_dst_region_must_cover_source_region(self):
        bus = SoCBusHandler(standard="axi")

        with _assert_raises_soc_error(self):
            bus.add_slave(
                "ps_io",
                axi.AXIInterface(),
                SoCRegion(origin=0x6000_0000, size=0x2000),
                dst_region=SoCRegion(origin=0xe000_0000, size=0x1000),
            )

        self.assertNotIn("ps_io", bus.regions)
        self.assertNotIn("ps_io", bus.slaves)


class TestSoCBusStandardIntegration(unittest.TestCase):
    def test_slaves_are_adapted_to_bus_standard(self):
        cases = [
            ("wishbone", axi.AXILiteInterface, wishbone.Interface),
            ("wishbone", axi.AXIInterface,     wishbone.Interface),
            ("axi-lite", wishbone.Interface,   axi.AXILiteInterface),
            ("axi-lite", axi.AXIInterface,     axi.AXILiteInterface),
            ("axi",      wishbone.Interface,   axi.AXIInterface),
            ("axi",      axi.AXILiteInterface, axi.AXIInterface),
        ]

        for bus_standard, source_cls, expected_cls in cases:
            with self.subTest(bus_standard=bus_standard, source_cls=source_cls.__name__):
                bus       = SoCBusHandler(standard=bus_standard)
                interface = _make_bus_interface(source_cls)

                bus.add_slave("slave", interface, SoCRegion(origin=0x00000000, size=0x1000))

                self.assertIsInstance(bus.slaves["slave"], expected_cls)
                self.assertEqual(bus.slaves["slave"].data_width,    bus.data_width)
                self.assertEqual(bus.slaves["slave"].address_width, bus.address_width)

    def test_masters_are_adapted_to_bus_standard(self):
        cases = [
            ("wishbone", axi.AXIInterface,     wishbone.Interface),
            ("axi-lite", wishbone.Interface,   axi.AXILiteInterface),
            ("axi-lite", axi.AXIInterface,     axi.AXILiteInterface),
            ("axi",      axi.AXILiteInterface, axi.AXIInterface),
        ]

        for bus_standard, source_cls, expected_cls in cases:
            with self.subTest(bus_standard=bus_standard, source_cls=source_cls.__name__):
                bus       = SoCBusHandler(standard=bus_standard)
                interface = _make_bus_interface(source_cls)

                bus.add_master("master", interface)

                self.assertIsInstance(bus.masters["master"], expected_cls)
                self.assertEqual(bus.masters["master"].data_width,    bus.data_width)
                self.assertEqual(bus.masters["master"].address_width, bus.address_width)

    def test_native_slave_interface_is_kept(self):
        cases = [
            ("wishbone", wishbone.Interface),
            ("axi-lite", axi.AXILiteInterface),
            ("axi",      axi.AXIInterface),
        ]

        for bus_standard, interface_cls in cases:
            with self.subTest(bus_standard=bus_standard):
                bus       = SoCBusHandler(standard=bus_standard)
                interface = _make_bus_interface(interface_cls)

                bus.add_slave("slave", interface, SoCRegion(origin=0x00000000, size=0x1000))

                self.assertIs(bus.slaves["slave"], interface)

    def test_slave_data_width_is_converted_to_bus_width(self):
        bus       = SoCBusHandler(standard="wishbone", data_width=64)
        interface = wishbone.Interface(data_width=32, address_width=32)

        bus.add_slave("slave", interface, SoCRegion(origin=0x00000000, size=0x1000))

        self.assertIsInstance(bus.slaves["slave"], wishbone.Interface)
        self.assertEqual(bus.slaves["slave"].data_width, 64)

    def test_wishbone_slave_can_be_clock_domain_crossed(self):
        bus       = SoCBusHandler(standard="wishbone")
        interface = wishbone.Interface()

        bus.add_slave(
            "slave",
            interface,
            SoCRegion(origin=0x00000000, size=0x1000),
            clock_domain="periph",
        )

        self.assertIsInstance(bus.slaves["slave"], wishbone.Interface)
        self.assertIsNot(bus.slaves["slave"], interface)

    def test_axi_lite_slave_can_be_clock_domain_crossed(self):
        bus       = SoCBusHandler(standard="axi-lite")
        interface = axi.AXILiteInterface(clock_domain="periph")

        bus.add_slave(
            "slave",
            interface,
            SoCRegion(origin=0x00000000, size=0x1000),
            clock_domain="periph",
        )

        self.assertIsInstance(bus.slaves["slave"], axi.AXILiteInterface)
        self.assertIsNot(bus.slaves["slave"], interface)
        self.assertEqual(bus.slaves["slave"].clock_domain, "sys")

    def test_axi_slave_can_be_clock_domain_crossed(self):
        bus       = SoCBusHandler(standard="axi")
        interface = axi.AXIInterface(clock_domain="periph")

        bus.add_slave(
            "slave",
            interface,
            SoCRegion(origin=0x00000000, size=0x1000),
            clock_domain="periph",
        )

        self.assertIsInstance(bus.slaves["slave"], axi.AXIInterface)
        self.assertIsNot(bus.slaves["slave"], interface)
        self.assertEqual(bus.slaves["slave"].clock_domain, "sys")

    def test_narrow_axi_lite_slave_with_strip_origin_adapts_to_wishbone_bus(self):
        bus       = SoCBusHandler(standard="wishbone", data_width=32, address_width=32)
        interface = axi.AXILiteInterface(data_width=32, address_width=28)

        bus.add_slave(
            "slave",
            interface,
            SoCRegion(origin=0x4000_0000, size=0x1000_0000),
            strip_origin=True,
        )

        self.assertIsInstance(bus.slaves["slave"], wishbone.Interface)
        self.assertEqual(bus.slaves["slave"].address_width, bus.address_width)

    def test_axi_slave_adaptation_uses_existing_master_id_width(self):
        bus = SoCBusHandler(standard="axi")
        bus.add_master("cpu", axi.AXIInterface(id_width=4))

        bus.add_slave("wb", wishbone.Interface(), SoCRegion(origin=0x00000000, size=0x1000))

        self.assertIsInstance(bus.slaves["wb"], axi.AXIInterface)
        self.assertEqual(bus.slaves["wb"].id_width, 4)

    def test_bus_standard_kwargs_follow_soc_bus(self):
        self.assertEqual(
            SoCBusHandler(standard="wishbone").get_bus_standard_kwargs(),
            {"bus_standard": "wishbone"})
        self.assertEqual(
            SoCBusHandler(standard="axi-lite").get_bus_standard_kwargs(with_axi_id_width=True),
            {"bus_standard": "axi-lite"})

        bus = SoCBusHandler(standard="axi")
        bus.add_master("cpu", axi.AXIInterface(id_width=4))

        self.assertEqual(bus.get_axi_id_width(), 4)
        self.assertEqual(
            bus.get_bus_standard_kwargs(with_axi_id_width=True),
            {"bus_standard": "axi", "axi_id_width": 4})

    def test_axi_id_width_mismatch_on_new_master_rolls_back_master(self):
        bus = SoCBusHandler(standard="axi")
        bus.add_slave("ram", axi.AXIInterface(id_width=1), SoCRegion(origin=0x00000000, size=0x1000))

        with _assert_raises_soc_error(self):
            bus.add_master("cpu", axi.AXIInterface(id_width=4))

        self.assertNotIn("cpu", bus.masters)

    def test_axi_id_width_mismatch_on_new_slave_rolls_back_slave_and_region(self):
        bus = SoCBusHandler(standard="axi")
        bus.add_master("cpu", axi.AXIInterface(id_width=4))

        with _assert_raises_soc_error(self):
            bus.add_slave("ram", axi.AXIInterface(id_width=1), SoCRegion(origin=0x00000000, size=0x1000))

        self.assertNotIn("ram", bus.slaves)
        self.assertNotIn("ram", bus.regions)

    def test_invalid_adapter_direction_is_rejected(self):
        bus = SoCBusHandler()

        with self.assertRaisesRegex(ValueError, "direction must be"):
            bus.add_adapter("bad", wishbone.Interface(), direction="sideways")

    def test_auto_named_masters_and_slaves_are_stable(self):
        bus = SoCBusHandler()

        bus.add_master(master=wishbone.Interface())
        bus.add_master(master=wishbone.Interface())
        bus.add_slave(slave=wishbone.Interface(), region=SoCRegion(origin=0x00000000, size=0x1000))
        bus.add_slave(slave=wishbone.Interface(), region=SoCRegion(origin=0x00001000, size=0x1000))

        self.assertEqual(list(bus.masters.keys()), ["master0", "master1"])
        self.assertEqual(list(bus.slaves.keys()),  ["slave0",  "slave1"])

    def test_partial_zero_origin_region_keeps_address_decoder(self):
        bus    = SoCBusHandler(timeout=8)
        master = wishbone.Interface()
        slave  = wishbone.Interface()
        bus.add_master("master", master)
        bus.add_slave("slave", slave, SoCRegion(origin=0x00000000, size=0x1000))
        bus.finalize()

        def generator():
            yield master.adr.eq(0x1000 // 4)
            yield master.cyc.eq(1)
            yield master.stb.eq(1)
            yield
            self.assertEqual((yield slave.cyc), 0)

        run_simulation(bus, generator())

    def test_full_address_region_keeps_configured_timeout(self):
        bus = SoCBusHandler(timeout=8)
        bus.add_master("master", wishbone.Interface())
        bus.add_slave("slave", wishbone.Interface(), SoCRegion(
            origin = 0x00000000,
            size   = 2**bus.address_width,
        ))

        bus.finalize()

        self.assertTrue(hasattr(bus._interconnect, "timeout"))

    def test_slave_can_use_predeclared_region(self):
        bus = SoCBusHandler()
        bus.add_region("ram", SoCRegion(origin=0x00000000, size=0x1000))

        bus.add_slave("ram", wishbone.Interface())

        self.assertIn("ram", bus.slaves)
        self.assertEqual(bus.regions["ram"].origin, 0x00000000)

    def test_slave_requires_name_or_region(self):
        bus = SoCBusHandler()

        with _assert_raises_soc_error(self):
            bus.add_slave(slave=wishbone.Interface())
        with _assert_raises_soc_error(self):
            bus.add_slave("missing", wishbone.Interface())

    def test_duplicate_master_does_not_replace_existing_master(self):
        bus    = SoCBusHandler()
        master = wishbone.Interface()
        bus.add_master("cpu", master)

        with _assert_raises_soc_error(self):
            bus.add_master("cpu", wishbone.Interface())

        self.assertIs(bus.masters["cpu"], master)

    def test_duplicate_slave_does_not_add_new_region(self):
        bus   = SoCBusHandler()
        slave = wishbone.Interface()
        bus.add_slave("ram", slave, SoCRegion(origin=0x00000000, size=0x1000))

        with _assert_raises_soc_error(self):
            bus.add_slave("ram", wishbone.Interface(), SoCRegion(origin=0x00001000, size=0x1000))

        self.assertIs(bus.slaves["ram"], slave)
        self.assertEqual(list(bus.regions.keys()), ["ram"])
        self.assertEqual(bus.regions["ram"].origin, 0x00000000)

    def test_byte_addressed_master_warns_on_word_addressed_bus(self):
        bus    = SoCBusHandler(standard="wishbone", addressing="word")
        master = wishbone.Interface(addressing="byte")

        with self.assertLogs("SoCBusHandler", level="WARNING") as logs:
            bus.add_master("csr_dma", master)

        self.assertIn("full byte addresses in the SoC memory map", "\n".join(logs.output))


class TestSoCCSRHandler(unittest.TestCase):
    def test_invalid_csr_handler_parameters_are_rejected(self):
        for kwargs in [
            {"data_width": 16},
            {"address_width": 13},
            {"alignment": 16},
            {"paging": 0x200},
            {"ordering": "middle"},
        ]:
            with self.subTest(kwargs=kwargs):
                with _assert_raises_soc_error(self):
                    SoCCSRHandler(**kwargs)

    def test_address_map_allocates_and_reuses_locations(self):
        csr = SoCCSRHandler(reserved_csrs={"ctrl": 0})

        self.assertEqual(csr.address_map("timer0"), 1)
        self.assertEqual(csr.address_map("timer0"), 1)
        self.assertEqual(csr.address_map("timer0", origin=True), csr.paging)

    def test_address_map_uses_memory_name_override(self):
        csr    = SoCCSRHandler()
        memory = SimpleNamespace(name_override="buffer")

        loc = csr.address_map("dma", memory=memory)

        self.assertEqual(csr.locs["dma_buffer"], loc)

    def test_csr_region_must_be_paging_aligned(self):
        csr = SoCCSRHandler()
        csr.add_region("timer0", SoCCSRRegion(origin=csr.paging, busword=32, obj=object()))

        self.assertIn("timer0", csr.regions)
        with _assert_raises_soc_error(self):
            csr.add_region("misaligned", SoCCSRRegion(origin=csr.paging + 4, busword=32, obj=object()))

    def test_csr_region_duplicate_is_rejected_without_replacing_region(self):
        csr    = SoCCSRHandler()
        region = SoCCSRRegion(origin=csr.paging, busword=32, obj=object())
        csr.add_region("timer0", region)

        with _assert_raises_soc_error(self):
            csr.add_region("timer0", SoCCSRRegion(origin=2*csr.paging, busword=32, obj=object()))

        self.assertIs(csr.regions["timer0"], region)

    def test_csr_master_checks_data_width_and_duplicates(self):
        csr    = SoCCSRHandler(data_width=32)
        master = SimpleNamespace(data_width=32)
        csr.add_master("main", master)

        self.assertIs(csr.masters["main"], master)
        with _assert_raises_soc_error(self):
            csr.add_master("main", SimpleNamespace(data_width=32))
        with _assert_raises_soc_error(self):
            csr.add_master("wide", SimpleNamespace(data_width=8))

    def test_csr_location_exhaustion_does_not_mutate_locs(self):
        csr = SoCCSRHandler(address_width=14, paging=0x4000)

        for n in range(csr.n_locs):
            csr.add(f"csr{n}")

        with _assert_raises_soc_error(self):
            csr.add("overflow")

        self.assertNotIn("overflow", csr.locs)


class TestSoCIRQHandler(unittest.TestCase):
    def test_irq_handler_rejects_invalid_irq_counts(self):
        for n_irqs in [-1, 1.5, True]:
            with self.subTest(n_irqs=n_irqs):
                with _assert_raises_soc_error(self):
                    SoCIRQHandler(n_irqs=n_irqs)

        self.assertEqual(SoCIRQHandler(n_irqs=0).n_locs, 0)

    def test_irq_handler_requires_enable_before_add(self):
        irq = SoCIRQHandler(n_irqs=4)

        with _assert_raises_soc_error(self):
            irq.add("timer0")

        irq.enable()
        irq.add("timer0")
        irq.add("uart", 3)

        self.assertEqual(irq.locs, {"timer0": 0, "uart": 3})

    def test_irq_handler_rejects_duplicate_and_out_of_range_locations(self):
        irq = SoCIRQHandler(n_irqs=2)
        irq.enable()
        irq.add("timer0", 0)

        with _assert_raises_soc_error(self):
            irq.add("uart", 0)
        with _assert_raises_soc_error(self):
            irq.add("ethmac", 2)

    def test_irq_auto_allocation_exhaustion_does_not_mutate_locs(self):
        irq = SoCIRQHandler(n_irqs=1)
        irq.enable()
        irq.add("timer0")

        with _assert_raises_soc_error(self):
            irq.add("uart")

        self.assertNotIn("uart", irq.locs)


class TestSoC(unittest.TestCase):
    def test_build_time_honors_source_date_epoch(self):
        source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "0"
        try:
            self.assertEqual(build_time(),                "1970-01-01 00:00:00")
            self.assertEqual(build_time(with_time=False), "1970-01-01")
        finally:
            if source_date_epoch is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = source_date_epoch

    def test_soc_error_does_not_replace_stderr(self):
        stderr = sys.stderr

        with self.assertRaises(SoCError):
            raise SoCError()

        self.assertIs(sys.stderr, stderr)

    def test_soc_initializes_platform_and_clock_constants(self):
        platform = _FakePlatform()
        soc      = SoC(platform, sys_clk_freq=100e6)

        self.assertIs(soc.platform, platform)
        self.assertEqual(soc.sys_clk_freq, 100000000)
        self.assertEqual(soc.constants["CONFIG_PLATFORM_NAME"], "unit")
        self.assertEqual(soc.constants["CONFIG_CLOCK_FREQUENCY"], 100000000)

    def test_constants_are_uppercase_and_duplicates_can_be_overridden(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)

        soc.add_constant("foo", 1)
        soc.add_constant("foo", 2, check_duplicate=False)

        self.assertEqual(soc.constants["FOO"], 2)

    def test_duplicate_constants_are_rejected_by_default(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)

        soc.add_constant("foo", 1)
        with _assert_raises_soc_error(self):
            soc.add_constant("foo", 2)

    def test_config_names_are_prefixed(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)

        soc.add_config("FEATURE", 1)

        self.assertEqual(soc.constants["CONFIG_FEATURE"], 1)

    def test_add_hyperram_maps_region_and_uses_soc_bus_standard(self):
        cases = [
            ("wishbone", wishbone.Interface),
            ("axi-lite", axi.AXILiteInterface),
            ("axi",      axi.AXIInterface),
        ]

        for bus_standard, interface_cls in cases:
            with self.subTest(bus_standard=bus_standard):
                soc = SoC(_FakePlatform(), sys_clk_freq=100e6, bus_standard=bus_standard)
                if bus_standard == "axi":
                    soc.bus.add_master("cpu", axi.AXIInterface(id_width=4))

                hyperram = soc.add_hyperram(
                    pads        = _HyperRamPads(),
                    region_name = "main_ram",
                    origin      = 0x4000_0000,
                    size        = 0x1000,
                    with_csr    = False,
                )

                self.assertIsInstance(hyperram, HyperRAM)
                self.assertIs(soc.hyperram, hyperram)
                self.assertIsInstance(hyperram.bus, interface_cls)
                self.assertIs(soc.bus.slaves["main_ram"], hyperram.bus)
                self.assertEqual(soc.bus.regions["main_ram"].origin, 0x4000_0000)
                if bus_standard == "axi":
                    self.assertEqual(hyperram.bus.id_width, 4)

    def test_add_hyperram_uses_mem_map_origin(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=100e6)
        soc.mem_map["hyperram"] = 0x2000_0000

        soc.add_hyperram(pads=_HyperRamPads(), size=0x1000, with_csr=False)

        self.assertEqual(soc.bus.regions["hyperram"].origin, 0x2000_0000)

    def test_add_hyperram_requests_platform_pads(self):
        platform = _FakePlatform()
        platform.requests[("hyperram", 1)] = _HyperRamPads()
        soc = SoC(platform, sys_clk_freq=100e6)

        soc.add_hyperram(number=1, size=0x1000, with_csr=False)

        self.assertEqual(platform.request_calls, [("hyperram", 1, False)])

    def test_add_hyperram_rejects_derived_kwargs(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=100e6)

        with _assert_raises_soc_error(self):
            soc.add_hyperram(pads=_HyperRamPads(), size=0x1000, bus_standard="wishbone")
        with _assert_raises_soc_error(self):
            soc.add_hyperram(pads=_HyperRamPads(), size=0x1000, axi_id_width=1)
        with _assert_raises_soc_error(self):
            soc.add_hyperram(pads=_HyperRamPads(), size=0x1000, sys_clk_freq=100e6)

    def test_add_hyperram_requires_size(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=100e6)

        with _assert_raises_soc_error(self):
            soc.add_hyperram(pads=_HyperRamPads())

    def test_add_uart_keeps_soc_level_integration(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        soc.add_uart(uart_name="stub")

        self.assertTrue(hasattr(soc, "uart"))
        self.assertIn("UART_POLLING", soc.constants)

    def test_get_csr_address_returns_main_bus_address(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.mem_map["csr"] = 0xf0000000

        self.assertEqual(soc.csr.address_map("timer0", origin=True), 0)
        self.assertEqual(soc.get_csr_address("timer0"), soc.mem_map["csr"])

    def test_csr_bridge_defaults_to_decoded_region_without_cpu(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.bus.add_region("io", SoCIORegion(origin=0x00000000, size=2**soc.bus.address_width))

        soc.add_csr_bridge(origin=0x00000000)

        self.assertTrue(soc.bus.regions["csr"].decode)
        self.assertIn("csr", soc.bus.slaves)
        self.assertIn("csr", soc.csr.masters)

    def test_finalize_bus_requires_csr_origin(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc._finalize_bus()

    def test_mem_map_is_instance_local(self):
        soc0 = SoC(_FakePlatform(), sys_clk_freq=1e6)
        soc1 = SoC(_FakePlatform(), sys_clk_freq=1e6)

        soc0.mem_map["scratch"] = 0x20000000

        self.assertNotIn("scratch", soc1.mem_map)
        self.assertNotIn("scratch", SoC.mem_map)

    def test_soc_core_rejects_missing_integrated_memory_origin(self):
        soc = SoCCore.__new__(SoCCore)
        soc.logger = logging.getLogger("SoC")
        soc.mem_map = {"main_ram": 0x40000000}

        self.assertEqual(soc._get_mem_map_origin("main_ram"), 0x40000000)

        with _assert_raises_soc_error(self):
            soc._get_mem_map_origin("sram")

    def test_soc_core_rejects_cfu_without_cpu(self):
        with _assert_raises_soc_error(self):
            SoCCore(_FakePlatform(), clk_freq=1e6, cpu_type="None", cpu_cfu="cfu.v")

    def test_soc_core_rejects_cfu_without_cfu_variant(self):
        with _assert_raises_soc_error(self):
            SoCCore(_FakePlatform(), clk_freq=1e6, cpu_type="vexriscv", cpu_cfu="cfu.v")

    def test_soc_core_rom_init_keeps_requested_size(self):
        with tempfile.NamedTemporaryFile() as init_file:
            init_file.write(b"\x01\x02\x03\x04")
            init_file.flush()

            soc = SoCCore(_FakePlatform(),
                clk_freq            = 1e6,
                cpu_type            = "vexriscv",
                integrated_rom_size = 0x20000,
                integrated_rom_init = init_file.name,
                uart_name           = "stub",
                with_ctrl           = False)

        self.assertEqual(soc.integrated_rom_size, 0x20000)
        self.assertEqual(soc.bus.regions["rom"].size, 0x20000)
        self.assertTrue(soc.integrated_rom_initialized)

    def test_init_ram_rejects_unknown_name(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.init_ram("missing", contents=[0])

    def test_bios_requirements_check_required_csr_and_regions(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.check_bios_requirements()

        soc.csr.locs["timer0"] = 0
        with _assert_raises_soc_error(self):
            soc.check_bios_requirements()

        soc.bus.add_region("rom",  SoCRegion(origin=0x00000000, size=0x1000, mode="rx"))
        soc.bus.add_region("sram", SoCRegion(origin=0x10000000, size=0x1000))
        soc.check_bios_requirements()

    def test_finalize_skips_cpu_reset_check_without_reset_address(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.cpu = SimpleNamespace()

        soc._finalize_cpu_reset_address()

        self.assertFalse(hasattr(soc.cpu, "reset_address"))

    def test_finalize_irq_accepts_direct_irq_signal(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.cpu = SimpleNamespace(interrupt=Signal(4), interrupts={})
        soc.raw = SimpleNamespace(irq=Signal())
        soc.irq.enable()
        soc.irq.add("raw", 2)

        soc._finalize_irq()

        self.assertEqual(soc.constants["CONFIG_CPU_INTERRUPTS"], 3)
        self.assertEqual(soc.constants["RAW_INTERRUPT"], 2)

    def test_finalize_irq_warns_on_unresolved_source(self):
        soc = SoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.cpu = SimpleNamespace(interrupt=Signal(4), interrupts={})
        soc.irq.enable()
        soc.irq.add("missing", 1)

        with self.assertLogs("SoC", level="WARNING") as log:
            soc._finalize_irq()

        messages = "\n".join(log.output)
        self.assertIn("missing", messages)
        self.assertIn("unconnected", messages)
        self.assertEqual(soc.constants["MISSING_INTERRUPT"], 1)

    def test_build_uses_platform_name_and_sanitizes_numeric_build_name(self):
        platform = _FakePlatform()
        soc      = SoC(platform, sys_clk_freq=1e6)

        self.assertEqual(soc.get_build_name(), "unit")
        self.assertEqual(soc.build(build_name="1top", run=False), "built")

        self.assertEqual(soc.get_build_name(), "_1top")
        _, _, kwargs = platform.build_calls[0]
        self.assertEqual(kwargs["build_name"], "_1top")
        self.assertFalse(kwargs["run"])

    def test_pcie_uses_local_endpoint_for_renamed_instances(self):
        source = inspect.getsource(LiteXSoC.add_pcie)

        self.assertIn("LitePCIeWishboneMaster(endpoint,", source)
        self.assertIn("LitePCIeMSIX(endpoint=endpoint,", source)
        self.assertNotIn("self.pcie_endpoint", source)

    def test_pcie_requires_csr_origin_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_pcie()

    def test_pcie_dma_depth_helper_reports_missing_entries(self):
        source = inspect.getsource(LiteXSoC.add_pcie)

        self.assertIn("missing entry for DMA", source)
        self.assertIn("raise SoCError() from e", source)
        self.assertIn('_pcie_dma_depth("dma_buffering_depths"', source)
        self.assertIn('_pcie_dma_depth("dma_writer_buffering_depths"', source)
        self.assertIn('_pcie_dma_depth("dma_reader_buffering_depths"', source)

    def test_ethernet_timestamp_requires_timer0(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_ethernet(with_timestamp=True)

    def test_ethernet_requires_phy_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_ethernet()

    def test_ethernet_dhcp_enables_dynamic_ip_and_udp_broadcast(self):
        source = inspect.getsource(LiteXSoC.add_ethernet)

        self.assertIn("with_dhcp=False", source)
        self.assertIn("dynamic_ip = True", source)
        self.assertIn('self.add_constant("ETH_DYNAMIC_IP")', source)
        self.assertIn('self.add_constant("ETH_UDP_BROADCAST")', source)
        self.assertIn('self.add_constant("ETH_WITH_DHCP")', source)

    def test_etherbone_requires_phy_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_etherbone()

    def test_spi_flash_rejects_invalid_clock_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_spi_flash(clk_freq=0)

    def test_spi_flash_requires_module_without_custom_phy(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_spi_flash()

    def test_spi_flash_exports_erase_geometry(self):
        from litespi.ids import SpiNorFlashManufacturerIDs
        from litespi.opcodes import SpiNorFlashOpCodes as Codes
        from litespi.phy.model import LiteSPIPHYModel
        from litespi.spi_nor_flash_module import SpiNorFlashModule

        class EraseGeometryModule(SpiNorFlashModule):
            manufacturer_id = SpiNorFlashManufacturerIDs.NONJEDEC
            device_id       = 0x1234
            name            = "erase-geometry"
            total_size      = 256
            page_size       = 256
            total_pages     = 1
            supported_opcodes = [Codes.READ_1_1_1, Codes.PP_1_1_1]
            dummy_bits = 0

        module = EraseGeometryModule(Codes.READ_1_1_1)
        # Set the attributes directly to keep this test compatible with LiteSPI releases that
        # predate erase descriptors while exercising LiteX's constant generation.
        module.erase_opcode    = Codes.BE_4K_4B
        module.erase_size      = 4 * 1024
        module.erase_addr_bits = 32
        phy = LiteSPIPHYModel(module, init=[0])
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.cpu = SimpleNamespace(endianness="little")
        soc.add_spi_flash(mode="1x", module=module, phy=phy, with_master=True)

        self.assertEqual(soc.constants["SPIFLASH_MODULE_ERASE_OPCODE"], Codes.BE_4K_4B.code)
        self.assertEqual(soc.constants["SPIFLASH_MODULE_ERASE_SIZE"], 4 * 1024)
        self.assertEqual(soc.constants["SPIFLASH_MODULE_ERASE_ADDR_BITS"], 32)

    def test_spi_ram_requires_module(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_spi_ram()

    def test_video_terminal_requires_uart(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_video_terminal()

    def test_video_terminal_rejects_bad_timing_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)
        soc.uart = SimpleNamespace()

        with _assert_raises_soc_error(self):
            soc.add_video_terminal(timings="800@60Hz")

    def test_video_framebuffer_requires_phy(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_video_framebuffer()

    def test_video_framebuffer_rejects_bad_timing_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_video_framebuffer(
                phy     = stream.Endpoint(video_data_layout),
                timings = "800@60Hz",
            )

    def test_sata_requires_phy_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_sata()

    def test_sata_rejects_unknown_phy_generation_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_sata(phy=SimpleNamespace(gen="gen4"))

    def test_uartbone_rejects_invalid_clock_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_uartbone(clk_freq=0)

    def test_uartbone_rejects_invalid_baudrate_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_uartbone(baudrate=0)

    def test_spi_master_rejects_invalid_clock_before_core_creation(self):
        for spi_clk_freq in [0, -1]:
            with self.subTest(spi_clk_freq=spi_clk_freq):
                soc  = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)
                pads = Record([("clk", 1), ("cs_n", 1), ("mosi", 1), ("miso", 1)])

                with _assert_raises_soc_error(self):
                    soc.add_spi_master(pads=pads, spi_clk_freq=spi_clk_freq)

                self.assertFalse(hasattr(soc, "spimaster"))

    def test_spi_sdcard_rejects_invalid_clock_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_spi_sdcard(spi_clk_freq=0)

    def test_sdcard_rejects_invalid_mode_before_imports(self):
        soc = LiteXSoC(_FakePlatform(), sys_clk_freq=1e6)

        with _assert_raises_soc_error(self):
            soc.add_sdcard(mode="erase")


if __name__ == "__main__":
    unittest.main()
