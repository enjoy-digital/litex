#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.soc.integration.export import get_csr_header
from litex.soc.integration.soc import SoCCSRRegion
from litex.soc.interconnect.csr import CSRField, CSRStorage


def _get_csr_header(csr):
    return get_csr_header(
        regions = {
            "ctrl": SoCCSRRegion(origin=0xf0000000, busword=32, obj=[csr]),
        },
        constants                    = {},
        csr_base                     = 0xf0000000,
        with_fields_access_functions = True,
    )


class TestCSRExport(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
