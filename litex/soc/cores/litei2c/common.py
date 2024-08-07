#
# This file is part of LiteX.
#
# Copyright (c) 2024 Fin Maaß <f.maass@vogl-electronic.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

# Core <-> PHY Layouts -----------------------------------------------------------------------------

"""
Stream layout for LiteI2CCore->PHY connection:
data - data to be transmitted
addr - slave address
len_tx - number of bytes to transmit
len_rx - number of bytes to receive
"""
i2c_core2phy_layout = [
    ("data",     32),
    ("addr",     7),
    ("len_tx",   3),
    ("len_rx",   3),
    ("recover",  1)
]
"""
Stream layout for PHY->LiteI2CCore connection
data - received data
nack - NACK signal
unfinished_tx - another tx transfer is expected
unfinished_rx - another rx transfer is expected
"""
i2c_phy2core_layout = [
    ("data",  32),
    ("nack", 1),
    ("unfinished_tx", 1),
    ("unfinished_rx", 1)
]

# Helpers ------------------------------------------------------------------------------------------

class ResyncReg(Module):
    def __init__(self, src, dst, clock_domain):
        if clock_domain == "sys":
            self.comb += dst.eq(src)
        else:
            self.specials += MultiReg(src, dst, clock_domain)
