#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.soc.cores.cpu.cv32e41p.core import CPU_VARIANTS, CV32E41P


def _cv32e41p_gcc_flags(variant):
    cpu = CV32E41P.__new__(CV32E41P)
    cpu.variant = variant
    return cpu.gcc_flags


class TestCV32E41P(unittest.TestCase):
    def test_only_standard_variant_is_advertised(self):
        self.assertEqual(CPU_VARIANTS, ["standard"])

    def test_standard_variant_does_not_emit_compressed_instructions(self):
        flags = _cv32e41p_gcc_flags("standard")

        self.assertIn("-march=rv32i2p0_m", flags)
        self.assertNotIn("-march=rv32i2p0_mc", flags)
        self.assertIn("-D__cv32e41p__", flags)


if __name__ == "__main__":
    unittest.main()
