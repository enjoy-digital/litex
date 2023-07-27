#
# This file is part of LiteX.
#
# This file is Copyright (c) 2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

# LiteX Context ------------------------------------------------------------------------------------

# FIXME: PoC to fix Efinix AsyncFIFO issue, think a bit more about it to see how to do it properly.

class LiteXContext:
    platform  = None
    toolchain = None
    device    = None
    soc       = None
