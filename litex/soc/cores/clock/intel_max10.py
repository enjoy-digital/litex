#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.cores.clock.common import *
from litex.soc.cores.clock.intel_common import *

# Intel / Max10 ------------------------------------------------------------------------------------

class Max10PLL(IntelClocking):
    nclkouts_max   = 5
    n_div_range    = (1, 512+1)
    m_div_range    = (1, 512+1)
    c_div_range    = (1, 512+1)
    clkin_freq_range     = (5e6, 472.5e6)
    clkin_pfd_freq_range = (5e6, 325e6)  # FIXME: use
    vco_freq_range       = (600e6, 1300e6)
    def __init__(self, speedgrade="-6"):
        self.logger = logging.getLogger("Max10PLL")
        self.logger.info("Creating Max10PLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        IntelClocking.__init__(self)
        self.clko_freq_range = {
            "-6" : (0e6, 472.5e6),
            "-7" : (0e6, 450e6),
            "-8" : (0e6, 402.5e6),
        }[speedgrade]
