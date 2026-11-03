#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Reference solution: the enable field of the ticker control register resets to 0, the ticker is
# specified to run out of reset: reset it to 1.

import os

def solve(workdir):
    filename = os.path.join(workdir, "target.py")
    with open(filename) as f:
        content = f.read()
    content = content.replace(
        'CSRField("enable", size=1, description="Ticker enable."),',
        'CSRField("enable", size=1, reset=1, description="Ticker enable."),')
    with open(filename, "w") as f:
        f.write(content)
