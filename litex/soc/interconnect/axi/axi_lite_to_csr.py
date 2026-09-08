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

from litex.soc.interconnect import csr_bus

from litex.soc.interconnect.axi.axi_common import *
from litex.soc.interconnect.axi.axi_lite import *

# AXI-Lite to CSR ----------------------------------------------------------------------------------

class AXILite2CSR(LiteXModule):
    def __init__(self, axi_lite=None, bus_csr=None, register=False):
        # TODO: unused register argument
        if axi_lite is None:
            axi_lite = AXILiteInterface()
        if bus_csr is None:
            bus_csr = csr_bus.Interface(data_width=axi_lite.data_width)

        self.axi_lite = axi_lite
        self.csr      = bus_csr

        if axi_lite.data_width != bus_csr.alignment:
            raise ValueError("AXI-Lite data width must match CSR alignment.")
        if bus_csr.data_width > axi_lite.data_width:
            raise ValueError("CSR data width must not exceed AXI-Lite data width.")

        csr_we = Signal()
        fsm, comb = axi_lite_to_simple(
            axi_lite   = self.axi_lite,
            port_adr   = self.csr.adr,
            port_re    = self.csr.re,
            port_dat_r = self.csr.dat_r,
            port_dat_w = self.csr.dat_w,
            port_we    = csr_we)
        self.fsm = fsm
        self.comb += comb
        # Narrow CSRs occupy the low byte lanes of each aligned bus word. Writes selecting
        # only padding lanes must not change the register or trigger its write side effects.
        self.comb += self.csr.we.eq(csr_we & (axi_lite.w.strb[:(bus_csr.data_width + 7)//8] != 0))
