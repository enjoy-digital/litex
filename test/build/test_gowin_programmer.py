#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.build.gowin.programmer import (
    GowinProgrammer,
    GOWIN_CABLE_FT2CH,
    GOWIN_CABLE_GWU2X,
)


class TestGowinProgrammer(unittest.TestCase):
    def test_cable_name_resolution(self):
        programmer = GowinProgrammer("GW2A-18C", cable="ft2ch")
        self.assertEqual(programmer.cable, GOWIN_CABLE_FT2CH)

        programmer = GowinProgrammer("GW1NR-9C", cable="gwu2x")
        self.assertEqual(programmer.cable, GOWIN_CABLE_GWU2X)

        programmer = GowinProgrammer("GW5AT-15A", cable="usb-debugger-a")
        self.assertEqual(programmer.cable, 4)

    def test_invalid_cable_name(self):
        with self.assertRaises(ValueError):
            GowinProgrammer("GW2A-18C", cable="invalid")

    def test_programmer_args(self):
        programmer = GowinProgrammer("GW5AST-138B", cable="usb-debugger-a", channel=0)
        cmd_line = programmer._add_programmer_args([])
        self.assertEqual(cmd_line, [
            "--cable-index", "4",
            "--channel", "0",
        ])

    def test_location_overrides_channel(self):
        programmer = GowinProgrammer(
            "GW5AST-138B",
            cable       = "usb-debugger-a",
            channel     = 0,
            location    = 2,
        )
        cmd_line = programmer._add_programmer_args([])
        self.assertEqual(cmd_line, [
            "--cable-index", "4",
            "--location", "2",
        ])

    def test_uid_argument(self):
        programmer = GowinProgrammer(
            "GW5AST-138B",
            cable = "ft2ch",
            uid   = "0123456789ABCDEF",
        )
        cmd_line = programmer._add_programmer_args([])
        self.assertEqual(cmd_line, [
            "--cable-index", "1",
            "--uid", "0123456789ABCDEF",
        ])


if __name__ == "__main__":
    unittest.main()
