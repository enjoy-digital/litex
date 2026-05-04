#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import sys
import unittest
from contextlib import contextmanager
from types import SimpleNamespace

from litex.soc.interconnect import axi, wishbone

from litex.soc.integration.soc import (
    SoC,
    SoCBusHandler,
    SoCCSRHandler,
    SoCCSRRegion,
    SoCError,
    SoCIORegion,
    SoCIRQHandler,
    SoCRegion,
    add_ip_address_constants,
    add_mac_address_constants,
)


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

    def build(self, soc, *args, **kwargs):
        self.build_calls.append((soc, args, kwargs))
        return "built"


def _make_bus_interface(interface_cls, data_width=32, address_width=32):
    return interface_cls(data_width=data_width, address_width=address_width)


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
        with self.assertRaisesRegex(ValueError, "48 bits"):
            add_mac_address_constants(_ConstantCollector(), "MAC", 2**48)


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
        with self.assertRaisesRegex(ValueError, "integer"):
            SoCRegion(origin=0, size="0x1000")
        with self.assertRaisesRegex(ValueError, "positive"):
            SoCRegion(origin=0, size=0)


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

    def test_address_width_conversion_between_bus_standards(self):
        wishbone_bus = SoCBusHandler(standard="wishbone", data_width=32, address_width=32)
        axi_bus      = SoCBusHandler(standard="axi",      data_width=64, address_width=32)

        self.assertEqual(wishbone_bus.get_address_width("wishbone"), 32)
        self.assertEqual(wishbone_bus.get_address_width("axi-lite"), 34)
        self.assertEqual(wishbone_bus.get_address_width("axi"),      34)
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

    def test_region_io_containment_uses_exact_boundaries(self):
        bus       = SoCBusHandler()
        io_region = SoCIORegion(origin=0x80000000, size=0x1000)
        bus.add_region("io", io_region)

        self.assertTrue(bus.check_region_is_io(SoCRegion(origin=0x80000f00, size=0x100, cached=False)))
        self.assertFalse(bus.check_region_is_io(SoCRegion(origin=0x80001000, size=0x100, cached=False)))

    def test_region_decoder_rejects_misaligned_origin(self):
        bus = SoCBusHandler()

        with _assert_raises_soc_error(self):
            SoCRegion(origin=0x0800, size=0x1000).decoder(bus)

    def test_full_address_region_decoder_always_matches(self):
        bus     = SoCBusHandler()
        decoder = SoCRegion(origin=0x00000000, size=2**bus.address_width).decoder(bus)

        self.assertTrue(decoder(0))
        self.assertTrue(decoder(0xffffffff))


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

    def test_axi_slave_adaptation_uses_existing_master_id_width(self):
        bus = SoCBusHandler(standard="axi")
        bus.add_master("cpu", axi.AXIInterface(id_width=4))

        bus.add_slave("wb", wishbone.Interface(), SoCRegion(origin=0x00000000, size=0x1000))

        self.assertIsInstance(bus.slaves["wb"], axi.AXIInterface)
        self.assertEqual(bus.slaves["wb"].id_width, 4)

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

    def test_build_uses_platform_name_and_sanitizes_numeric_build_name(self):
        platform = _FakePlatform()
        soc      = SoC(platform, sys_clk_freq=1e6)

        self.assertEqual(soc.get_build_name(), "unit")
        self.assertEqual(soc.build(build_name="1top", run=False), "built")

        self.assertEqual(soc.get_build_name(), "_1top")
        _, _, kwargs = platform.build_calls[0]
        self.assertEqual(kwargs["build_name"], "_1top")
        self.assertFalse(kwargs["run"])


if __name__ == "__main__":
    unittest.main()
