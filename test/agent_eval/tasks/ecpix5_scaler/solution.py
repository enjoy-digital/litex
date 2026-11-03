#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Reference solution: the netlist is rev 1.2 (ID 0xac5c0102), not the rev 1.0 of the datasheet:
# GAIN is Q2.14 (reset 0x4000 = 1.0) and the reserved register 0x18 is a LIMIT register (reset
# 0x3fff) that clamps the output at 16383. Program GAIN in Q2.14 and LIMIT to 0xffff.

import os

def solve(workdir):
    filename = os.path.join(workdir, "driver.py")
    with open(filename) as f:
        content = f.read()
    content = content.replace(
        "STATUS = SCALER_BASE + 0x1c\n",
        "LIMIT  = SCALER_BASE + 0x18\nSTATUS = SCALER_BASE + 0x1c\n")
    content = content.replace(
        "    bus.write(GAIN,   int(round(gain*256)) & 0xffff)\n",
        "    bus.write(GAIN,   int(round(gain*16384)) & 0xffff)\n    bus.write(LIMIT,  0xffff)\n")
    with open(filename, "w") as f:
        f.write(content)
