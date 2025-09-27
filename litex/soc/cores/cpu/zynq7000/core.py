#
# This file is part of LiteX.
#
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# Copyright (c) 2022 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *

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
    csr_decode           = True # AXI address is decoded in AXI2Wishbone, offset needs to be added in Software.

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "sram": 0x0010_0000,  # DDR in fact
            "csr":  0x4000_0000,  # default GP0 address on Zynq
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

        # PS7 peripherals.
        self.can_use        = []
        self.i2c_use        = []
        self.spi_use        = []

        # PS7 EMIO GPIOs (starts at 54).
        self._emio_use      = 0          # EMIO/GPIOs reserved/used.
        self._emio_pads_i   = Signal(64)
        self._emio_pads_o   = Signal(64)
        self._emio_pads_t   = Signal(64)

        # [ 7: 0]: SPI Numbers [68:61]
        # [15: 8]: SPI Numbers [91:84]
        self.interrupt      = Signal(16)

        # # #

        # PS7 Clocking.
        self.cd_ps7 = ClockDomain()

        # PS7 (Minimal) ----------------------------------------------------------------------------
        self.ps7_name   = None
        self.ps7_tcl    = []
        self.config     = {
            # Enable interrupts by default
            "PCW_USE_FABRIC_INTERRUPT"  : 1,
            "PCW_IRQ_F2P_INTR"          : 1,
            "PCW_NUM_F2P_INTR_INPUTS"   : 16,

            # Enable EMIO GPIO by default
            "PCW_GPIO_EMIO_GPIO_ENABLE" :  1,
            "PCW_GPIO_EMIO_GPIO_IO"     : 64,
        }
        ps7_rst_n       = Signal()
        ps7_ddram_pads  = platform.request("ps7_ddram")
        self.cpu_params = dict(
            # Clk / Rst.
            io_PS_CLK   = platform.request("ps7_clk"),
            io_PS_PORB  = platform.request("ps7_porb"),
            io_PS_SRSTB = platform.request("ps7_srstb"),

            # MIO.
            io_MIO = platform.request("ps7_mio"),

            # EMIO.
            i_GPIO_I = self._emio_pads_i,
            o_GPIO_O = self._emio_pads_o,
            o_GPIO_T = self._emio_pads_t,

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

            # Interrupts PL -> PS.
            i_IRQ_F2P       = self.interrupt,

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

        # GP0 as Bus master ------------------------------------------------------------------------
        self.pbus = self.add_axi_gp_master()
        self.periph_buses.append(self.pbus)

    def set_ps7_xci(self, xci):
        # Add .xci as Vivado IP and set ps7_name from .xci filename.
        self.ps7_xci  = xci
        self.ps7_name = os.path.splitext(os.path.basename(xci))[0]
        self.platform.add_ip(xci)

    def add_ps7_config(self, config):
        # Config must be provided as a config, value dict.
        assert isinstance(config, dict)
        self.config.update(config)

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
        axi_gpn = axi.AXIInterface(
            data_width    = 32,
            address_width = 32,
            id_width      = 12,
            version       = "axi3"
        )
        self.axi_gp_masters.append(axi_gpn)

        self.add_ps7_config({
            f"PCW_USE_M_AXI_GP{n}":                  1,
            #f"PCW_M_AXI_GP{n}_FREQMHZ":              100, # FIXME: parameter?
            f"PCW_M_AXI_GP{n}_ID_WIDTH":             12,
            f"PCW_M_AXI_GP{n}_ENABLE_STATIC_REMAP":  0,
            f"PCW_M_AXI_GP{n}_SUPPORT_NARROW_BURST": 0,
            f"PCW_M_AXI_GP{n}_THREAD_ID_WIDTH":      12,
        })

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

    def add_axi_gp_slave(self, clock_domain="ps7"):
        assert len(self.axi_gp_slaves) < 2
        n       = len(self.axi_gp_slaves)
        axi_gpn = axi.AXIInterface(
            data_width    = 32,
            address_width = 32,
            id_width      = 12,
            version       = "axi3",
            clock_domain  = clock_domain
        )
        self.axi_gp_slaves.append(axi_gpn)
        self.cpu_params.update({
            #AXI S GP clk.
            f"i_S_AXI_GP{n}_ACLK" : ClockSignal(clock_domain),

            #AXI S GP aw.
            f"i_S_AXI_GP{n}_AWVALID" : axi_gpn.aw.valid,
            f"i_S_AXI_GP{n}_AWADDR"  : axi_gpn.aw.addr,
            f"o_S_AXI_GP{n}_AWREADY" : axi_gpn.aw.ready,
            f"i_S_AXI_GP{n}_AWBURST" : axi_gpn.aw.burst,
            f"i_S_AXI_GP{n}_AWLEN"   : axi_gpn.aw.len,
            f"i_S_AXI_GP{n}_AWSIZE"  : axi_gpn.aw.size,
            f"i_S_AXI_GP{n}_AWID"    : axi_gpn.aw.id,
            f"i_S_AXI_GP{n}_AWLOCK"  : axi_gpn.aw.lock,
            f"i_S_AXI_GP{n}_AWPROT"  : axi_gpn.aw.prot,
            f"i_S_AXI_GP{n}_AWCACHE" : axi_gpn.aw.cache,
            f"i_S_AXI_GP{n}_AWQOS"   : axi_gpn.aw.qos,

            #AXI S GP w.
            f"i_S_AXI_GP{n}_WVALID"  : axi_gpn.w.valid,
            f"i_S_AXI_GP{n}_WLAST"   : axi_gpn.w.last,
            f"o_S_AXI_GP{n}_WREADY"  : axi_gpn.w.ready,
            f"i_S_AXI_GP{n}_WID"     : axi_gpn.w.id,
            f"i_S_AXI_GP{n}_WDATA"   : axi_gpn.w.data,
            f"i_S_AXI_GP{n}_WSTRB"   : axi_gpn.w.strb,

            #AXI S GP b.
            f"o_S_AXI_GP{n}_BVALID"  : axi_gpn.b.valid,
            f"i_S_AXI_GP{n}_BREADY"  : axi_gpn.b.ready,
            f"o_S_AXI_GP{n}_BID"     : axi_gpn.b.id,
            f"o_S_AXI_GP{n}_BRESP"   : axi_gpn.b.resp,

            #AXI S GP ar.
            f"i_S_AXI_GP{n}_ARVALID" : axi_gpn.ar.valid,
            f"i_S_AXI_GP{n}_ARADDR"  : axi_gpn.ar.addr,
            f"o_S_AXI_GP{n}_ARREADY" : axi_gpn.ar.ready,
            f"i_S_AXI_GP{n}_ARBURST" : axi_gpn.ar.burst,
            f"i_S_AXI_GP{n}_ARLEN"   : axi_gpn.ar.len,
            f"i_S_AXI_GP{n}_ARSIZE"  : axi_gpn.ar.size,
            f"i_S_AXI_GP{n}_ARID"    : axi_gpn.ar.id,
            f"i_S_AXI_GP{n}_ARLOCK"  : axi_gpn.ar.lock,
            f"i_S_AXI_GP{n}_ARPROT"  : axi_gpn.ar.prot,
            f"i_S_AXI_GP{n}_ARCACHE" : axi_gpn.ar.cache,
            f"i_S_AXI_GP{n}_ARQOS"   : axi_gpn.ar.qos,

            #AXI S GP r.
            f"o_S_AXI_GP{n}_RVALID"  : axi_gpn.r.valid,
            f"i_S_AXI_GP{n}_RREADY"  : axi_gpn.r.ready,
            f"o_S_AXI_GP{n}_RLAST"   : axi_gpn.r.last,
            f"o_S_AXI_GP{n}_RID"     : axi_gpn.r.id,
            f"o_S_AXI_GP{n}_RRESP"   : axi_gpn.r.resp,
            f"o_S_AXI_GP{n}_RDATA"   : axi_gpn.r.data,
        })
        return axi_gpn

    # AXI High Performance Slave -------------------------------------------------------------------

    def add_axi_hp_slave(self, clock_domain="ps7", clock_freq=None, data_width=64):
        assert len(self.axi_hp_slaves) < 4
        n       = len(self.axi_hp_slaves)
        axi_hpn = axi.AXIInterface(
            data_width    = data_width,
            address_width = 32,
            id_width      = 6,
            version       = "axi3",
            clock_domain  = clock_domain
        )
        self.axi_hp_slaves.append(axi_hpn)

        # Enable HPx peripheral and set data_width.
        self.add_ps7_config({
            f"PCW_USE_S_AXI_HP{n}"        : 1,
            f"PCW_S_AXI_HP{n}_DATA_WIDTH" : data_width,
            f"PCW_S_AXI_HP{n}_ID_WIDTH"   : 6,
        })

        # If provided: set HPx frequency configuration.
        if clock_freq is not None:
            self.add_ps7_config({
                f"PCW_S_AXI_HP{n}_FREQMHZ" : int(clock_freq / 1e6),
            })

        self.cpu_params.update({
            # AXI HP0 clk.
            f"i_S_AXI_HP{n}_ACLK"    : ClockSignal(clock_domain),

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

    """
    Enable CANx peripheral. Peripheral may be optionally set
    Attributes
    ==========
    n: int
        CAN id (0, 1)
    pads:
        Physicals pads (tx and rx)
    ext_clk: int or None
        When unset/None CAN is clocked by internal clock (IO PLL).
        value must be 0 <= ext_clk < 54.
    ext_clk_freq: float
        when ext_clk is set, external clock frequency (Hz)
    """
    def add_can(self, n, pads, ext_clk=None, ext_clk_freq=None):
        assert n < 2 and not n in self.can_use
        assert ext_clk is None or (ext_clk < 54 and ext_clk is not None)
        assert pads is not None

        # Mark as used
        self.can_use.append(n)

        # PS7 configuration.
        self.add_ps7_config({
            f"PCW_CAN{n}_PERIPHERAL_ENABLE": 1,
            f"PCW_CAN{n}_CAN{n}_IO":         "EMIO",
            f"PCW_CAN{n}_GRP_CLK_ENABLE":    {True: 0, False: 1}[ext_clk == None],
        })

        if ext_clk:
            self.add_ps7_config({
                f"PCW_CAN{n}_GRP_CLK_IO"         : f"MIO {ext_clk}",
                f"PCW_CAN{n}_PERIPHERAL_FREQMHZ" : int(clk_freq / 1e6),
            })

        # PS7 connections.
        self.cpu_params.update({
            f"i_CAN{n}_PHY_RX": pads.rx,
            f"o_CAN{n}_PHY_TX": pads.tx,
        })

    """
    Connect and Enables SPIn controler (may be via PS7 MIO or PL EMIO).
    Attributes
    ==========
    n: int
        controler ID 0/1
    pads_or_mio_group: Record or str:
        When pads_or_mio_group is:
        - a Record, SPIn controler is configured to uses EMIO
        - a str, SPIn controler is configured to uses PS7 MIO. str must
        be the name of the MIO group: "MIO xx .. yy"
    """
    def add_spi(self, n, pads_or_mio_group, ss1_en=False, ss2_en=False):
        assert n < 2 and not n in self.spi_use
        assert pads_or_mio_group is not None

        # Mark as used.
        self.spi_use.append(n)

        # When SPI is used via PS7 MIO pads_or_mio_group is a string
        # otherwise a resource.
        io_type = {True: pads_or_mio_group, False: "EMIO"}[isinstance(pads_or_mio_group, str)]

        # MIO IOs must be "MIO xx .. yy"
        assert not (io_type != "EMIO" and re.match("MIO \d\d .. \d\d", io_type) is None)

        # In EMIO check if Record contains cs1_n/cs2_n
        if io_type == "EMIO":
            ss1_en = hasattr(pads_or_mio_group, "cs1_n")
            ss2_en = hasattr(pads_or_mio_group, "cs2_n")

        # PS7 configuration.
        self.add_ps7_config({
            f"PCW_SPI{n}_PERIPHERAL_ENABLE" : 1,
            f"PCW_SPI{n}_SPI{n}_IO"         : io_type,
            f"PCW_SPI{n}_GRP_SS1_ENABLE"    : {True: 1, False: 0}[io_type == "EMIO" or ss1_en],
            f"PCW_SPI{n}_GRP_SS2_ENABLE"    : {True: 1, False: 0}[io_type == "EMIO" or ss2_en],
        })

        # Inject SPIn configuration to use it via csv/json
        LiteXContext.top.add_constant(f"CONFIG_PS7_SPI{n}_ENABLE", 1)
        LiteXContext.top.add_constant(f"CONFIG_PS7_SPI{n}_IO",     io_type)

        # SPIn interface is only exposed when controler is set to EMIO.
        if io_type == "EMIO":
            # Signals.
            sclk = TSTriple()
            mosi = TSTriple()
            miso = TSTriple()
            ss   = TSTriple()

            # Physical connections.
            self.specials += [
                Instance("IOBUF",
                    i_I   = mosi.o,
                    o_O   = mosi.i,
                    i_T   = mosi.oe,
                    io_IO = pads_or_mio_group.mosi
                ),
                Instance("IOBUF",
                    i_I   = miso.o,
                    o_O   = miso.i,
                    i_T   = miso.oe,
                    io_IO = pads_or_mio_group.miso
                ),
                Instance("IOBUF",
                    i_I   = sclk.o,
                    o_O   = sclk.i,
                    i_T   = sclk.oe,
                    io_IO = pads_or_mio_group.clk
                ),
                Instance("IOBUF",
                    i_I   = ss.o,
                    o_O   = ss.i,
                    i_T   = ss.oe,
                    io_IO = pads_or_mio_group.cs_n
                ),
            ]

            # PS7 connections.
            self.cpu_params.update({
                # SCLK
                f"i_SPI{n}_SCLK_I" : sclk.i,
                f"o_SPI{n}_SCLK_O" : sclk.o,
                f"o_SPI{n}_SCLK_T" : sclk.oe,
                # MOSI
                f"i_SPI{n}_MOSI_I" : mosi.i,
                f"o_SPI{n}_MOSI_O" : mosi.o,
                f"o_SPI{n}_MOSI_T" : mosi.oe,
                # MISO
                f"i_SPI{n}_MISO_I" : miso.i,
                f"o_SPI{n}_MISO_O" : miso.o,
                f"o_SPI{n}_MISO_T" : miso.oe,
                # SSx
                f"i_SPI{n}_SS_I"   : ss.i,
                f"o_SPI{n}_SS_O"   : ss.o,
                f"o_SPI{n}_SS_T"   : ss.oe,
                f"o_SPI{n}_SS1_O"  : pads_or_mio_group.cs1_n if ss1_en else Open(),
                f"o_SPI{n}_SS2_O"  : pads_or_mio_group.cs2_n if ss2_en else Open(),
            })

    """
    Connect and Enables I2C controler (may be via PS7 MIO or PL EMIO).
    Attributes
    ==========
    n: int
        controler ID 0/1
    pads_or_mio_group: Record or str:
        When pads is a Record, I2Cn controler is configured to uses EMIO
        When pads is a str, I2Cn controler is configured to uses PS7 MIO. str must
        be "MIO xx .. yy"
    """
    def add_i2c(self, n, pads_or_mio_group):
        assert n < 2 and not n in self.i2c_use
        assert pads_or_mio_group is not None

        # Mark as used.
        self.i2c_use.append(n)

        # When I2C is used via PS7 MIO pads_or_mio_group is a string
        # otherwise a resource.
        io_type = {True: pads_or_mio_group, False: "EMIO"}[isinstance(pads_or_mio_group, str)]

        # MIO IOs must be "MIO xx .. yy"
        assert not (io_type != "EMIO" and re.match("MIO \d\d .. \d\d", io_type) is None)

        # PS7 configuration.
        self.add_ps7_config({
            f"PCW_I2C{n}_PERIPHERAL_ENABLE" : 1,
            f"PCW_I2C{n}_I2C{n}_IO"         : io_type,
        })

        # Inject I2Cn configuration to use it via csv/json
        LiteXContext.top.add_constant(f"CONFIG_PS7_I2C{n}_ENABLE", 1)
        LiteXContext.top.add_constant(f"CONFIG_PS7_I2C{n}_IO",     io_type)

        # I2Cn interface is only exposed when controler is set to EMIO.
        if io_type == "EMIO":
            # Signals.
            scl = TSTriple()
            sda = TSTriple()

            # Physical connections.
            self.specials += [
                Instance("IOBUF",
                    i_I   = sda.o,
                    o_O   = sda.i,
                    i_T   = sda.oe,
                    io_IO = pads_or_mio_group.sda
                ),
                Instance("IOBUF",
                    i_I   = scl.o,
                    o_O   = scl.i,
                    i_T   = scl.oe,
                    io_IO = pads_or_mio_group.scl
                ),
            ]

            # PS7 connections.
            self.cpu_params.update({
                f"i_I2C{n}_SCL_I" : scl.i,
                f"o_I2C{n}_SCL_O" : scl.o,
                f"o_I2C{n}_SCL_T" : scl.oe,
                f"i_I2C{n}_SDA_I" : sda.i,
                f"o_I2C{n}_SDA_O" : sda.o,
                f"o_I2C{n}_SDA_T" : sda.oe,
            })

    """
    Connect Signal,TSTriple or pads to the EMIO interface.
    Attributes
    ==========
    pads: physical pads (request/request_all), Signal(x), TSTriple or list of TSTriple.
    pads_type: str (signal, pads)
        pads means a physical signal, signal means any Signals internally
        defined (may be connected to a physical pad or a Core).
    pads_dir: str (in, out, inout)
        pads direction, only used for signals.
    """
    def add_gpios(self, pads, pads_type="signal", pads_dir="inout"):
        assert pads_type in ["signal", "pads"]
        assert pads_dir  in ["in", "out", "inout"]
        assert len(pads) + self._emio_use <= len(self._emio_pads_i)

        def _connect_ios(p=None, p_i=None, p_o=None, p_t=None):
            if p is not None:
                assert p_i is None and p_o is None and p_t is None
                assert self._emio_use < len(self._emio_pads_i)

                # Uses intermediate signals for IOBUF -> Zynq7000
                # to avoid conflicts wire vs reg for the same signal.
                p_i = Signal()
                self.specials += Instance("IOBUF",
                    i_I   = self._emio_pads_o[self._emio_use],
                    o_O   = p_i,
                    i_T   = self._emio_pads_t[self._emio_use],
                    io_IO = p,
                )

            if p_i is not None:
                self.comb += self._emio_pads_i[self._emio_use].eq(p_i)
            if p_o is not None:
                self.comb += p_o.eq(self._emio_pads_o[self._emio_use])
            if p_t is not None:
                self.comb += p_t.eq(self._emio_pads_t[self._emio_use])
            self._emio_use += 1

        # TSTriple is not iterable.
        # Directly connects _I/_O/_T and return.
        if type(pads) == TSTriple:
            _connect_ios(p_i=pads.i, p_o=pads.o, p_t=pads.oe)
            return # Nothing to do

        # When pads is type Cat (from request_all)
        # convert it to a list to have a clean verilog.
        if pads_type == "pads" and isinstance(pads, Cat):
            pads = [p for p in pads.l]

        for (i, p) in enumerate(pads):
            if type(p) == TSTriple: # bypass direction check
                                    # In this mode .o/.i are considered having
                                    # a size == 1
                _connect_ios(p_i=p.i, p_o=p.o, p_t=p.oe)
            elif pads_type == "pads": # Direct connection
                _connect_ios(p=p)
            else: # internal signal
                _connect_ios(
                    p_i = p,
                    p_o = {True: p, False: None}[pads_dir in ["inout", "out"]],
                )

    def do_finalize(self):
        if self.ps7_name is None:
            raise Exception("PS7 must be set with set_ps7 or set_ps7_xci methods.")
        if len(self.ps7_tcl):
            # Add configs to PS7.
            if len(self.config):
                self.ps7_tcl.append("set_property -dict [list \\")
                for config, value in self.config.items():
                    self.ps7_tcl.append("CONFIG.{} {} \\".format(
                        config, '{{' + str(value) + '}}'))
                self.ps7_tcl.append(f"] [get_ips {self.ps7_name}]")

            self.ps7_tcl += [
                f"upgrade_ip [get_ips {self.ps7_name}]",
                f"generate_target all [get_ips {self.ps7_name}]",
                f"synth_ip [get_ips {self.ps7_name}]"
            ]
            self.platform.toolchain.pre_synthesis_commands += self.ps7_tcl
        self.specials += Instance(self.ps7_name, **self.cpu_params)
