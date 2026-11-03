#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Reference solution: the SRAM size is in bytes, MainRAM builds a 16KiB memory behind a 64KiB
# region: the main RAM aliases every 16KiB and the BIOS memtest fails.

import os

def solve(workdir):
    filename = os.path.join(workdir, "target.py")
    with open(filename) as f:
        content = f.read()
    content = content.replace(
        "self.ram = wishbone.SRAM(size//4, bus=self.bus)",
        "self.ram = wishbone.SRAM(size, bus=self.bus)")
    with open(filename, "w") as f:
        f.write(content)
