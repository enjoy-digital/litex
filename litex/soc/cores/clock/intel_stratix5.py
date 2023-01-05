#
# This file is part of LiteX.
#
# Copyright (c) 2023 stone3311 <fenstein12@googlemail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.cores.clock.common import *
from litex.soc.cores.clock.intel_common import *

# Intel / StratixV --------------------------------------------------------------------------------

class StratixVPLL(IntelClocking):
    nclkouts_max   = 18
    n_div_range    = (1, 512+1)
    m_div_range    = (1, 512+1)
    c_div_range    = (1, 512+1)
    clkin_pfd_freq_range  = (5e6, 325e6)
    def __init__(self, speedgrade="-C4"):
        self.logger = logging.getLogger("StratixVPLL")
        self.logger.info("Creating StratixVPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        IntelClocking.__init__(self)

        if speedgrade == "-C4" or speedgrade == "-I4":
            self.clkin_freq_range =   (5e6,  650e6)
            self.vco_freq_range   = (600e6, 1300e6)
        else:
            self.clkin_freq_range =   (5e6,  800e6)
            self.vco_freq_range   = (600e6, 1600e6)

        self.clko_freq_range = {
            "-C1"   : (5e6, 717e6),
            "-C2"   : (5e6, 717e6),
            "-C2L"  : (5e6, 717e6),
            "-I2"   : (5e6, 717e6),
            "-I2L"  : (5e6, 717e6),
            "-C3"   : (5e6, 650e6),
            "-I3"   : (5e6, 650e6),
            "-I3L"  : (5e6, 650e6),
            "-C4"   : (5e6, 580e6),
            "-I4"   : (5e6, 580e6),
        }[speedgrade]
