#
# This file is part of LiteX-Boards.
#
# This file is Copyright (c) 2017-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Tim 'mithro' Ansell <me@mith.ro>
# SPDX-License-Identifier: BSD-2-Clause

import subprocess
import unittest
import os

from migen import *

from litex.soc.integration.builder import *

class TestTargets(unittest.TestCase):
    excluded_platforms = [
        "qmtech_daughterboard",              # Reason: Not a real platform.
        "enclustra_st1",                     # Readon: Not a real platform.
        "quicklogic_quickfeather",           # Reason: No default clock.
        "efinix_titanium_ti60_f225_dev_kit", # Reason: Require Efinity toolchain.
        "efinix_trion_t120_bga576_dev_kit",  # Reason: Require Efinity toolchain.
        "efinix_trion_t20_bga256_dev_kit",   # Reason: Require Efinity toolchain.
        "efinix_trion_t20_mipi_dev_kit",     # Reason: Require Efinity toolchain.
        "efinix_xyloni_dev_kit",             # Reason: Require Efinity toolchain.
        "sipeed_tang_primer",                # Reason: Require Anlogic toolchain.
        "jungle_electronics_fireant",        # Reason: Require Efinity toolchain.
        "efinix_t8f81_dev_kit",              # Reason: Require Efinity toolchain.
        "adi_plutosdr",                      # Reason: No default clock.
        "newae_cw305",                       # Reason: No default clock.
    ]
    excluded_targets   = [
        "simple",                            # Reason: Generic target.
        "quicklogic_quickfeather",           # Reason: No default clock.
        "efinix_titanium_ti60_f225_dev_kit", # Reason: Require Efinity toolchain.
        "efinix_trion_t120_bga576_dev_kit",  # Reason: Require Efinity toolchain.
        "efinix_trion_t20_bga256_dev_kit",   # Reason: Require Efinity toolchain.
        "efinix_trion_t20_mipi_dev_kit",     # Reason: Require Efinity toolchain.
        "efinix_xyloni_dev_kit",             # Reason: Require Efinity toolchain.
        "sipeed_tang_primer",                # Reason: Require Anlogic toolchain.
        "jungle_electronics_fireant",        # Reason: Require Efinity toolchain.
        "efinix_t8f81_dev_kit",              # Reason: Require Efinity toolchain.
    ]

    # Build simple design for all platforms.
    def test_platforms(self):
        # Collect platforms.
        platforms = []
        for file in os.listdir("./litex_boards/platforms/"):
            if file.endswith(".py"):
                file = file.replace(".py", "")
                if file not in ["__init__"] + self.excluded_platforms:
                    platforms.append(file)

        # Test platforms with simple design.
        for name in platforms:
            with self.subTest(platform=name):
                os.system("rm -rf build")
                cmd = """\
python3 -m litex_boards.targets.simple litex_boards.platforms.{} \
    --build            \
    --no-compile       \
    --uart-name="stub" \
""".format(name)
                subprocess.check_call(cmd, shell=True)

    # Build default configuration for all targets.
    def test_targets(self):
        # Collect targets.
        targets = []
        for file in os.listdir("./litex_boards/targets/"):
            if file.endswith(".py"):
                file = file.replace(".py", "")
                if file not in ["__init__"] + self.excluded_targets:
                    targets.append(file)

        # Test targets.
        for name in targets:
            with self.subTest(target=name):
                os.system("rm -rf build")
                cmd = """\
python3 -m litex_boards.targets.{} \
    --cpu-type=vexriscv     \
    --cpu-variant=minimal   \
    --build                 \
    --no-compile            \
""".format(name)
                subprocess.check_call(cmd, shell=True)
