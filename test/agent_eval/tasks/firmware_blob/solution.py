#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Reference solution: the prebuilt firmware writes the channel in bits 9:8 of adc_control (the
# layout of the SoC it was built for), where this SoC has the oversample field: every conversion
# reads channel 0 (with oversampling). Swap the channel (now bits 9:8) and oversample (5:4) fields.

import os

def solve(workdir):
    filename = os.path.join(workdir, "target.py")
    with open(filename) as f:
        content = f.read()
    content = content.replace(
        '            CSRField("channel",    size=2, offset=4, description="Channel to convert."),\n'
        '            CSRField("oversample", size=2, offset=8, description="Oversampling (2^oversample samples averaged)."),\n',
        '            CSRField("oversample", size=2, offset=4, description="Oversampling (2^oversample samples averaged)."),\n'
        '            CSRField("channel",    size=2, offset=8, description="Channel to convert."),\n')
    with open(filename, "w") as f:
        f.write(content)
