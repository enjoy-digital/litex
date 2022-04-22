#
# This file is part of LiteX.
#
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# Copyright (c) 2022 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.soc.interconnect import axi

from litex.soc.cores.cpu import CPU

# Zynq 7000 ----------------------------------------------------------------------------------------

class Zynq7000(CPU):
    variants             = ["standard"]
    category             = "hardcore"
    family               = "arm"
    name                 = "zynq7000"
    human_name           = "Zynq7000"
    data_width           = 32
    endianness           = "little"
    reset_address        = 0xfc00_0000
    gcc_triple           = "arm-none-eabi"
    gcc_flags            = "-mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard"
    linker_output_format = "elf32-littlearm"
    nop                  = "nop"
    io_regions           = {0x4000_0000: 0xbc00_0000} # Origin, Length.
    csr_decode           = False # AXI address is decoded in AXI2Wishbone (target level).

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "sram": 0x10_0000,  # DDR in fact
            "rom":  0xfc00_0000,
        }

    def __init__(self, platform, variant, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.platform       = platform
        self.reset          = Signal()
        self.periph_buses   = []    # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses   = []    # Memory buses (Connected directly to LiteDRAM).

        self.axi_gp_masters = []    # General Purpose AXI Masters.
        self.axi_gp_slaves  = []    # General Purpose AXI Slaves.
        self.axi_hp_slaves  = []    # High Performance AXI Slaves.

        # # #

        # PS7 Clocking.
        self.clock_domains.cd_ps7 = ClockDomain()

        # PS7 (Minimal) ----------------------------------------------------------------------------
        self.ps7_name   = None
        self.ps7_tcl    = []
        ps7_rst_n       = Signal()
        ps7_ddram_pads  = platform.request("ps7_ddram")
        self.cpu_params = dict(
            # Clk / Rst.
            io_PS_CLK   = platform.request("ps7_clk"),
            io_PS_PORB  = platform.request("ps7_porb"),
            io_PS_SRSTB = platform.request("ps7_srstb"),

            # MIO.
            io_MIO = platform.request("ps7_mio"),

            # DDRAM.
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

            # USB0.
            i_USB0_VBUS_PWRFAULT = 0,

            # Fabric Clk / Rst.
            o_FCLK_CLK0     = ClockSignal("ps7"),
            o_FCLK_RESET0_N = ps7_rst_n
        )
        self.specials += AsyncResetSynchronizer(self.cd_ps7, ~ps7_rst_n)

        # Enet0 mdio -------------------------------------------------------------------------------
        ps7_enet0_mdio_pads = platform.request("ps7_enet0_mdio", loose=True)
        if ps7_enet0_mdio_pads is not None:
            self.cpu_params.update(
                o_ENET0_MDIO_MDC = ps7_enet0_mdio_pads.mdc,
                i_ENET0_MDIO_I   = ps7_enet0_mdio_pads.i,
                o_ENET0_MDIO_O   = ps7_enet0_mdio_pads.o,
                o_ENET0_MDIO_T   = ps7_enet0_mdio_pads.t
            )

        # Enet0 ------------------------------------------------------------------------------------
        ps7_enet0_pads = platform.request("ps7_enet0", loose=True)
        if ps7_enet0_pads is not None:
            self.cpu_params.update(
                    o_ENET0_GMII_TX_EN  = ps7_enet0_pads.tx_en,
                    o_ENET0_GMII_TX_ER  = ps7_enet0_pads.tx_er,
                    o_ENET0_GMII_TXD    = ps7_enet0_pads.txd,
                    i_ENET0_GMII_COL    = ps7_enet0_pads.col,
                    i_ENET0_GMII_CRS    = ps7_enet0_pads.crs,
                    i_ENET0_GMII_RX_CLK = ps7_enet0_pads.rx_clk,
                    i_ENET0_GMII_RX_DV  = ps7_enet0_pads.rx_dv,
                    i_ENET0_GMII_RX_ER  = ps7_enet0_pads.rx_er,
                    i_ENET0_GMII_TX_CLK = ps7_enet0_pads.tx_clk,
                    i_ENET0_GMII_RXD    = ps7_enet0_pads.rxd
                )

        # SDIO0 ------------------------------------------------------------------------------------
        ps7_sdio0_pads = platform.request("ps7_sdio0", loose=True)
        if ps7_sdio0_pads is not None:
            self.cpu_params.update(
                o_SDIO0_CLK     = ps7_sdio0_pads.clk,
                i_SDIO0_CLK_FB  = ps7_sdio0_pads.clk_fb,
                o_SDIO0_CMD_O   = ps7_sdio0_pads.cmd_o,
                i_SDIO0_CMD_I   = ps7_sdio0_pads.cmd_i,
                o_SDIO0_CMD_T   = ps7_sdio0_pads.cmd_t,
                o_SDIO0_DATA_O  = ps7_sdio0_pads.data_o,
                i_SDIO0_DATA_I  = ps7_sdio0_pads.data_i,
                o_SDIO0_DATA_T  = ps7_sdio0_pads.data_t,
                o_SDIO0_LED     = ps7_sdio0_pads.led,
                o_SDIO0_BUSPOW  = ps7_sdio0_pads.buspow,
                o_SDIO0_BUSVOLT = ps7_sdio0_pads.busvolt,
            )

        # SDIO0_CD ---------------------------------------------------------------------------------
        ps7_sdio0_cd_pads = platform.request("ps7_sdio0_cd", loose=True)
        if ps7_sdio0_cd_pads is not None:
            self.cpu_params.update(i_SDIO0_CDN = ps7_sdio0_cd_pads.cdn)

        # SDIO0_WP ---------------------------------------------------------------------------------
        ps7_sdio0_wp_pads = platform.request("ps7_sdio0_wp", loose=True)
        if ps7_sdio0_wp_pads is not None:
            self.cpu_params.update(i_SDIO0_WP = ps7_sdio0_wp_pads.wp)

    def set_ps7_xci(self, xci):
        # Add .xci as Vivado IP and set ps7_name from .xci filename.
        self.ps7_xci  = xci
        self.ps7_name = os.path.splitext(os.path.basename(xci))[0]
        self.platform.add_ip(xci)

    def add_ps7_config(self, config):
        # Check that PS7 has been set.
        if self.ps7_name is None:
            raise Exception("Please set PS7 with set_ps7 method first.")
        # Config must be provided as a config, value dict.
        assert isinstance(config, dict)
        # Add configs to PS7.
        self.ps7_tcl.append("set_property -dict [list \\")
        for config, value in config.items():
            self.ps7_tcl.append("CONFIG.{} {} \\".format(config, '{{' + str(value) + '}}'))
        self.ps7_tcl.append(f"] [get_ips {self.ps7_name}]")

    def set_ps7(self, name=None, xci=None, preset=None, config=None):
        # Check that PS7 has not already been set.
        if self.ps7_name is not None:
            raise Exception(f"PS7 has already been set to {self.ps7_name}.")
        # when preset is a TCL file -> drop extension before using as the ps7 name
        #                              and use absolute path
        preset_tcl = False
        if preset is not None:
            preset_split = preset.split('.')
            if len(preset_split) > 1 and preset_split[-1] == "tcl":
                name = preset_split[0]
                preset = os.path.abspath(preset)
                preset_tcl = True
        self.ps7_name = preset if name is None else name

        # User should provide an .xci file, preset_name or config dict but not all at once.
        if (xci is not None) and (preset is not None):
            raise Exception("PS7 .xci and preset specified, please only provide one.")

        # User provides an .xci file...
        if xci is not None:
            self.set_ps7_xci(xci)

        # User provides a preset or/and config
        else:
            self.ps7_tcl.append(f"set ps7 [create_ip -vendor xilinx.com -name processing_system7 -module_name {self.ps7_name}]")
            if preset is not None:
                assert isinstance(preset, str)
                if preset_tcl:
                    self.ps7_tcl.append("source {}".format(preset))
                    self.ps7_tcl.append("set ps7_cfg [apply_preset IPINST]")
                    self.ps7_tcl.append("set_property -dict $ps7_cfg [get_ips {}]".format(self.ps7_name))
                else:
                    self.ps7_tcl.append("set_property -dict [list CONFIG.preset {}] [get_ips {}]".format("{{" + preset + "}}", self.ps7_name))
            if config is not None:
                self.add_ps7_config(config)

    # AXI General Purpose Master -------------------------------------------------------------------

    def add_axi_gp_master(self):
        assert len(self.axi_gp_masters) < 2
        n       = len(self.axi_gp_masters)
        axi_gpn = axi.AXIInterface(data_width=32, address_width=32, id_width=12)
        self.axi_gp_masters.append(axi_gpn)
        self.cpu_params.update({
            # AXI GP clk.
            f"i_M_AXI_GP{n}_ACLK"    : ClockSignal("ps7"),

            # AXI GP aw.
            f"o_M_AXI_GP{n}_AWVALID" : axi_gpn.aw.valid,
            f"i_M_AXI_GP{n}_AWREADY" : axi_gpn.aw.ready,
            f"o_M_AXI_GP{n}_AWADDR"  : axi_gpn.aw.addr,
            f"o_M_AXI_GP{n}_AWBURST" : axi_gpn.aw.burst,
            f"o_M_AXI_GP{n}_AWLEN"   : axi_gpn.aw.len,
            f"o_M_AXI_GP{n}_AWSIZE"  : axi_gpn.aw.size,
            f"o_M_AXI_GP{n}_AWID"    : axi_gpn.aw.id,
            f"o_M_AXI_GP{n}_AWLOCK"  : axi_gpn.aw.lock,
            f"o_M_AXI_GP{n}_AWPROT"  : axi_gpn.aw.prot,
            f"o_M_AXI_GP{n}_AWCACHE" : axi_gpn.aw.cache,
            f"o_M_AXI_GP{n}_AWQOS"   : axi_gpn.aw.qos,

            # AXI GP w.
            f"o_M_AXI_GP{n}_WVALID"  : axi_gpn.w.valid,
            f"o_M_AXI_GP{n}_WLAST"   : axi_gpn.w.last,
            f"i_M_AXI_GP{n}_WREADY"  : axi_gpn.w.ready,
            f"o_M_AXI_GP{n}_WID"     : axi_gpn.w.id,
            f"o_M_AXI_GP{n}_WDATA"   : axi_gpn.w.data,
            f"o_M_AXI_GP{n}_WSTRB"   : axi_gpn.w.strb,

            # AXI GP b.
            f"i_M_AXI_GP{n}_BVALID"  : axi_gpn.b.valid,
            f"o_M_AXI_GP{n}_BREADY"  : axi_gpn.b.ready,
            f"i_M_AXI_GP{n}_BID"     : axi_gpn.b.id,
            f"i_M_AXI_GP{n}_BRESP"   : axi_gpn.b.resp,

            # AXI GP ar.
            f"o_M_AXI_GP{n}_ARVALID" : axi_gpn.ar.valid,
            f"i_M_AXI_GP{n}_ARREADY" : axi_gpn.ar.ready,
            f"o_M_AXI_GP{n}_ARADDR"  : axi_gpn.ar.addr,
            f"o_M_AXI_GP{n}_ARBURST" : axi_gpn.ar.burst,
            f"o_M_AXI_GP{n}_ARLEN"   : axi_gpn.ar.len,
            f"o_M_AXI_GP{n}_ARID"    : axi_gpn.ar.id,
            f"o_M_AXI_GP{n}_ARLOCK"  : axi_gpn.ar.lock,
            f"o_M_AXI_GP{n}_ARSIZE"  : axi_gpn.ar.size,
            f"o_M_AXI_GP{n}_ARPROT"  : axi_gpn.ar.prot,
            f"o_M_AXI_GP{n}_ARCACHE" : axi_gpn.ar.cache,
            f"o_M_AXI_GP{n}_ARQOS"   : axi_gpn.ar.qos,

            # AXI GP r.
            f"i_M_AXI_GP{n}_RVALID"  : axi_gpn.r.valid,
            f"o_M_AXI_GP{n}_RREADY"  : axi_gpn.r.ready,
            f"i_M_AXI_GP{n}_RLAST"   : axi_gpn.r.last,
            f"i_M_AXI_GP{n}_RID"     : axi_gpn.r.id,
            f"i_M_AXI_GP{n}_RRESP"   : axi_gpn.r.resp,
            f"i_M_AXI_GP{n}_RDATA"   : axi_gpn.r.data,
        })
        return axi_gpn

    # AXI General Purpose Slave --------------------------------------------------------------------

    def add_axi_gp_slave(self):
        raise NotImplementedError

    # AXI High Performance Slave -------------------------------------------------------------------

    def add_axi_hp_slave(self):
        assert len(self.axi_hp_slaves) < 4
        n       = len(self.axi_hp_slaves)
        axi_hpn = axi.AXIInterface(data_width=64, address_width=32, id_width=6)
        self.axi_hp_slaves.append(axi_hpn)
        self.cpu_params.update({
            # AXI HP0 clk.
            f"i_S_AXI_HP{n}_ACLK"    : ClockSignal("ps7"),

            # AXI HP0 aw.
            f"i_S_AXI_HP{n}_AWVALID" : axi_hpn.aw.valid,
            f"o_S_AXI_HP{n}_AWREADY" : axi_hpn.aw.ready,
            f"i_S_AXI_HP{n}_AWADDR"  : axi_hpn.aw.addr,
            f"i_S_AXI_HP{n}_AWBURST" : axi_hpn.aw.burst,
            f"i_S_AXI_HP{n}_AWLEN"   : axi_hpn.aw.len,
            f"i_S_AXI_HP{n}_AWSIZE"  : axi_hpn.aw.size,
            f"i_S_AXI_HP{n}_AWID"    : axi_hpn.aw.id,
            f"i_S_AXI_HP{n}_AWLOCK"  : axi_hpn.aw.lock,
            f"i_S_AXI_HP{n}_AWPROT"  : axi_hpn.aw.prot,
            f"i_S_AXI_HP{n}_AWCACHE" : axi_hpn.aw.cache,
            f"i_S_AXI_HP{n}_AWQOS"   : axi_hpn.aw.qos,

            # AXI HP0 w.
            f"i_S_AXI_HP{n}_WVALID" : axi_hpn.w.valid,
            f"i_S_AXI_HP{n}_WLAST"  : axi_hpn.w.last,
            f"o_S_AXI_HP{n}_WREADY" : axi_hpn.w.ready,
            f"i_S_AXI_HP{n}_WID"    : axi_hpn.w.id,
            f"i_S_AXI_HP{n}_WDATA"  : axi_hpn.w.data,
            f"i_S_AXI_HP{n}_WSTRB"  : axi_hpn.w.strb,

            # AXI HP0 b.
            f"o_S_AXI_HP{n}_BVALID" : axi_hpn.b.valid,
            f"i_S_AXI_HP{n}_BREADY" : axi_hpn.b.ready,
            f"o_S_AXI_HP{n}_BID"    : axi_hpn.b.id,
            f"o_S_AXI_HP{n}_BRESP"  : axi_hpn.b.resp,

            # AXI HP0 ar.
            f"i_S_AXI_HP{n}_ARVALID" : axi_hpn.ar.valid,
            f"o_S_AXI_HP{n}_ARREADY" : axi_hpn.ar.ready,
            f"i_S_AXI_HP{n}_ARADDR"  : axi_hpn.ar.addr,
            f"i_S_AXI_HP{n}_ARBURST" : axi_hpn.ar.burst,
            f"i_S_AXI_HP{n}_ARLEN"   : axi_hpn.ar.len,
            f"i_S_AXI_HP{n}_ARID"    : axi_hpn.ar.id,
            f"i_S_AXI_HP{n}_ARLOCK"  : axi_hpn.ar.lock,
            f"i_S_AXI_HP{n}_ARSIZE"  : axi_hpn.ar.size,
            f"i_S_AXI_HP{n}_ARPROT"  : axi_hpn.ar.prot,
            f"i_S_AXI_HP{n}_ARCACHE" : axi_hpn.ar.cache,
            f"i_S_AXI_HP{n}_ARQOS"   : axi_hpn.ar.qos,

            # AXI HP0 r.
            f"o_S_AXI_HP{n}_RVALID" : axi_hpn.r.valid,
            f"i_S_AXI_HP{n}_RREADY" : axi_hpn.r.ready,
            f"o_S_AXI_HP{n}_RLAST"  : axi_hpn.r.last,
            f"o_S_AXI_HP{n}_RID"    : axi_hpn.r.id,
            f"o_S_AXI_HP{n}_RRESP"  : axi_hpn.r.resp,
            f"o_S_AXI_HP{n}_RDATA"  : axi_hpn.r.data,
        })
        return axi_hpn

    def do_finalize(self):
        if self.ps7_name is None:
            raise Exception("PS7 must be set with set_ps7 or set_ps7_xci methods.")
        if len(self.ps7_tcl):
            self.ps7_tcl += [
                f"upgrade_ip [get_ips {self.ps7_name}]",
                f"generate_target all [get_ips {self.ps7_name}]",
                f"synth_ip [get_ips {self.ps7_name}]"
            ]
            self.platform.toolchain.pre_synthesis_commands += self.ps7_tcl
        self.specials += Instance(self.ps7_name, **self.cpu_params)
