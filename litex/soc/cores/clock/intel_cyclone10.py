#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.cores.clock.common import *
from litex.soc.cores.clock.intel_common import *

# Intel / Cyclone10LP ------------------------------------------------------------------------------

class Cyclone10LPPLL(IntelClocking):
    nclkouts_max   = 5
    n_div_range    = (1, 512+1)
    m_div_range    = (1, 512+1)
    c_div_range    = (1, 512+1)
    clkin_pfd_freq_range  = (5e6, 325e6)  # FIXME: use
    vco_freq_range        = (600e6, 1300e6)
    def __init__(self, speedgrade="-C6"):
        self.logger = logging.getLogger("Cyclone10LPPLL")
        self.logger.info("Creating Cyclone10LPPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        IntelClocking.__init__(self)
        self.clkin_freq_range = {
            "-C6" : (5e6, 472.5e6),
            "-C8" : (5e6, 472.5e6),
            "-I7" : (5e6, 472.5e6),
            "-A7" : (5e6, 472.5e6),
            "-I8" : (5e6, 362e6),
        }[speedgrade]
        self.clko_freq_range = {
            "-C6" : (0e6, 472.5e6),
            "-C8" : (0e6, 402.5e6),
            "-I7" : (0e6, 450e6),
            "-A7" : (0e6, 450e6),
            "-I8" : (0e6, 362e6),
        }[speedgrade]
