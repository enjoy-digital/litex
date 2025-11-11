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

from litex.build.xilinx.vivado import XilinxVivadoToolchain

from litex.gen import *

from litex.soc.interconnect import axi
from litex.soc.interconnect.csr import CSRStatus, CSRField

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
        self.reserve_pads   = isinstance(platform.toolchain, XilinxVivadoToolchain)
        self.reset          = Signal()
        self.periph_buses   = []    # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses   = []    # Memory buses (Connected directly to LiteDRAM).

        self.axi_gp_masters = []    # General Purpose AXI Masters.
        self.axi_gp_slaves  = []    # General Purpose AXI Slaves.
        self.axi_hp_slaves  = []    # High Performance AXI Slaves.

        # PS7 peripherals.
        self.can_use        = []
        self.i2c_use        = []
        self.gem_mac        = {}          # GEM MAC reserved ports.
        self.sdio_use       = []          # SDx reserved ports.
        self.spi_use        = []
        self.uart_use       = []

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
        ps7_ddram_pads  = platform.request("ps7_ddram", reserve=self.reserve_pads)
        self.cpu_params = dict(
            # Clk / Rst.
            io_PS_CLK   = platform.request("ps7_clk", reserve=self.reserve_pads),
            io_PS_PORB  = platform.request("ps7_porb", reserve=self.reserve_pads),
            io_PS_SRSTB = platform.request("ps7_srstb", reserve=self.reserve_pads),

            # MIO.
            io_MIO = platform.request("ps7_mio", reserve=self.reserve_pads),

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
    Connect and Enables UARTn controler (may be via PS7 MIO or PL EMIO).
    Attributes
    ==========
    n: int
        controler ID 0/1
    pads_or_mio_group: Record or str:
        When pads_or_mio_group is:
        - a Record, UARTn controler is configured to uses EMIO
        - a str, UARTn controler is configured to uses PS7 MIO. str must
        be the name of the MIO group: "MIO xx .. yy"
    """
    def add_uart(self, n, pads_or_mio_group):
        assert n < 2 and not n in self.uart_use
        assert pads_or_mio_group is not None

        # Mark as used.
        self.uart_use.append(n)

        # When UART is used via PS7 MIO pads_or_mio_group is a string
        # otherwise a resource.
        io_type = {True: pads_or_mio_group, False: "EMIO"}[isinstance(pads_or_mio_group, str)]

        # MIO IOs must be "MIO xx .. yy"
        assert not (io_type != "EMIO" and re.match("MIO \d\d .. \d\d", io_type) is None)

        # PS7 configuration.
        self.add_ps7_config({
            f"PCW_UART{n}_PERIPHERAL_ENABLE" : 1,
            f"PCW_UART{n}_GRP_FULL_ENABLE"   : 0, # FIXME: adds control signals
            f"PCW_UART{n}_UART{n}_IO"        : io_type,
        })

        # Inject UARTn configuration to use it via csv/json
        LiteXContext.top.add_constant(f"CONFIG_PS7_UART{n}_ENABLE", 1)
        LiteXContext.top.add_constant(f"CONFIG_PS7_UART{n}_IO",     io_type)

        # UARTn interface is only exposed when controler is set to EMIO.
        if io_type == "EMIO":
            # PS7 connections.
            self.cpu_params.update({
                f"o_UART{n}_TX" : pads_or_mio_group.tx,
                f"i_UART{n}_RX" : pads_or_mio_group.rx,
            })

    """
    Connect and Enables SDn controler (may be via PS7 MIO or PL EMIO).
    Attributes
    ==========
    n: int
        controler ID 0/1
    pads_or_mio_group: Record or str:
        When pads_or_mio_group is:
        - a Record, SDn controler is configured to uses EMIO
        - a str, SDn controler is configured to uses PS7 MIO. str must
        be the name of the MIO group: "MIO xx .. yy"
    card_detect: str or Signal
        card detect signal (MIO mode only)
    write_protect: str or Signal
        write protect signal (MIO mode only)
    power_control: str
        power control signal must always be a MIO x string
    """
    def add_sdio(self, n, pads_or_mio_group, card_detect=None, write_protect=None, power_control=None):
        assert n < 2 and not n in self.sdio_use
        assert pads_or_mio_group is not None

        """ Note for devicetree
        &sdhci1 {
            status = "okay";
            max-frequency = <25000000>;
            sdhci-caps-mask = <0x0 0x00200000>; /* turn off HISPD mode because we're using EMIO (see drivers/mmc/host/sdhci.h for list of capabilities mask values) */
        };
        """

        # Mark as used.
        self.sdio_use.append(n)

        # When SPI is used via PS7 MIO pads_or_mio_group is a string
        # otherwise a resource.
        io_type = {True: pads_or_mio_group, False: "EMIO"}[isinstance(pads_or_mio_group, str)]

        # Power Control signal may be left unused or connected via MIO but never EMIO
        assert power_control is None or isinstance(power_control, str)

        # EMIO mode: card_detect and write_protect must be searched in platform pads_or_mio_group
        if io_type == "EMIO":
            assert card_detect is None and write_protect is None

        # PS7 configuration.
        self.add_ps7_config({
            f"PCW_SD{n}_PERIPHERAL_ENABLE" : 1,
            f"PCW_SD{n}_SD{n}_IO"          : io_type,
        })

        # When SDx is configured in MIO mode CD/WP may be enabled/disabled
        # in EMIO mode these signals are always enabled and not configurables.
        if io_type != "EMIO":
            if card_detect is not None:
                cd_type = {True: card_detect, False: "EMIO"}[isinstance(card_detect, str)]
                self.add_ps7_config({
                    f"PCW_SD{n}_GRP_CD_ENABLE" : 1,
                    f"PCW_SD{n}_GRP_CD_IO"     : cd_type,
                })
                if cd_type == "EMIO":
                    self.cpu_params[f"i_SDIO{n}_CDN"] = card_detect

            if write_protect is not None:
                wp_type = {True: write_protect, False: "EMIO"}[isinstance(write_protect, str)]
                self.add_ps7_config({
                    f"PCW_SD{n}_GRP_WP_ENABLE" : 1,
                    f"PCW_SD{n}_GRP_WP_IO"     : wp_type,
                })
                if wp_type == "EMIO":
                    self.cpu_params[f"i_SDIO{n}_WP"] = write_protect

        # For both MIO and EMIO PW may be enabled/disabled but it is
        # always connected to an MIO pin (PS).
        if power_control is not None:
            self.add_ps7_config({
                f"PCW_SD{n}_GRP_POW_ENABLE" : 1,
                f"PCW_SD{n}_GRP_POW_IO"     : power_control,
            })

        # Inject SDn configuration to use it via csv/json
        LiteXContext.top.add_constant(f"CONFIG_PS7_SD{n}_ENABLE", 1)
        LiteXContext.top.add_constant(f"CONFIG_PS7_SD{n}_IO",     io_type)

        # when MIO mode: No more task with SDx configuration
        if io_type != "EMIO":
            return

        sd_data_o = Signal(4)
        sd_data_i = Signal(4)
        sd_data_t = Signal(4)
        sd_cmd    = TSTriple()

        for i in range(4):
            self.specials += Instance("IOBUF",
                i_I   = sd_data_o[i],
                o_O   = sd_data_i[i],
                i_T   = sd_data_t[i],
                io_IO = pads_or_mio_group.data[i],
            )
        self.specials += Instance("IOBUF",
            i_I   = sd_cmd.o,
            o_O   = sd_cmd.i,
            i_T   = sd_cmd.oe,
            io_IO = pads_or_mio_group.cmd,
        )

        # PS7 connectios.
        self.cpu_params.update({
            # CLK
            f"o_SDIO{n}_CLK"     : pads_or_mio_group.clk,
            f"i_SDIO{n}_CLK_FB"  : pads_or_mio_group.clk, # feedback clock (required?)
            # CMD
            f"o_SDIO{n}_CMD_O"   : sd_cmd.o,
            f"i_SDIO{n}_CMD_I"   : sd_cmd.i,
            f"o_SDIO{n}_CMD_T"   : sd_cmd.oe,
            # DATA
            f"o_SDIO{n}_DATA_O"  : sd_data_o,
            f"i_SDIO{n}_DATA_I"  : sd_data_i,
            f"o_SDIO{n}_DATA_T"  : sd_data_t,
            # LED
            f"o_SDIO{n}_LED"     : pads_or_mio_group.led if hasattr(pads_or_mio_group, "led") else Open(),
            # Card Detect
            f"i_SDIO{n}_CDN"     : pads_or_mio_group.cd if hasattr(pads_or_mio_group, "cd") else Constant(1, 1),
            # Write Protect
            f"i_SDIO{n}_WP"      : pads_or_mio_group.wp if hasattr(pads_or_mio_group, "wp") else Constant(0, 1),
            # Bus Power
            f"o_SDIO{n}_BUSPOW"  : pads_or_mio_group.pow if hasattr(pads_or_mio_group, "pow") else Open(),
            # Bus volt
            f"o_SDIO{n}_BUSVOLT" : pads_or_mio_group.bus_volt if hasattr(pads_or_mio_group, "bus_volt") else Open(3),
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
            if hasattr(pads_or_mio_group, "mosi"):
                self.specials += Instance("IOBUF",
                    i_I   = mosi.o,
                    o_O   = mosi.i,
                    i_T   = mosi.oe,
                    io_IO = pads_or_mio_group.mosi
                )

            if hasattr(pads_or_mio_group, "miso"):
                self.specials += Instance("IOBUF",
                    i_I   = miso.o,
                    o_O   = miso.i,
                    i_T   = miso.oe,
                    io_IO = pads_or_mio_group.miso
                )
            self.specials += [
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
    """
    Enable GEMx peripheral.
        - when if_type == rgmii, a ClockDomain called rgmii is required
        - when external_clk, a ClockDomain called gmii is required
        - when external_clk and txc_skew == 2, two ClockDomain are required: gmii and gmii_ps
        - rgmii ClockDomain must be feeded by a 200MHz signal
        - gmii and gmii_ps must be feeded by a 125MHz, 25MHz or 2.5MHz depending on ethernet speed
    ==========
    n: int
        GEM id (0, 1)
    eth_pads_or_mio_group:
        Physicals pads when EMIO or MIO xx .. yy when MIO.
    mdio_pads_or_mio_group:
        mdio/mdc pads when EMIO or MIO xx .. yy when MIO.
    clock_pads:
        Physicals tx/rx clock pads.
    if_type: str
        Physical ethernet interface (gmii, rgmii).
    internal_phyaddr: int
        gmii_to_rgmii MDIO addr (rgmii only)
    external_phyaddr: int
        external PHY MDIO addr
    external_clk: bool
        125MHz, 25MHz or 2.5MHz are applied externally or internally with an MMCM
    txc_skew: int
        tx clk edge aligned (0) or delayed by 2ns (2)
    use_idelay_ctrl: bool
        Instantiate IDELAYCTRL in design
    """
    def add_ethernet(self, n=0,
        eth_pads_or_mio_group  = None,
        mdio_pads_or_mio_group = None,
        clock_pads             = None,
        if_type                = "gmii",
        external_phyaddr       = 0,     # external PHY address

        # RGMII only.
        internal_phyaddr       = 8,     # gmii_to_rgmii address
        external_clk           = False, # When True cd_domain gmii and gmii_ps (when txc_skew = 2)
        txc_skew               = 2,     # 0: 2ns added by PHY, 2: 2ns added by MMCM
        use_idelay_ctrl        = True,
        ):
        assert n < 2 and not n in self.gem_mac
        assert eth_pads_or_mio_group is not None
        assert not (if_type == "rgmii" and clock_pads is None)
        assert if_type in ["gmii", "rgmii"]

        eth_io_type  = {True: eth_pads_or_mio_group,  False: "EMIO"}[isinstance(eth_pads_or_mio_group, str)]
        mdio_io_type = {True: mdio_pads_or_mio_group, False: "EMIO"}[isinstance(mdio_pads_or_mio_group, str)]

        eth_pads  = eth_pads_or_mio_group
        mdio_pads = mdio_pads_or_mio_group

        # ps7 configuration
        self.add_ps7_config({
            f"PCW_ENET{n}_PERIPHERAL_ENABLE"      : 1,
            f"PCW_ACT_ENET{n}_PERIPHERAL_FREQMHZ" : "125.000000",
            f"PCW_ENET{n}_ENET{n}_IO"             : eth_io_type,
        })
        if mdio_pads_or_mio_group is None:
            self.add_ps7_config({
                f"PCW_ENET{n}_GRP_MDIO_ENABLE" : 0,
            })
        else:
            self.add_ps7_config({
                f"PCW_ENET{n}_GRP_MDIO_ENABLE" : 1,
                f"PCW_ENET{n}_GRP_MDIO_IO"     : mdio_io_type,
            })

        # Inject GEMn configuration to use it via csv/json
        LiteXContext.top.add_constant(f"CONFIG_PS7_GEM{n}_ENABLE",      1)
        LiteXContext.top.add_constant(f"CONFIG_PS7_GEM{n}_TYPE",        if_type)
        LiteXContext.top.add_constant(f"CONFIG_PS7_GEM{n}_INT_PHYADDR", internal_phyaddr)
        LiteXContext.top.add_constant(f"CONFIG_PS7_GEM{n}_EXT_PHYADDR", external_phyaddr)
        LiteXContext.top.add_constant(f"CONFIG_PS7_GEM{n}_IO",          eth_io_type)
        LiteXContext.top.add_constant(f"CONFIG_PS7_GEM{n}_MDIO_ENABLE", mdio_pads_or_mio_group is not None)
        LiteXContext.top.add_constant(f"CONFIG_PS7_GEM{n}_MDIO_IO",     mdio_io_type)

        mac_params = dict()

        # ps7 MDIO connection
        if mdio_pads_or_mio_group is not None and mdio_io_type == "EMIO":
            mdio_mdc = Signal()
            mdio_i   = Signal()
            mdio_o   = Signal()
            mdio_t   = Signal()
            self.cpu_params.update({
                f"o_ENET{n}_MDIO_MDC" : mdio_mdc,
                f"i_ENET{n}_MDIO_I"   : mdio_i,
                f"o_ENET{n}_MDIO_O"   : mdio_o,
                f"o_ENET{n}_MDIO_T"   : mdio_t,
            })

            if if_type == "gmii":
                # MDIO
                self.comb += mdio_pads.mdc.eq(mdio_mdc)

                self.specials += Instance("IOBUF",
                    i_I   = mdio_o,
                    o_O   = mdio_i,
                    i_T   = mdio_t,
                    io_IO = mdio_pads.mdio
                )
            elif if_type == "rgmii":
                # PHY pads
                phys_mdio_i = Signal()
                phys_mdio_o = Signal()
                phys_mdio_t = Signal()

                self.specials += Instance("IOBUF",
                    i_I   = phys_mdio_o,
                    o_O   = phys_mdio_i,
                    i_T   = phys_mdio_t,
                    io_IO = mdio_pads.mdio
                )

                # PS -> gmii2rgmii -> PHY
                mac_params.update({
                    # PS GEM: MDIO
                    "i_mdio_gem_mdc" : mdio_mdc,
                    "o_mdio_gem_i"   : mdio_i,
                    "i_mdio_gem_o"   : mdio_o,
                    "i_mdio_gem_t"   : mdio_t,
                    # PHY: MDIO
                    "o_mdio_phy_mdc" : mdio_pads.mdc,
                    "i_mdio_phy_i"   : phys_mdio_i,
                    "o_mdio_phy_o"   : phys_mdio_o,
                    "o_mdio_phy_t"   : phys_mdio_t,
                })

        # MMIO interface: nothing to do here
        if eth_io_type != "EMIO":
            return

        if if_type == "gmii":
            self.cpu_params.update({
                # Clk/Rst
                f"i_ENET{n}_GMII_RX_CLK" : clock_pads.rx,
                f"i_ENET{n}_GMII_TX_CLK" : clock_pads.tx,

                # PS GEM -> PHY
                f"i_ENET{n}_GMII_CRS"    : eth_pads.crs,
                f"i_ENET{n}_GMII_COL"    : eth_pads.col,
                f"i_ENET{n}_GMII_RXD"    : eth_pads.rx_data,
                f"i_ENET{n}_GMII_RX_ER"  : eth_pads.rx_er,
                f"i_ENET{n}_GMII_RX_DV"  : eth_pads.rx_dv,
                f"o_ENET{n}_GMII_TXD"    : eth_pads.tx_data,
                f"o_ENET{n}_GMII_TX_EN"  : eth_pads.tx_en,
                f"o_ENET{n}_GMII_TX_ER"  : eth_pads.tx_er,
            })
        elif if_type == "rgmii":
            # Status.
            self.rgmii_status = CSRStatus(fields=[
                CSRField("link_status",   size=1, offset=0),
                CSRField("clock_speed",   size=2, offset=1),
                CSRField("duplex_status", size=1, offset=3),
                CSRField("speed_mode",    size=2, offset=4),
            ])

            # ps7 GMII connection
            gmii_rx_clk = Signal()
            gmii_crs    = Signal()
            gmii_col    = Signal()
            gmii_rxd    = Signal(8)
            gmii_rx_er  = Signal()
            gmii_rx_dv  = Signal()
            gmii_tx_clk = Signal()
            gmii_txd    = Signal(8)
            gmii_tx_en  = Signal()
            gmii_tx_er  = Signal()

            self.cpu_params.update({
                # Clk/Rst
                f"i_ENET{n}_GMII_RX_CLK" : gmii_rx_clk,
                f"i_ENET{n}_GMII_TX_CLK" : gmii_tx_clk,

                f"i_ENET{n}_GMII_CRS"    : gmii_crs,
                f"i_ENET{n}_GMII_COL"    : gmii_col,
                f"i_ENET{n}_GMII_RXD"    : gmii_rxd,
                f"i_ENET{n}_GMII_RX_ER"  : gmii_rx_er,
                f"i_ENET{n}_GMII_RX_DV"  : gmii_rx_dv,
                f"o_ENET{n}_GMII_TXD"    : gmii_txd,
                f"o_ENET{n}_GMII_TX_EN"  : gmii_tx_en,
                f"o_ENET{n}_GMII_TX_ER"  : gmii_tx_er,
            })

            if hasattr(eth_pads, "rst_n"):
                self.comb += eth_pads.rst_n.eq(~ResetSignal("sys"))

            mac_params.update({
                # Clk/Rst
                "i_tx_reset"      : ResetSignal("sys"),
                "i_rx_reset"      : ResetSignal("sys"),
                "i_clkin"         : ClockSignal("rgmii"),
                "o_ref_clk_out"   : Open(),

                # PS GEM: GMII
                "o_gmii_tx_clk"   : gmii_tx_clk,
                "i_gmii_tx_en"    : gmii_tx_en,
                "i_gmii_txd"      : gmii_txd,
                "i_gmii_tx_er"    : gmii_tx_er,
                "o_gmii_crs"      : gmii_crs,
                "o_gmii_col"      : gmii_col,
                "o_gmii_rx_clk"   : gmii_rx_clk,
                "o_gmii_rx_dv"    : gmii_rx_dv,
                "o_gmii_rxd"      : gmii_rxd,
                "o_gmii_rx_er"    : gmii_rx_er,
                # PHY: RGMII
                "o_rgmii_txd"     : eth_pads.tx_data,
                "o_rgmii_tx_ctl"  : eth_pads.tx_ctl,
                "o_rgmii_txc"     : clock_pads.tx,
                "i_rgmii_rxd"     : eth_pads.rx_data,
                "i_rgmii_rx_ctl"  : eth_pads.rx_ctl,
                "i_rgmii_rxc"     : clock_pads.rx,
                # Status
                "o_link_status"   : self.rgmii_status.fields.link_status,
                "o_clock_speed"   : self.rgmii_status.fields.clock_speed,
                "o_duplex_status" : self.rgmii_status.fields.duplex_status,
                "o_speed_mode"    : self.rgmii_status.fields.speed_mode,
            })

            if external_clk:
                mac_params.update({
                    "i_gmii_clk"     : ClockSignal("gmii"),
                    "o_gmii_clk_out" : Open(),
                })

                if txc_skew == 2:
                    mac_params.update({
                        "i_gmii_clk_90"     : ClockSignal("gmii_ps"),
                        "o_gmii_clk_90_out" : Open(),
                    })
            else:
                mac_params.update({
                    "o_mmcm_locked_out"   : Open(),
                    "o_gmii_clk_125m_out" : Open(),
                    "o_gmii_clk_25m_out"  : Open(),
                    "o_gmii_clk_2_5m_out" : Open(),
                })
                if txc_skew == 2:
                    mac_params.update({
                        "o_gmii_clk_125m_90_out" : Open(),
                        "o_gmii_clk_25m_90_out"  : Open(),
                        "o_gmii_clk_2_5m_90_out" : Open(),
                    })
            self.specials += Instance(f"gem{n}", **mac_params)
        self.gem_mac[n] = (if_type, internal_phyaddr, txc_skew, external_clk, use_idelay_ctrl)

    def do_finalize(self):
        if len(self.ps7_tcl) and isinstance(self.platform.toolchain, XilinxVivadoToolchain):
            if self.ps7_name is None:
                raise Exception("PS7 must be set with set_ps7 or set_ps7_xci methods.")
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
        else:
            # With openXC7 ps7_name is imposed by the toolchain
            self.ps7_name = "PS7"

            # No '_' in I/O names
            cpu_params = {}
            for k,v in self.cpu_params.items():
                direction, *name = k.split("_")
                name = ''.join(name)
                # Some I/Os have differents name
                # a dict is used when naming differs really
                # between Vivado and Yosys
                name = {
                    "DDRRASn"          : "DDRRASB",
                    "DDRDQSn"          : "DDRDQSN",
                    "DDRDQS"           : "DDRDQSP",
                    "DDRClkn"          : "DDRCKN",
                    "DDRClk"           : "DDRCKP",
                    "DDRCSn"           : "DDRCSB",
                    "DDRCASn"          : "DDRCASB",
                    "DDRBankAddr"      : "DDRBA",
                    "DDRAddr"          : "DDRA",
                    "FCLKRESET0N"      : "FCLKRESETN",
                    "FCLKCLK0"         : "FCLKCLK",
                    "USB0VBUSPWRFAULT" : "EMIOUSB0VBUSPWRFAULT",
                    "USB1VBUSPWRFAULT" : "EMIOUSB1VBUSPWRFAULT",
                }.get(name, name)

                # Most peripherals when used via EMIO keep the
                # same name but with EMIO before and T -> TN
                if name.startswith(("GPIO", "I2C")):
                    name = f"EMIO{name}" + {True: "N", False: ""}[name[-1] == "T"]

                key = direction + "_" + name
                cpu_params[key] = v
            # Rewrite cpu_params with corrected pins name.
            self.cpu_params = cpu_params
        self.specials += Instance(self.ps7_name, **self.cpu_params)

        # Ethernet

        if len(self.gem_mac):
            mac_tcl = []
            for i, (if_type, phyaddr, txc_skew, external_clk, use_idelay_ctrl) in self.gem_mac.items():
                if if_type == "rgmii":
                    ip_name         = "gmii_to_rgmii"
                    external_clk    = {True:"true", False:"false"}[external_clk]
                    use_idelay_ctrl = {True:"true", False:"false"}[use_idelay_ctrl]

                    mac_tcl.append(f"set gem{i} [create_ip -vendor xilinx.com -name {ip_name} -module_name gem{i}]")
                    mac_tcl.append("set_property -dict [ list \\")
                    # FIXME: when more this sequence differs for the first and others
                    mac_tcl += [
                        "CONFIG.{} {} \\".format("C_EXTERNAL_CLOCK",  '{{' + external_clk    + '}}'),
                        "CONFIG.{} {} \\".format("C_USE_IDELAY_CTRL", '{{' + use_idelay_ctrl + '}}'),
                        "CONFIG.{} {} \\".format("C_PHYADDR",         '{{' + str(phyaddr)    + '}}'),
                        "CONFIG.{} {} \\".format("RGMII_TXC_SKEW",    '{{' + str(txc_skew)   + '}}'),
                        "CONFIG.{} {} \\".format("SupportLevel",      '{{Include_Shared_Logic_in_Core}}'),
                        f"] [get_ips gem{i}]",
                        f"generate_target all [get_ips gem{i}]",
                        f"synth_ip [get_ips gem{i}]"
                    ]

            self.platform.toolchain.pre_synthesis_commands += mac_tcl
