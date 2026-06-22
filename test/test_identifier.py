#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Unit tests for litex.soc.cores.identifier.Identifier.

The class itself is just a Memory-backed ROM, but the constructor enforces two real invariants
worth pinning down: no commas in the identifier, and ≤255 byte length. Plus the ROM contents
must match the input string + a NUL terminator.
"""

import unittest

from litex.soc.cores.identifier import Identifier


class TestIdentifier(unittest.TestCase):
    def test_rom_contents_match_string(self):
        ident = "litex"
        dut   = Identifier(ident)
        # mem.init holds the bytes of `ident` followed by a NUL terminator.
        self.assertEqual(dut.mem.init, list(ident.encode()) + [0])
        self.assertEqual(dut.mem.depth, len(ident) + 1)
        self.assertEqual(dut.mem.width, 8)

    def test_empty_string_is_just_a_nul(self):
        dut = Identifier("")
        self.assertEqual(dut.mem.init,  [0])
        self.assertEqual(dut.mem.depth, 1)

    def test_comma_in_string_is_rejected(self):
        with self.assertRaises(ValueError):
            Identifier("foo,bar")

    def test_string_at_max_length_is_accepted(self):
        # 255 chars is the upper bound (exclusive of the NUL terminator).
        ident = "a"*255
        dut   = Identifier(ident)
        self.assertEqual(dut.mem.depth, 256)

    def test_string_over_max_length_is_rejected(self):
        with self.assertRaises(ValueError):
            Identifier("a"*256)


if __name__ == "__main__":
    unittest.main()
