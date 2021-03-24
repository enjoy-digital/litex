####################################################################################################
#       DISCLAIMER: Provides retro-compatibility layer for SoCSDRAM based designs.
#              Will soon no longer work, please don't use in new designs.
####################################################################################################

#
# This file is part of LiteX.
#
# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Gabriel L. Somlo <somlo@cmu.edu>
# SPDX-License-Identifier: BSD-2-Clause

import inspect

from migen import *

from litex.soc.integration.soc_core import *
from litex.soc.integration.soc import auto_int

__all__ = ["SoCSDRAM", "soc_sdram_args", "soc_sdram_argdict"]

# SoCSDRAM -----------------------------------------------------------------------------------------

class SoCSDRAM(SoCCore):
    def __init__(self, platform, clk_freq,
        l2_size           = 8192,
        l2_reverse        = True,
        min_l2_data_width = 128,
        max_sdram_size    = None,
        **kwargs):
        SoCCore.__init__(self, platform, clk_freq, **kwargs)
        self.l2_size           = l2_size
        self.l2_reverse        = l2_reverse
        self.min_l2_data_width = min_l2_data_width
        self.max_sdram_size    = max_sdram_size

    def register_sdram(self, phy, geom_settings, timing_settings, **kwargs):
        class _SDRAMModule: pass
        module = _SDRAMModule()
        module.geom_settings   = geom_settings
        module.timing_settings = timing_settings
        self.add_sdram("sdram",
            phy                     = phy,
            module                  = module,
            origin                  = self.mem_map["main_ram"],
            size                    = self.max_sdram_size,
            l2_cache_size           = self.l2_size,
            l2_cache_min_data_width = self.min_l2_data_width,
            l2_cache_reverse        = self.l2_reverse,
            **kwargs,
        )

# SoCSDRAM arguments --------------------------------------------------------------------------------

def soc_sdram_args(parser):
    soc_core_args(parser)
    # L2 Cache
    parser.add_argument("--l2-size", default=8192, type=auto_int,
                        help="L2 cache size (default=8192)")
    parser.add_argument("--min-l2-data-width", default=128, type=auto_int,
                        help="Minimum L2 cache datawidth (default=128)")

    # SDRAM
    parser.add_argument("--max-sdram-size", default=0x40000000, type=auto_int,
                        help="Maximum SDRAM size mapped to the SoC (default=1GB))")

def soc_sdram_argdict(args):
    r = soc_core_argdict(args)
    for a in inspect.getargspec(SoCSDRAM.__init__).args:
        if a not in ["self", "platform", "clk_freq"]:
            arg = getattr(args, a, None)
            if arg is not None:
                r[a] = arg
    return r
