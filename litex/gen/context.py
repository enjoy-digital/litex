#
# This file is part of LiteX.
#
# This file is Copyright (c) 2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

# LiteX Context ------------------------------------------------------------------------------------

class LiteXContext:
    """
    A context for LiteX-related settings.

    This class serves as a container for the platform, toolchain, device,
    and system-on-a-chip (SoC) information for a given LiteX project.

    Attributes:
        platform  : The FPGA Platform of the project.
        toolchain : The FPGA Toolchain to be used for synthesis and place-and-route.
        device    : The FPGA Device of the LiteX project.
        soc       : The FPGA SoC of the LiteX project.
    """
    platform  = None
    toolchain = None
    device    = None
    soc       = None
