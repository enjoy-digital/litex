#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Reference solution: the ID and VALUE addresses are swapped in monitor.py (the CSRs of the sensor
# are allocated in declaration order: control, status, value, id; see csr.csv).

import os

def solve(workdir):
    filename = os.path.join(workdir, "monitor.py")
    with open(filename) as f:
        content = f.read()
    content = content.replace(
        "SENSOR_ID      = 0x00001008\nSENSOR_VALUE   = 0x0000100c\n",
        "SENSOR_ID      = 0x0000100c\nSENSOR_VALUE   = 0x00001008\n")
    with open(filename, "w") as f:
        f.write(content)
