#
# This file is part of LiteX.
#
# Copyright (c) 2022 Icenowy Zheng <icenowy@aosc.io>
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.cores.clock.gowin_gw1n import GW1NPLL

# GoWin / GW2APLL ----------------------------------------------------------------------------------

class GW2APLL(GW1NPLL):
    # GW2A has the same PLL primitive than GW1N but vco/pfd_freq_range are specific to device.

    @staticmethod
    def get_vco_freq_range(device):
        vco_freq_range = None
        if device.startswith('GW2A-'):
            vco_freq_range = (500e6, 1250e6) # datasheet values
        if vco_freq_range is None:
            raise ValueError(f"Unsupported device {device}.")
        return vco_freq_range

    @staticmethod
    def get_pfd_freq_range(device):
        pfd_freq_range = None
        if device.startswith('GW2A-'):
            pfd_freq_range = (3e6, 500e6)  # datasheet values
        if pfd_freq_range is None:
            raise ValueError(f"Unsupported device {device}.")
        return pfd_freq_range
