#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.cores.clock.common import *
from litex.soc.cores.clock.intel_common import *

# Intel / CycloneV --------------------------------------------------------------------------------

class CycloneVPLL(IntelClocking):
    nclkouts_max   = 5
    n_div_range    = (1, 512+1)
    m_div_range    = (1, 512+1)
    c_div_range    = (1, 512+1)
    clkin_pfd_freq_range  = (5e6, 325e6)  # FIXME: use
    clkfin_pfd_freq_range = (50e6, 160e6) # FIXME: use
    def __init__(self, speedgrade="-C6"):
        self.logger = logging.getLogger("CycloneVPLL")
        self.logger.info("Creating CycloneVPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        IntelClocking.__init__(self)
        self.clkin_freq_range = {
            "-C6" : (5e6, 670e6),
            "-C7" : (5e6, 622e6),
            "-I7" : (5e6, 622e6),
            "-C8" : (5e6, 622e6),
            "-A7" : (5e6, 500e6),
        }[speedgrade]
        self.vco_freq_range = {
            "-C6" : (600e6, 1600e6),
            "-C7" : (600e6, 1600e6),
            "-I7" : (600e6, 1600e6),
            "-C8" : (600e6, 1300e6),
            "-A7" : (600e6, 1300e6),
        }[speedgrade]
        self.clko_freq_range = {
            "-C6" : (0e6, 550e6),
            "-C7" : (0e6, 550e6),
            "-I7" : (0e6, 550e6),
            "-C8" : (0e6, 460e6),
            "-A7" : (0e6, 460e6),
        }[speedgrade]
