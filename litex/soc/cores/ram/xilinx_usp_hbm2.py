#
# This file is part of LiteX.
#
# Copyright (c) 2020-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.interconnect.axi import *
from litex.soc.interconnect.csr import *

# Ultrascale + HBM2 IP Wrapper ---------------------------------------------------------------------

class USPHBM2(Module, AutoCSR):
    """Xilinx Virtex US+ High Bandwidth Memory 2 IP wrapper"""
    def __init__(self, platform, hbm_ip_name="hbm_0"):
        self.platform = platform
        self.hbm_name = hbm_ip_name

        self.axi = []
        self.apb = []

        self.hbm_params = {}

        self.init_done = CSRStatus()

        # # #

        class Open(Signal): pass

        # Clocks -----------------------------------------------------------------------------------
        # Ref = 100 MHz (HBM: 900 (225-900) MHz), drives internal PLL (1 per stack).
        for i in range(2):
            self.hbm_params[f"i_HBM_REF_CLK_{i:1d}"] = ClockSignal("hbm_ref")

        # APB: 100 (50-100) MHz
        for i in range(2):
            self.hbm_params[f"i_APB_{i:1d}_PCLK"]     = ClockSignal("apb")
            self.hbm_params[f"i_APB_{i:1d}_PRESET_N"] = ~ResetSignal("apb")

        # AXI: 450 (225-450) MHz
        for i in range(32):
            self.hbm_params[f"i_AXI_{i:02d}_ACLK"]     = ClockSignal("axi")
            self.hbm_params[f"i_AXI_{i:02d}_ARESET_N"] = ~ResetSignal("apb")

        # AXI --------------------------------------------------------------------------------------
        for i in range(32):
            axi = AXIInterface(data_width=256, address_width=33, id_width=6)
            self.axi.append(axi)

            # AW Channel.
            self.hbm_params[f"i_AXI_{i :02d}_AWADDR"]      = axi.aw.addr
            self.hbm_params[f"i_AXI_{i :02d}_AWBURST"]     = axi.aw.burst
            self.hbm_params[f"i_AXI_{i :02d}_AWID"]        = axi.aw.id
            self.hbm_params[f"i_AXI_{i :02d}_AWLEN"]       = axi.aw.len
            self.hbm_params[f"i_AXI_{i :02d}_AWSIZE"]      = axi.aw.size
            self.hbm_params[f"i_AXI_{i :02d}_AWVALID"]     = axi.aw.valid
            self.hbm_params[f"o_AXI_{i :02d}_AWREADY"]     = axi.aw.ready

            # W Channel.
            self.hbm_params[f"i_AXI_{i:02d}_WDATA"]        = axi.w.data
            self.hbm_params[f"i_AXI_{i:02d}_WLAST"]        = axi.w.last
            self.hbm_params[f"i_AXI_{i:02d}_WSTRB"]        = axi.w.strb
            self.hbm_params[f"i_AXI_{i:02d}_WDATA_PARITY"] = 0 # FIXME: Manage parity?
            self.hbm_params[f"i_AXI_{i:02d}_WVALID"]       = axi.w.valid
            self.hbm_params[f"o_AXI_{i:02d}_WREADY"]       = axi.w.ready

            # B Channel.
            self.hbm_params[f"o_AXI_{i:02d}_BID"]          = axi.b.id
            self.hbm_params[f"o_AXI_{i:02d}_BRESP"]        = axi.b.resp
            self.hbm_params[f"o_AXI_{i:02d}_BVALID"]       = axi.b.valid
            self.hbm_params[f"i_AXI_{i:02d}_BREADY"]       = axi.b.ready

            # AR Channel.
            self.hbm_params[f"i_AXI_{i:02d}_ARADDR"]       = axi.ar.addr
            self.hbm_params[f"i_AXI_{i:02d}_ARBURST"]      = axi.ar.burst
            self.hbm_params[f"i_AXI_{i:02d}_ARID"]         = axi.ar.id
            self.hbm_params[f"i_AXI_{i:02d}_ARLEN"]        = axi.ar.len
            self.hbm_params[f"i_AXI_{i:02d}_ARSIZE"]       = axi.ar.size
            self.hbm_params[f"i_AXI_{i:02d}_ARVALID"]      = axi.ar.valid
            self.hbm_params[f"o_AXI_{i:02d}_ARREADY"]      = axi.ar.ready

            # R Channel.
            self.hbm_params[f"o_AXI_{i:02d}_RDATA_PARITY"] = Open() # FIXME: Manage parity?
            self.hbm_params[f"o_AXI_{i:02d}_RDATA"]        = axi.r.data
            self.hbm_params[f"o_AXI_{i:02d}_RID"]          = axi.r.id
            self.hbm_params[f"o_AXI_{i:02d}_RLAST"]        = axi.r.last
            self.hbm_params[f"o_AXI_{i:02d}_RRESP"]        = axi.r.resp
            self.hbm_params[f"o_AXI_{i:02d}_RVALID"]       = axi.r.valid
            self.hbm_params[f"i_AXI_{i:02d}_RREADY"]       = axi.r.ready

        # APB --------------------------------------------------------------------------------------
        # FIXME: Connect to CSR or Wishbone.
        apb_complete = Signal(2)
        for i in range(2):
            self.hbm_params[f"i_APB_{i:1d}_PWDATA"]  = 0
            self.hbm_params[f"i_APB_{i:1d}_PADDR"]   = 0
            self.hbm_params[f"i_APB_{i:1d}_PENABLE"] = 0
            self.hbm_params[f"i_APB_{i:1d}_PSEL"]    = 0
            self.hbm_params[f"i_APB_{i:1d}_PWRITE"]  = 0

            self.hbm_params[f"o_APB_{i:1d}_PRDATA"]  = Open()
            self.hbm_params[f"o_APB_{i:1d}_PREADY"]  = Open()
            self.hbm_params[f"o_APB_{i:1d}_PSLVERR"] = Open()

            self.hbm_params[f"o_apb_complete_{i:1d}"] = apb_complete[i]
        self.comb += self.init_done.status.eq(apb_complete == 0b11)

        # Temperature ------------------------------------------------------------------------------
        for i in range(2):
            self.hbm_params[f"o_DRAM_{i:1d}_STAT_CATTRIP"] = Open()
            self.hbm_params[f"o_DRAM_{i:1d}_STAT_TEMP"]    = Open()

    def add_sources(self, platform):
        platform.add_ip(os.path.join(os.getcwd(), "ip", "hbm", self.hbm_name + ".xci"))

    def do_finalize(self):
        self.add_sources(self.platform)
        self.specials += Instance(self.hbm_name, **self.hbm_params)
