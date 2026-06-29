#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace

from litex.soc.integration.export import (
    get_csr_header,
    get_csr_svd,
    get_linker_regions,
    get_mem_header,
    get_soc_header,
)
from litex.soc.integration.soc import SoCCSRRegion, SoCRegion
from litex.soc.interconnect.csr import CSRField, CSRStatus, CSRStorage


def _get_csr_header(csr):
    return get_csr_header(
        regions = {
            "ctrl": SoCCSRRegion(origin=0xf0000000, busword=32, obj=[csr]),
        },
        constants                    = {},
        csr_base                     = 0xf0000000,
        with_fields_access_functions = True,
    )


def _get_csr_svd(csr, ordering="big"):
    csr.finalize(32, ordering)
    soc = SimpleNamespace(
        irq = SimpleNamespace(locs={}),
        csr = SimpleNamespace(
            data_width = 32,
            ordering   = ordering,
            regions    = {
                "ctrl": SoCCSRRegion(origin=0xf0000000, busword=32, obj=[csr]),
            },
        ),
        mem_regions = {},
        constants   = {},
    )
    return get_csr_svd(soc, description="test")


def _get_svd_registers(svd):
    registers = {}
    root = ET.fromstring(svd)
    for register in root.findall("./peripherals/peripheral/registers/register"):
        fields = {}
        for field in register.findall("./fields/field"):
            fields[field.findtext("name")] = {
                "msb":      field.findtext("msb"),
                "lsb":      field.findtext("lsb"),
                "bitRange": field.findtext("bitRange"),
            }
        registers[register.findtext("name")] = fields
    return registers


class TestCSRExport(unittest.TestCase):
    def test_soc_header_formats_int_constants(self):
        header = get_soc_header({
            "CONFIG_SMALL":           42,
            "CONFIG_CLOCK_FREQUENCY": 100000000,
            "CONFIG_RESET_ADDR":      0x80000000,
            "CONFIG_MASK":            0xffff,
            "CONFIG_64BIT":           0x100000000,
            "CONFIG_NEGATIVE_64BIT": -0x80000001,
        })

        self.assertIn("#define CONFIG_SMALL 42\n", header)
        self.assertIn("#define CONFIG_CLOCK_FREQUENCY 100000000\n", header)
        self.assertIn("#define CONFIG_RESET_ADDR 0x80000000\n", header)
        self.assertIn("#define CONFIG_MASK 0xffff\n", header)
        self.assertIn("#define CONFIG_64BIT 0x100000000ULL\n", header)
        self.assertIn("#define CONFIG_NEGATIVE_64BIT -0x80000001LL\n", header)
        self.assertIn("static inline uint64_t config_64bit_read(void)", header)
        self.assertIn("static inline int64_t config_negative_64bit_read(void)", header)

    def test_csr_field_accessors_use_uint64_for_wide_csr(self):
        csr = CSRStorage(name="wide", fields=[
            CSRField("low",  size=32, offset=0),
            CSRField("high", size=32, offset=32),
        ])

        header = _get_csr_header(csr)

        self.assertIn("static inline uint64_t ctrl_wide_high_extract(uint64_t oldword)", header)
        self.assertIn("uint64_t word = ctrl_wide_read();", header)
        self.assertIn("static inline uint64_t ctrl_wide_high_replace(uint64_t oldword, uint64_t plain_value)", header)
        self.assertIn("uint64_t oldword = ctrl_wide_read();", header)
        self.assertIn("uint64_t newword = ctrl_wide_high_replace(oldword, plain_value);", header)
        self.assertNotIn("static inline uint32_t ctrl_wide_high_extract(uint32_t oldword)", header)

    def test_csr_field_accessors_keep_uint32_for_32_bit_csr(self):
        csr = CSRStorage(name="narrow", fields=[
            CSRField("field", size=8, offset=8),
        ])

        header = _get_csr_header(csr)

        self.assertIn("static inline uint32_t ctrl_narrow_field_extract(uint32_t oldword)", header)
        self.assertIn("uint32_t word = ctrl_narrow_read();", header)
        self.assertIn("static inline void ctrl_narrow_field_write(uint32_t plain_value)", header)

    def test_csr_field_accessors_skip_csr_wider_than_uint64(self):
        csr = CSRStorage(name="too_wide", fields=[
            CSRField("field", size=8, offset=64),
        ])

        header = _get_csr_header(csr)

        self.assertNotIn("ctrl_too_wide_field_extract", header)
        self.assertNotIn("ctrl_too_wide_field_read", header)

    def test_cpu_bios_map_exports_virtual_memory_aliases(self):
        cpu = SimpleNamespace(
            bios_map = lambda addr, cached: addr + (0x80000000 if cached else 0xa0000000),
        )
        regions = {
            "main_ram": SoCRegion(origin=0x00000000, size=0x1000, cached=True),
            "csr":      SoCRegion(origin=0x18000000, size=0x1000, cached=False),
        }

        linker = get_linker_regions(regions, cpu=cpu)
        header = get_mem_header(regions, cpu=cpu)

        self.assertIn("main_ram : ORIGIN = 0x80000000", linker)
        self.assertIn("csr : ORIGIN = 0xb8000000", linker)
        self.assertIn("#define MAIN_RAM_BASE 0x00000000L", header)
        self.assertIn("#define MAIN_RAM_BASE_VA 0x80000000L", header)
        self.assertIn("#define CSR_BASE 0x18000000L", header)
        self.assertIn("#define CSR_BASE_VA 0xb8000000L", header)

    def test_cpu_bios_map_exports_virtual_csr_accessors(self):
        cpu = SimpleNamespace(
            bios_map = lambda addr, cached: addr + (0x80000000 if cached else 0xa0000000),
        )
        csr = CSRStatus(name="scratch", size=32)
        header = get_csr_header(
            regions = {
                "ctrl": SoCCSRRegion(origin=0x18000000, busword=32, obj=[csr]),
            },
            constants = {},
            csr_base  = 0x18000000,
            cpu       = cpu,
        )

        self.assertIn("#define CSR_BASE 0x18000000L", header)
        self.assertIn("#define CSR_BASE_VA 0xb8000000L", header)
        self.assertIn("#define CSR_CTRL_BASE (CSR_BASE + 0x0L)", header)
        self.assertIn("#define CSR_CTRL_BASE_VA (CSR_BASE_VA + 0x0L)", header)
        self.assertIn("return csr_read_simple((CSR_BASE_VA + 0x0L));", header)

    def test_csr_header_omits_virtual_aliases_for_identity_map(self):
        cpu = SimpleNamespace(
            bios_map = lambda addr, cached: addr,
        )
        csr = CSRStatus(name="scratch", size=32)
        header = get_csr_header(
            regions = {
                "ctrl": SoCCSRRegion(origin=0x18000000, busword=32, obj=[csr]),
            },
            constants = {},
            csr_base  = 0x18000000,
            cpu       = cpu,
        )

        self.assertIn("#define CSR_BASE 0x18000000L", header)
        self.assertIn("#define CSR_CTRL_BASE (CSR_BASE + 0x0L)", header)
        self.assertIn("#define CSR_CTRL_SCRATCH_ADDR (CSR_BASE + 0x0L)", header)
        self.assertIn("return csr_read_simple((CSR_BASE + 0x0L));", header)
        self.assertNotIn("CSR_BASE_VA", header)
        self.assertNotIn("CSR_CTRL_BASE_VA", header)
        self.assertNotIn("CSR_CTRL_SCRATCH_ADDR_VA", header)

    def test_relative_csr_header_omits_virtual_aliases_for_identity_map(self):
        cpu = SimpleNamespace(
            bios_map = lambda addr, cached: addr,
        )
        csr = CSRStatus(name="scratch", size=32)
        header = get_csr_header(
            regions = {
                "ctrl": SoCCSRRegion(origin=0x0, busword=32, obj=[csr]),
            },
            constants            = {},
            csr_base             = 0x0,
            with_csr_base_define = False,
            cpu                  = cpu,
        )

        self.assertIn("#define CSR_CTRL_BASE 0x0L", header)
        self.assertIn("#define CSR_CTRL_SCRATCH_ADDR 0x0L", header)
        self.assertIn("return csr_read_simple(0x0L);", header)
        self.assertNotIn("CSR_CTRL_BASE_VA", header)
        self.assertNotIn("CSR_CTRL_SCRATCH_ADDR_VA", header)

    def test_svd_splits_wide_csr_fields_per_bus_word(self):
        csr = CSRStatus(name="switch", description="TMU Switch Status", fields=[
            CSRField("source", size=32, offset=0,  description="Source Thread ID"),
            CSRField("dest",   size=32, offset=32, description="Destination Thread ID"),
        ])

        svd       = _get_csr_svd(csr)
        registers = _get_svd_registers(svd)

        self.assertNotIn("<msb>-", svd)
        self.assertNotIn("<bitRange>[-", svd)
        self.assertEqual(registers["SWITCH1"], {
            "dest": {"msb": "31", "lsb": "0", "bitRange": "[31:0]"},
        })
        self.assertEqual(registers["SWITCH0"], {
            "source": {"msb": "31", "lsb": "0", "bitRange": "[31:0]"},
        })

    def test_svd_clips_field_crossing_split_csr_boundary(self):
        csr = CSRStatus(name="wide", fields=[
            CSRField("middle", size=32, offset=16),
        ])

        svd       = _get_csr_svd(csr)
        registers = _get_svd_registers(svd)

        self.assertNotIn("<msb>32</msb>", svd)
        self.assertEqual(registers["WIDE1"], {
            "middle": {"msb": "15", "lsb": "0", "bitRange": "[15:0]"},
        })
        self.assertEqual(registers["WIDE0"], {
            "middle": {"msb": "31", "lsb": "16", "bitRange": "[31:16]"},
        })


if __name__ == "__main__":
    unittest.main()
