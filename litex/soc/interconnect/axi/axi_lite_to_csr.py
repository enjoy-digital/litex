#
# This file is part of LiteX.
#
# Copyright (c) 2018-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""AXI4-Full/Lite support for LiteX"""

from migen import *

from litex.gen import *

from litex.build.generic_platform import *

from litex.soc.interconnect.axi.axi_common import *
from litex.soc.interconnect.axi.axi_lite import *

# AXI-Lite to CSR ----------------------------------------------------------------------------------

class AXILite2CSR(LiteXModule):
    def __init__(self, axi_lite=None, bus_csr=None, register=False):
        # TODO: unused register argument
        if axi_lite is None:
            axi_lite = AXILiteInterface()
        if bus_csr is None:
            bus_csr = csr_bus.Interface()

        self.axi_lite = axi_lite
        self.csr      = bus_csr

        fsm, comb = axi_lite_to_simple(
            axi_lite   = self.axi_lite,
            port_adr   = self.csr.adr,
            port_dat_r = self.csr.dat_r,
            port_dat_w = self.csr.dat_w,
            port_we    = self.csr.we)
        self.fsm = fsm
        self.comb += comb
