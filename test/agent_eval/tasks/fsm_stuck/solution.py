#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Reference solution: the word counter of the engine is 8-bit, it wraps before reaching a length
# above 256 and the FSM never leaves RUN: size it as the length register.

import os

def solve(workdir):
    filename = os.path.join(workdir, "target.py")
    with open(filename) as f:
        content = f.read()
    content = content.replace(
        "self.count = count = Signal(8)",
        "self.count = count = Signal(16)")
    with open(filename, "w") as f:
        f.write(content)
