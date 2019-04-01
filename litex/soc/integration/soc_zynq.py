import os

from migen import *

from litex.build.generic_platform import tools
from litex.soc.integration.soc_core import *
from litex.soc.integration.cpu_interface import get_csr_header
from litex.soc.interconnect import wishbone
from litex.soc.interconnect import axi


class SoCZynq(SoCCore):
    SoCCore.mem_map["csr"] = 0x00000000
    def __init__(self, platform, clk_freq, ps7_name, **kwargs):
        SoCCore.__init__(self, platform, clk_freq, cpu_type=None, shadow_base=0x00000000, **kwargs)

        # PS7 --------------------------------------------------------------------------------------
        self.axi_gp0 = axi_gp0 = axi.AXIInterface(data_width=32, address_width=32, id_width=12)
        ps7_ddram_pads = platform.request("ps7_ddram")
        self.specials += Instance(ps7_name,
            # clk/rst
            io_PS_CLK=platform.request("ps7_clk"),
            io_PS_PORB=platform.request("ps7_porb"),
            io_PS_SRSTB=platform.request("ps7_srstb"),

            # mio
            io_MIO=platform.request("ps7_mio"),

            # ddram
            io_DDR_Addr=ps7_ddram_pads.addr,
            io_DDR_BankAddr=ps7_ddram_pads.ba,
            io_DDR_CAS_n=ps7_ddram_pads.cas_n,
            io_DDR_Clk_n=ps7_ddram_pads.ck_n,
            io_DDR_Clk=ps7_ddram_pads.ck_p,
            io_DDR_CKE=ps7_ddram_pads.cke,
            io_DDR_CS_n=ps7_ddram_pads.cs_n,
            io_DDR_DM=ps7_ddram_pads.dm,
            io_DDR_DQ=ps7_ddram_pads.dq,
            io_DDR_DQS_n=ps7_ddram_pads.dqs_n,
            io_DDR_DQS=ps7_ddram_pads.dqs_p,
            io_DDR_ODT=ps7_ddram_pads.odt,
            io_DDR_RAS_n=ps7_ddram_pads.ras_n,
            io_DDR_DRSTB=ps7_ddram_pads.reset_n,
            io_DDR_WEB=ps7_ddram_pads.we_n,
            io_DDR_VRN=ps7_ddram_pads.vrn,
            io_DDR_VRP=ps7_ddram_pads.vrp,

            # ethernet
            i_ENET0_MDIO_I=0,

            # sdio0
            i_SDIO0_WP=0,

            # usb0
            i_USB0_VBUS_PWRFAULT=0,

            # fabric clk
            o_FCLK_CLK0=ClockSignal("sys"),

            # axi gp0 clk
            i_M_AXI_GP0_ACLK=ClockSignal("sys"),

            # axi gp0 aw
            o_M_AXI_GP0_AWVALID=axi_gp0.aw.valid,
            i_M_AXI_GP0_AWREADY=axi_gp0.aw.ready,
            o_M_AXI_GP0_AWADDR=axi_gp0.aw.addr,
            o_M_AXI_GP0_AWBURST=axi_gp0.aw.burst,
            o_M_AXI_GP0_AWLEN=axi_gp0.aw.len,
            o_M_AXI_GP0_AWSIZE=axi_gp0.aw.size,
            o_M_AXI_GP0_AWID=axi_gp0.aw.id,
            o_M_AXI_GP0_AWLOCK=axi_gp0.aw.lock,
            o_M_AXI_GP0_AWPROT=axi_gp0.aw.prot,
            o_M_AXI_GP0_AWCACHE=axi_gp0.aw.cache,
            o_M_AXI_GP0_AWQOS=axi_gp0.aw.qos,

            # axi gp0 w
            o_M_AXI_GP0_WVALID=axi_gp0.w.valid,
            o_M_AXI_GP0_WLAST=axi_gp0.w.last,
            i_M_AXI_GP0_WREADY=axi_gp0.w.ready,
            #o_M_AXI_GP0_WID=,
            o_M_AXI_GP0_WDATA=axi_gp0.w.data,
            o_M_AXI_GP0_WSTRB=axi_gp0.w.strb,

            # axi gp0 b
            i_M_AXI_GP0_BVALID=axi_gp0.b.valid,
            o_M_AXI_GP0_BREADY=axi_gp0.b.ready,
            i_M_AXI_GP0_BID=axi_gp0.b.id,
            i_M_AXI_GP0_BRESP=axi_gp0.b.resp,

            # axi gp0 ar
            o_M_AXI_GP0_ARVALID=axi_gp0.ar.valid,
            i_M_AXI_GP0_ARREADY=axi_gp0.ar.ready,
            o_M_AXI_GP0_ARADDR=axi_gp0.ar.addr,
            o_M_AXI_GP0_ARBURST=axi_gp0.ar.burst,
            o_M_AXI_GP0_ARLEN=axi_gp0.ar.len,
            o_M_AXI_GP0_ARID=axi_gp0.ar.id,
            o_M_AXI_GP0_ARLOCK=axi_gp0.ar.lock,
            o_M_AXI_GP0_ARSIZE=axi_gp0.ar.size,
            o_M_AXI_GP0_ARPROT=axi_gp0.ar.prot,
            o_M_AXI_GP0_ARCACHE=axi_gp0.ar.cache,
            o_M_AXI_GP0_ARQOS=axi_gp0.ar.qos,

            # axi gp0 r
            i_M_AXI_GP0_RVALID=axi_gp0.r.valid,
            o_M_AXI_GP0_RREADY=axi_gp0.r.ready,
            i_M_AXI_GP0_RLAST=axi_gp0.r.last,
            i_M_AXI_GP0_RID=axi_gp0.r.id,
            i_M_AXI_GP0_RRESP=axi_gp0.r.resp,
            i_M_AXI_GP0_RDATA=axi_gp0.r.data,
        )
        platform.add_ip(os.path.join("ip", ps7_name + ".xci"))

        # AXI to Wishbone --------------------------------------------------------------------------
        self.wb_gp0 = wb_gp0 = wishbone.Interface()
        axi2wishbone = axi.AXI2Wishbone(axi_gp0, wb_gp0, base_address=0x43c00000)
        self.submodules += axi2wishbone
        self.add_wb_master(wb_gp0)

    def generate_software_header(self, filename):
        csr_header = get_csr_header(self.get_csr_regions(),
                                    self.get_constants(),
                                    with_access_functions=False)
        tools.write_to_file(filename, csr_header)
