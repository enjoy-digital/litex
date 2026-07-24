#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.build.openfpgaloader import OpenFPGALoader


class TestOpenFPGALoader(unittest.TestCase):
    def test_device_option(self):
        programmer = OpenFPGALoader(device="/dev/ttyUSB2")

        self.assertEqual(programmer.cmd, [
            "openFPGALoader",
            "--device", "/dev/ttyUSB2",
        ])

    def test_legacy_positional_arguments(self):
        programmer = OpenFPGALoader(
            "board", "cable", 10e6, "fpga-part", 2, "ftdi-serial")

        self.assertEqual(programmer.cmd, [
            "openFPGALoader",
            "--board",       "board",
            "--fpga-part",   "fpga-part",
            "--cable",       "cable",
            "--freq",        "10000000",
            "--index-chain", "2",
            "--ftdi-serial", "ftdi-serial",
        ])


if __name__ == "__main__":
    unittest.main()
