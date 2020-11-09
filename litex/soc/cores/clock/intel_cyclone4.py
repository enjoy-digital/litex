#
# This file is part of LiteX.
#
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.cores.clock.common import *
from litex.soc.cores.clock.intel_common import *

# Intel / CycloneIV -------------------------------------------------------------------------------

class CycloneIVPLL(IntelClocking):
    nclkouts_max   = 5
    n_div_range    = (1, 512+1)
    m_div_range    = (1, 512+1)
    c_div_range    = (1, 512+1)
    vco_freq_range = (600e6, 1300e6)
    def __init__(self, speedgrade="-6"):
        self.logger = logging.getLogger("CycloneIVPLL")
        self.logger.info("Creating CycloneIVPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        IntelClocking.__init__(self)
        self.clkin_freq_range = {
            "-6" : (5e6, 472.5e6),
            "-7" : (5e6, 472.5e6),
            "-8" : (5e6, 472.5e6),
            "-8L": (5e6, 362e6),
            "-9L": (5e6, 256e6),
        }[speedgrade]
        self.clko_freq_range = {
            "-6" : (0e6, 472.5e6),
            "-7" : (0e6, 450e6),
            "-8" : (0e6, 402.5e6),
            "-8L": (0e6, 362e6),
            "-9L": (0e6, 265e6),
        }[speedgrade]
