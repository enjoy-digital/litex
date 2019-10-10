# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import os

from migen import *

from litex.build.generic_platform import tools
from litex.soc.integration.soc_core import *
from litex.soc.integration.cpu_interface import get_csr_header
from litex.soc.interconnect import wishbone
from litex.soc.interconnect import axi

# Record layouts -----------------------------------------------------------------------------------

def axi_fifo_ctrl_layout():
    return [
        ("racount",         3, DIR_M_TO_S),
        ("rcount",          8, DIR_M_TO_S),
        ("rdissuecapen",    1, DIR_S_TO_M),
        ("wacount",         6, DIR_M_TO_S),
        ("wcount",          8, DIR_M_TO_S),
        ("wrissuecapen",    1, DIR_S_TO_M),
    ]

# SoC Zynq -----------------------------------------------------------------------------------------

class SoCZynq(SoCCore):
    SoCCore.mem_map["csr"] = 0x00000000
    def __init__(self, platform, clk_freq, ps7_name, **kwargs):
        self.ps7_name = ps7_name
        SoCCore.__init__(self, platform, clk_freq, cpu_type=None, **kwargs)

        # PS7 (Minimal) ----------------------------------------------------------------------------
        fclk_reset0_n = Signal()
        ps7_ddram_pads = platform.request("ps7_ddram")
        self.ps7_params = dict(
            # clk/rst
            io_PS_CLK   = platform.request("ps7_clk"),
            io_PS_PORB  = platform.request("ps7_porb"),
            io_PS_SRSTB = platform.request("ps7_srstb"),

            # mio
            io_MIO=platform.request("ps7_mio"),

            # ddram
            io_DDR_Addr     = ps7_ddram_pads.addr,
            io_DDR_BankAddr = ps7_ddram_pads.ba,
            io_DDR_CAS_n    = ps7_ddram_pads.cas_n,
            io_DDR_Clk_n    = ps7_ddram_pads.ck_n,
            io_DDR_Clk      = ps7_ddram_pads.ck_p,
            io_DDR_CKE      = ps7_ddram_pads.cke,
            io_DDR_CS_n     = ps7_ddram_pads.cs_n,
            io_DDR_DM       = ps7_ddram_pads.dm,
            io_DDR_DQ       = ps7_ddram_pads.dq,
            io_DDR_DQS_n    = ps7_ddram_pads.dqs_n,
            io_DDR_DQS      = ps7_ddram_pads.dqs_p,
            io_DDR_ODT      = ps7_ddram_pads.odt,
            io_DDR_RAS_n    = ps7_ddram_pads.ras_n,
            io_DDR_DRSTB    = ps7_ddram_pads.reset_n,
            io_DDR_WEB      = ps7_ddram_pads.we_n,
            io_DDR_VRN      = ps7_ddram_pads.vrn,
            io_DDR_VRP      = ps7_ddram_pads.vrp,

            # ethernet
            i_ENET0_MDIO_I=0,

            # sdio0
            i_SDIO0_WP=0,

            # usb0
            i_USB0_VBUS_PWRFAULT=0,

            # fabric clk/rst
            o_FCLK_CLK0     = ClockSignal("sys"),
            o_FCLK_RESET0_N = fclk_reset0_n
        )
        self.comb += ResetSignal("sys").eq(~fclk_reset0_n)
        platform.add_ip(os.path.join("ip", ps7_name + ".xci"))

    # GP0 ------------------------------------------------------------------------------------------

    def add_gp0(self):
        self.axi_gp0 = axi_gp0 = axi.AXIInterface(data_width=32, address_width=32, id_width=12)
        self.ps7_params.update(
            # axi gp0 clk
            i_M_AXI_GP0_ACLK=ClockSignal("sys"),

            # axi gp0 aw
            o_M_AXI_GP0_AWVALID = axi_gp0.aw.valid,
            i_M_AXI_GP0_AWREADY = axi_gp0.aw.ready,
            o_M_AXI_GP0_AWADDR  = axi_gp0.aw.addr,
            o_M_AXI_GP0_AWBURST = axi_gp0.aw.burst,
            o_M_AXI_GP0_AWLEN   = axi_gp0.aw.len,
            o_M_AXI_GP0_AWSIZE  = axi_gp0.aw.size,
            o_M_AXI_GP0_AWID    = axi_gp0.aw.id,
            o_M_AXI_GP0_AWLOCK  = axi_gp0.aw.lock,
            o_M_AXI_GP0_AWPROT  = axi_gp0.aw.prot,
            o_M_AXI_GP0_AWCACHE = axi_gp0.aw.cache,
            o_M_AXI_GP0_AWQOS   = axi_gp0.aw.qos,

            # axi gp0 w
            o_M_AXI_GP0_WVALID = axi_gp0.w.valid,
            o_M_AXI_GP0_WLAST  = axi_gp0.w.last,
            i_M_AXI_GP0_WREADY = axi_gp0.w.ready,
            o_M_AXI_GP0_WID    = axi_gp0.w.id,
            o_M_AXI_GP0_WDATA  = axi_gp0.w.data,
            o_M_AXI_GP0_WSTRB  = axi_gp0.w.strb,

            # axi gp0 b
            i_M_AXI_GP0_BVALID = axi_gp0.b.valid,
            o_M_AXI_GP0_BREADY = axi_gp0.b.ready,
            i_M_AXI_GP0_BID    = axi_gp0.b.id,
            i_M_AXI_GP0_BRESP  = axi_gp0.b.resp,

            # axi gp0 ar
            o_M_AXI_GP0_ARVALID = axi_gp0.ar.valid,
            i_M_AXI_GP0_ARREADY = axi_gp0.ar.ready,
            o_M_AXI_GP0_ARADDR  = axi_gp0.ar.addr,
            o_M_AXI_GP0_ARBURST = axi_gp0.ar.burst,
            o_M_AXI_GP0_ARLEN   = axi_gp0.ar.len,
            o_M_AXI_GP0_ARID    = axi_gp0.ar.id,
            o_M_AXI_GP0_ARLOCK  = axi_gp0.ar.lock,
            o_M_AXI_GP0_ARSIZE  = axi_gp0.ar.size,
            o_M_AXI_GP0_ARPROT  = axi_gp0.ar.prot,
            o_M_AXI_GP0_ARCACHE = axi_gp0.ar.cache,
            o_M_AXI_GP0_ARQOS   = axi_gp0.ar.qos,

            # axi gp0 r
            i_M_AXI_GP0_RVALID = axi_gp0.r.valid,
            o_M_AXI_GP0_RREADY = axi_gp0.r.ready,
            i_M_AXI_GP0_RLAST  = axi_gp0.r.last,
            i_M_AXI_GP0_RID    = axi_gp0.r.id,
            i_M_AXI_GP0_RRESP  = axi_gp0.r.resp,
            i_M_AXI_GP0_RDATA  = axi_gp0.r.data,
        )

    # HP0 ------------------------------------------------------------------------------------------

    def add_hp0(self):
        self.axi_hp0 = axi_hp0 = axi.AXIInterface(data_width=64, address_width=32, id_width=6)
        self.axi_hp0_fifo_ctrl = axi_hp0_fifo_ctrl = Record(axi_fifo_ctrl_layout())
        self.ps7_params.update(
            # axi hp0 clk
            i_S_AXI_HP0_ACLK=ClockSignal("sys"),

            # axi hp0 aw
            i_S_AXI_HP0_AWVALID = axi_hp0.aw.valid,
            o_S_AXI_HP0_AWREADY = axi_hp0.aw.ready,
            i_S_AXI_HP0_AWADDR  = axi_hp0.aw.addr,
            i_S_AXI_HP0_AWBURST = axi_hp0.aw.burst,
            i_S_AXI_HP0_AWLEN   = axi_hp0.aw.len,
            i_S_AXI_HP0_AWSIZE  = axi_hp0.aw.size,
            i_S_AXI_HP0_AWID    = axi_hp0.aw.id,
            i_S_AXI_HP0_AWLOCK  = axi_hp0.aw.lock,
            i_S_AXI_HP0_AWPROT  = axi_hp0.aw.prot,
            i_S_AXI_HP0_AWCACHE = axi_hp0.aw.cache,
            i_S_AXI_HP0_AWQOS   = axi_hp0.aw.qos,

            # axi hp0 w
            i_S_AXI_HP0_WVALID = axi_hp0.w.valid,
            i_S_AXI_HP0_WLAST  = axi_hp0.w.last,
            o_S_AXI_HP0_WREADY = axi_hp0.w.ready,
            i_S_AXI_HP0_WID    = axi_hp0.w.id,
            i_S_AXI_HP0_WDATA  = axi_hp0.w.data,
            i_S_AXI_HP0_WSTRB  = axi_hp0.w.strb,

            # axi hp0 b
            o_S_AXI_HP0_BVALID = axi_hp0.b.valid,
            i_S_AXI_HP0_BREADY = axi_hp0.b.ready,
            o_S_AXI_HP0_BID    = axi_hp0.b.id,
            o_S_AXI_HP0_BRESP  = axi_hp0.b.resp,

            # axi hp0 ar
            i_S_AXI_HP0_ARVALID = axi_hp0.ar.valid,
            o_S_AXI_HP0_ARREADY = axi_hp0.ar.ready,
            i_S_AXI_HP0_ARADDR  = axi_hp0.ar.addr,
            i_S_AXI_HP0_ARBURST = axi_hp0.ar.burst,
            i_S_AXI_HP0_ARLEN   = axi_hp0.ar.len,
            i_S_AXI_HP0_ARID    = axi_hp0.ar.id,
            i_S_AXI_HP0_ARLOCK  = axi_hp0.ar.lock,
            i_S_AXI_HP0_ARSIZE  = axi_hp0.ar.size,
            i_S_AXI_HP0_ARPROT  = axi_hp0.ar.prot,
            i_S_AXI_HP0_ARCACHE = axi_hp0.ar.cache,
            i_S_AXI_HP0_ARQOS   = axi_hp0.ar.qos,

            # axi hp0 r
            o_S_AXI_HP0_RVALID = axi_hp0.r.valid,
            i_S_AXI_HP0_RREADY = axi_hp0.r.ready,
            o_S_AXI_HP0_RLAST  = axi_hp0.r.last,
            o_S_AXI_HP0_RID    = axi_hp0.r.id,
            o_S_AXI_HP0_RRESP  = axi_hp0.r.resp,
            o_S_AXI_HP0_RDATA  = axi_hp0.r.data,

            # axi hp0 fifo ctrl
            o_S_AXI_HP0_RACOUNT        = axi_hp0_fifo_ctrl.racount,
            o_S_AXI_HP0_RCOUNT         = axi_hp0_fifo_ctrl.rcount,
            i_S_AXI_HP0_RDISSUECAP1_EN = axi_hp0_fifo_ctrl.rdissuecapen,
            o_S_AXI_HP0_WACOUNT        = axi_hp0_fifo_ctrl.wacount,
            o_S_AXI_HP0_WCOUNT         = axi_hp0_fifo_ctrl.wcount,
            i_S_AXI_HP0_WRISSUECAP1_EN = axi_hp0_fifo_ctrl.wrissuecapen
        )

    def add_axi_to_wishbone(self, axi_port, base_address=0x43c00000):
        wb = wishbone.Interface()
        axi2wishbone = axi.AXI2Wishbone(axi_port, wb, base_address)
        self.submodules += axi2wishbone
        self.add_wb_master(wb)

    def do_finalize(self):
        SoCCore.do_finalize(self)
        self.specials += Instance(self.ps7_name, **self.ps7_params)

    def generate_software_header(self, filename):
        csr_header = get_csr_header(self.csr_regions,
                                    self.constants,
                                    with_access_functions=False)
        tools.write_to_file(filename, csr_header)
