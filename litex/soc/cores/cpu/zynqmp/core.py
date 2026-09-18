#
# This file is part of LiteX.
#
# Copyright (c) 2022 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import logging

from migen import *

from litex.gen                  import *

from litex.soc.cores.cpu        import CPU
from litex.soc.software.libxil  import LibXil
from litex.soc.interconnect     import axi
from litex.soc.interconnect.csr import *


# Zynq MP ------------------------------------------------------------------------------------------

logger = logging.getLogger("ZynqMP")

class ZynqMP(CPU):
    variants                 = ["standard"]
    category                 = "hardcore"
    family                   = "aarch64"
    name                     = "zynqmp"
    human_name               = "Zynq Ultrascale+ MPSoC"
    data_width               = 64
    endianness               = "little"
    reset_address            = 0xc000_0000
    gcc_triple               = "aarch64-none-elf"
    gcc_flags                = ""
    linker_output_format     = "elf64-littleaarch64"
    nop                      = "nop"
    io_regions               = {  # Origin, Length.
        0x8000_0000: 0x00_4000_0000,
        0xe000_0000: 0xff_2000_0000  # TODO: there are more details here
    }
    csr_decode               = True # AXI address is decoded in AXI2Wishbone, offset needs to be added in Software.
    integrated_rom_supported = False

    @property
    def mem_map(self):
        return {
            "sram": 0x0000_0000,  # DDR low in fact
            "csr":  0xA000_0000,  # ZynqMP M_AXI_HPM0_FPD (HPM0)
            "rom":  0xc000_0000,  # Quad SPI memory
        }

    def __init__(self, platform, variant, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.platform = platform
        self.reset          = Signal()
        self.periph_buses   = []          # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses   = []          # Memory buses (Connected directly to LiteDRAM).
        self.axi_gp_masters = [None] * 3  # General Purpose AXI Masters.
        self.gem_mac        = {}          # GEM MAC reserved ports.
        self.i2c_use        = []          # I2c reserved ports.
        self.spi_use        = []          # SPI reserved ports.
        self.uart_use       = []          # UART reserved ports.
        self.sdio_use       = []          # SD reserved ports.
        self.usb_use        = []          # USB reserved ports.
        self.can_use        = []          # CAN reserved/used ports.
        self.pps            = Signal(4)   # Optional PPS (with gemX and PTP enabled)
        self.libxil         = None        # Optional Xilinx libxil software package configuration.

        # PSU EMIO GPIOs (starts at 78).
        self._emio_use      = 0          # EMIO/GPIOs reserved/used.
        self._emio_pads_i   = Signal(95)
        self._emio_pads_o   = Signal(95)
        self._emio_pads_t   = Signal(95)

        # [ 7: 0]: PL_PS_Group0 [128:121]
        # [15: 8]: PL_PS_Group1 [143:136]
        self.interrupt      = Signal(16)

        self.cd_ps = ClockDomain()

        self.ps_name = "ps"
        self.ps_tcl = []
        self.config = {
            'PSU__FPGA_PL0_ENABLE'               : 1, # enable pl_clk0
            'PSU__USE__IRQ0'                     : 1, # enable PL_PS_Group0
            'PSU__NUM_F2P0__INTR__INPUTS'        : 8,
            'PSU__USE__IRQ1'                     : 1, # enable PL_PS_Group1
            'PSU__NUM_F2P1__INTR__INPUTS'        : 8,
            'PSU__USE__M_AXI_GP1'                : 0,

            # Enable EMIO GPIO by default
            'PSU__GPIO_EMIO__PERIPHERAL__ENABLE' : 1,
            'PSU__GPIO_EMIO__PERIPHERAL__IO'     : 95,
        }
        rst_n = Signal()
        self.cpu_params = dict(
            o_pl_clk0=ClockSignal("ps"),
            o_pl_resetn0=rst_n,
            i_pl_ps_irq0 = self.interrupt[0: 8],
            i_pl_ps_irq1 = self.interrupt[8:16],

            # EMIO.
            i_emio_gpio_i = self._emio_pads_i,
            o_emio_gpio_o = self._emio_pads_o,
            o_emio_gpio_t = self._emio_pads_t,
        )

        # Use GP0 as peripheral bus / CSR
        self.pbus = self.add_axi_gp_master(0)
        self.periph_buses.append(self.pbus)

        self.comb += ResetSignal("ps").eq(~rst_n)
        self.ps_tcl.append(f"set ps [create_ip -vendor xilinx.com -name zynq_ultra_ps_e -module_name {self.ps_name}]")

    """
    Configure the Xilinx libxil software package
    Attributes
    ==========
    xparameters: dict
        xparameters.h defines
    bspconfig: dict (optional)
        bspconfig.h contents (defaults: CPU-generic settings)
    embeddedsw_dir: str (optional)
        path to an existing Xilinx embeddedsw checkout
    embeddedsw_git_url: str (optional)
        embeddedsw git URL, used when no local checkout is provided
    """
    def set_libxil(self, xparameters, bspconfig=None, embeddedsw_dir=None, embeddedsw_git_url=None):
        self.libxil = LibXil(self, xparameters, bspconfig, embeddedsw_dir, embeddedsw_git_url)

    """
    Add the configured libxil software package/library to Builder.
    """
    def add_software_packages(self, builder):
        if self.libxil is None:
            logger.warning("libxil software package not enabled, use cpu.set_libxil(...) to enable it.")
            return
        self.libxil.add_software_packages(builder)

    """
    Prepare the configured libxil software environment after SoC finalization.
    """
    def prepare_software(self, builder):
        if self.libxil is not None:
            self.libxil.prepare_software(builder)

    def set_preset(self, preset):
        preset = os.path.abspath(preset)
        self.ps_tcl.append(f"source {preset}")
        self.ps_tcl.append("set psu_cfg [apply_preset IPINST]")
        self.ps_tcl.append("set_property -dict $psu_cfg [get_ips {}]".format(self.ps_name))

    def add_psu_config(self, config):
        # Config must be provided as a config, value dict.
        assert isinstance(config, dict)
        self.config.update(config)

    def add_mio_config(self, directions, iotype="", slew="", pullup="disable", drive_strength=None):
        # directions: {mio_pin_number: direction ("in"/"out"/"inout")}.
        assert pullup in ["disable", "pulldown", "pullup"]
        assert drive_strength is None or isinstance(drive_strength, dict)
        for i, direction in directions.items():
            assert 0 <= i < 78
            assert direction in ["in", "out", "inout"]
            mio_iotype         = iotype.get(i, "")     if isinstance(iotype, dict)   else iotype
            mio_slew           = slew.get(i, "")       if isinstance(slew, dict)     else slew
            mio_drive_strength = drive_strength.get(i) if drive_strength is not None else None
            assert mio_iotype in ["", "cmos", "schmitt"]
            assert mio_drive_strength is None or isinstance(mio_drive_strength, int)
            config = {
                f"PSU_MIO_{i}_DIRECTION"  : direction,
                f"PSU_MIO_{i}_PULLUPDOWN" : pullup,
            }
            if mio_iotype:
                config[f"PSU_MIO_{i}_INPUT_TYPE"]     = mio_iotype
            if mio_slew:
                config[f"PSU_MIO_{i}_SLEW"]           = mio_slew
            if mio_drive_strength is not None:
                config[f"PSU_MIO_{i}_DRIVE_STRENGTH"] = mio_drive_strength
            self.add_psu_config(config)

    def detect_emio_mio_pins(self, pads_or_mio_group):
        idx_lst = []
        # MIO groups are strings; EMIO pads are resources.
        io_type = {True: pads_or_mio_group, False: "EMIO"}[isinstance(pads_or_mio_group, str)]
        # Expand MIO ranges and individual pins, including non-contiguous groups.
        if io_type != "EMIO":
            for first, last in re.findall(r"(\d+)(?:\s*\.\.\s*(\d+))?", io_type):
                first = int(first)
                last = int(last) if last else first
                idx_lst.extend(range(first, last + 1))
        return (io_type, idx_lst)

    def add_axi_gp_master(self, n=0, data_width=32):
        assert n < 3 and self.axi_gp_masters[n] is None
        assert data_width in [32, 64, 128]
        axi_gpn = axi.AXIInterface(data_width=data_width, address_width=32, id_width=16)
        xpd     = {0 : "fpd", 1 : "fpd", 2 : "lpd"}[n]
        self.config[f'PSU__USE__M_AXI_GP{n}']      = 1
        self.config[f'PSU__MAXIGP{n}__DATA_WIDTH'] = data_width
        self.axi_gp_masters.append(axi_gpn)
        self.cpu_params.update({
            # AXI GPx clk.
            f"i_maxihpm0_{xpd}_aclk" : ClockSignal("ps"),

            # AXI GPx aw.
            f"o_maxigp{n}_awid"      : axi_gpn.aw.id,
            f"o_maxigp{n}_awaddr"    : axi_gpn.aw.addr,
            f"o_maxigp{n}_awlen"     : axi_gpn.aw.len,
            f"o_maxigp{n}_awsize"    : axi_gpn.aw.size,
            f"o_maxigp{n}_awburst"   : axi_gpn.aw.burst,
            f"o_maxigp{n}_awlock"    : axi_gpn.aw.lock,
            f"o_maxigp{n}_awcache"   : axi_gpn.aw.cache,
            f"o_maxigp{n}_awprot"    : axi_gpn.aw.prot,
            f"o_maxigp{n}_awvalid"   : axi_gpn.aw.valid,
            f"o_maxigp{n}_awuser"    : axi_gpn.aw.user,
            f"i_maxigp{n}_awready"   : axi_gpn.aw.ready,
            f"o_maxigp{n}_awqos"     : axi_gpn.aw.qos,

            # AXI GPx w.
            f"o_maxigp{n}_wdata"     : axi_gpn.w.data,
            f"o_maxigp{n}_wstrb"     : axi_gpn.w.strb,
            f"o_maxigp{n}_wlast"     : axi_gpn.w.last,
            f"o_maxigp{n}_wvalid"    : axi_gpn.w.valid,
            f"i_maxigp{n}_wready"    : axi_gpn.w.ready,

            # AXI GPx b.
            f"i_maxigp{n}_bid"       : axi_gpn.b.id,
            f"i_maxigp{n}_bresp"     : axi_gpn.b.resp,
            f"i_maxigp{n}_bvalid"    : axi_gpn.b.valid,
            f"o_maxigp{n}_bready"    : axi_gpn.b.ready,

            # AXI GPx ar.
            f"o_maxigp{n}_arid"      : axi_gpn.ar.id,
            f"o_maxigp{n}_araddr"    : axi_gpn.ar.addr,
            f"o_maxigp{n}_arlen"     : axi_gpn.ar.len,
            f"o_maxigp{n}_arsize"    : axi_gpn.ar.size,
            f"o_maxigp{n}_arburst"   : axi_gpn.ar.burst,
            f"o_maxigp{n}_arlock"    : axi_gpn.ar.lock,
            f"o_maxigp{n}_arcache"   : axi_gpn.ar.cache,
            f"o_maxigp{n}_arprot"    : axi_gpn.ar.prot,
            f"o_maxigp{n}_arvalid"   : axi_gpn.ar.valid,
            f"o_maxigp{n}_aruser"    : axi_gpn.ar.user,
            f"i_maxigp{n}_arready"   : axi_gpn.ar.ready,
            f"o_maxigp{n}_arqos"     : axi_gpn.ar.qos,

            # AXI GPx r.
            f"i_maxigp{n}_rid"       : axi_gpn.r.id,
            f"i_maxigp{n}_rdata"     : axi_gpn.r.data,
            f"i_maxigp{n}_rresp"     : axi_gpn.r.resp,
            f"i_maxigp{n}_rlast"     : axi_gpn.r.last,
            f"i_maxigp{n}_rvalid"    : axi_gpn.r.valid,
            f"o_maxigp{n}_rready"    : axi_gpn.r.ready,
        })

        return axi_gpn

    """
    Enable GEMx peripheral.
    ==========
    n: int
        GEM id (0, 1, 2, 3)
    pads_or_mio_group:
        Ethernet pads for EMIO, or a "MIO xx .. yy" group. With a GT
        lane, pads are provided by the GT and this parameter can be None.
    mdio_pads_or_mio_group:
        MDIO/MDC pads, a MIO group, or None to disable MDIO.
    clock_pads:
        Physical tx/rx clock pads for SGMII through the PL. When gt_lane
        is set, pass the GT reference-clock ID (0 to 3) instead of pads.
    if_type: str
        Ethernet interface for EMIO (gmii, rgmii, or sgmii through the PL).
        It is ignored for MIO (fixed RGMII) and GT lane (fixed SGMII).
    clock_pads_freq: float (optional, keyword-only)
        External GEM reference-clock frequency in MHz. Required with
        the GT reference-clock ID when gt_lane is set.
    ref_ctrl_clk_sel: str (optional, keyword-only)
        GEM reference clock source (DPLL/IOPLL/RPLL).
    ref_ctrl_clk_freq: float (optional, keyword-only)
        GEM reference clock frequency in MHz.
    gt_lane: int (optional, keyword-only)
        GT lane for SGMII (0 for GEM0, 1 for GEM1). When set, the
        interface is fixed to SGMII and pads_or_mio_group may be None.
    gt_location: str
        for SGMII Pads location (XaYb) (Required for SGMII).
    reset: Signal
        Reset signal between PS and converter (required for SGMII).
    with_ptp: bool
        Enable PTP support.
    iotype: str
        MIO input type (cmos/schmitt).
    slew: str
        MIO slew rate (slow/fast/...).
    """
    def add_ethernet(self, n=0,
        pads_or_mio_group      = None,
        mdio_pads_or_mio_group = None,
        clock_pads             = None,
        if_type                = "gmii",

        # ZynqMP clock and SGMII configuration.
        *,
        clock_pads_freq        = 0,
        ref_ctrl_clk_sel       = None,
        ref_ctrl_clk_freq      = 0,
        gt_lane                = None,
        gt_location            = None,
        reset                  = None,
        with_ptp               = False,
        iotype                 = "",
        slew                   = "fast"):
        assert 0 <= n < 4 and not n in self.gem_mac
        assert gt_lane is None or (n in [0, 1] and gt_lane == n)
        assert pads_or_mio_group is not None or gt_lane is not None
        if gt_lane is not None:
            assert type(clock_pads) is int and 0 <= clock_pads < 4
            assert clock_pads_freq != 0
            clock_pads = f"Ref Clk{clock_pads}"

        # MIO groups are strings; EMIO connections use platform resources.
        if gt_lane is None:
            (eth_io_type, eth_pins) = self.detect_emio_mio_pins(pads_or_mio_group)
            eth_if_type = "rgmii" if eth_io_type != "EMIO" else if_type
        else:
            eth_io_type, eth_pins = f"GT Lane{gt_lane}", []
            eth_if_type = "sgmii"
        if mdio_pads_or_mio_group is not None:
            (mdio_io_type, mdio_pins) = self.detect_emio_mio_pins(mdio_pads_or_mio_group)
        else:
            mdio_io_type, mdio_pins = "EMIO", []

        pads      = pads_or_mio_group
        mdio_pads = mdio_pads_or_mio_group

        # PSU configuration.
        self.add_psu_config({
            f"PSU__ENET{n}__PERIPHERAL__ENABLE" : 1,
            f"PSU__ENET{n}__PERIPHERAL__IO"     : eth_io_type,
            f"PSU__ENET{n}__GRP_MDIO__ENABLE"   : int(mdio_pads is not None),
        })

        if mdio_pads is not None:
            self.add_psu_config({
                f"PSU__ENET{n}__GRP_MDIO__IO" : mdio_io_type,
            })

        if isinstance(clock_pads, str):
            assert clock_pads_freq != 0
            self.add_psu_config({
                f"PSU__GEM{n}__REF_CLK_SEL"  : clock_pads,
                f"PSU__GEM{n}__REF_CLK_FREQ" : clock_pads_freq,
            })

        if ref_ctrl_clk_sel is not None:
            assert ref_ctrl_clk_freq != 0
            self.add_psu_config({
                f"PSU__CRL_APB__GEM{n}_REF_CTRL__SRCSEL"  : ref_ctrl_clk_sel,
                f"PSU__CRL_APB__GEM{n}_REF_CTRL__FREQMHZ" : ref_ctrl_clk_freq,
            })

        # PTP.
        if with_ptp:
            self.add_psu_config({
                f"PSU__ENET{n}__PTP__ENABLE" : 1,
            })

        if gt_lane is None and eth_io_type != "EMIO":
            assert len(eth_pins) == 12
            directions = {i: "out"  if index < 6 else "in"   for index, i in enumerate(eth_pins)}
            iotypes    = {i: "cmos" if index < 6 else iotype for index, i in enumerate(eth_pins)}
            slews      = {i: slew   if index < 6 else "fast" for index, i in enumerate(eth_pins)}
            self.add_mio_config(directions, iotype=iotypes, slew=slews)
        if mdio_pads is not None and mdio_io_type != "EMIO":
            assert len(mdio_pins) == 2
            self.add_mio_config(
                {mdio_pins[0]: "out", mdio_pins[1]: "inout"},
                iotype = {mdio_pins[0]: "cmos", mdio_pins[1]: iotype},
                slew   = slew,
            )

        # Inject GEMn configuration to use it via csv/json.
        LiteXContext.top.add_constant(f"CONFIG_PSU_GEM{n}_ENABLE",      1)
        LiteXContext.top.add_constant(f"CONFIG_PSU_GEM{n}_TYPE",        eth_if_type)
        LiteXContext.top.add_constant(f"CONFIG_PSU_GEM{n}_IO",          eth_io_type)
        LiteXContext.top.add_constant(f"CONFIG_PSU_GEM{n}_MDIO_ENABLE", int(mdio_pads is not None))
        LiteXContext.top.add_constant(f"CONFIG_PSU_GEM{n}_MDIO_IO",     mdio_io_type)

        # MDIO routing is independent of the Ethernet data interface.
        mdio_mdc  = Signal()
        mdio_i    = Signal()
        mdio_o    = Signal()
        mdio_t    = Signal()
        mdio_emio = mdio_pads is not None and mdio_io_type == "EMIO"
        if mdio_emio:
            self.cpu_params.update({
                f"o_emio_enet{n}_mdio_mdc" : mdio_mdc,
                f"i_emio_enet{n}_mdio_i"   : mdio_i,
                f"o_emio_enet{n}_mdio_o"   : mdio_o,
                f"o_emio_enet{n}_mdio_t"   : mdio_t,
            })

            # For interface in MIO or for gmii (ie direct connection)
            # the MDIO interface is directly connected to the PSU primitive.
            if eth_io_type != "EMIO" or eth_if_type == "gmii":
                self.comb += mdio_pads.mdc.eq(mdio_mdc)
                self.specials += Instance("IOBUF",
                    i_I   = mdio_o,
                    o_O   = mdio_i,
                    i_T   = mdio_t,
                    io_IO = mdio_pads.mdio,
                )

        # End of the Game with interface not in EMIO Mode.
        if eth_io_type != "EMIO":
            self.gem_mac[n] = ("GT", gt_lane) if gt_lane is not None else ("MIO", None)
            return

        assert eth_if_type in ["gmii", "rgmii", "sgmii"]

        # psu GMII connection
        gmii_rx_clk = Signal()
        speed_mode  = Signal(3)
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
            f"i_emio_enet{n}_gmii_rx_clk" : gmii_rx_clk,
            f"o_emio_enet{n}_speed_mode"  : speed_mode,
            f"i_emio_enet{n}_gmii_crs"    : gmii_crs,
            f"i_emio_enet{n}_gmii_col"    : gmii_col,
            f"i_emio_enet{n}_gmii_rxd"    : gmii_rxd,
            f"i_emio_enet{n}_gmii_rx_er"  : gmii_rx_er,
            f"i_emio_enet{n}_gmii_rx_dv"  : gmii_rx_dv,
            f"i_emio_enet{n}_gmii_tx_clk" : gmii_tx_clk,
            f"o_emio_enet{n}_gmii_txd"    : gmii_txd,
            f"o_emio_enet{n}_gmii_tx_en"  : gmii_tx_en,
            f"o_emio_enet{n}_gmii_tx_er"  : gmii_tx_er,
        })

        if eth_if_type == "gmii":
            assert clock_pads is not None and not isinstance(clock_pads, str)
            self.comb += [
                gmii_rx_clk.eq( clock_pads.rx),
                gmii_tx_clk.eq( clock_pads.tx),
                gmii_crs.eq(    pads.crs),
                gmii_col.eq(    pads.col),
                gmii_rxd.eq(    pads.rx_data),
                gmii_rx_er.eq(  pads.rx_er),
                gmii_rx_dv.eq(  pads.rx_dv),
                pads.tx_data.eq(gmii_txd),
                pads.tx_en.eq(  gmii_tx_en),
                pads.tx_er.eq(  gmii_tx_er),
            ]
            self.gem_mac[n] = ("gmii", None)
        elif eth_if_type == "rgmii":

            # In RGMII a gmii2rgmii adapter is required
            # The MDIO crosse the adapter
            phys_mdio_i = Signal()
            phys_mdio_o = Signal()
            phys_mdio_t = Signal()

            if mdio_emio:
                self.specials += Instance("IOBUF",
                    i_I   = phys_mdio_o,
                    o_O   = phys_mdio_i,
                    i_T   = phys_mdio_t,
                    io_IO = mdio_pads.mdio
                )
            else:
                self.comb += phys_mdio_i.eq(1)

            if hasattr(pads, "rst_n"):
                self.comb += pads.rst_n.eq(~ResetSignal("sys"))

            mac_params = dict(
                i_tx_reset          = ResetSignal("sys"),
                i_rx_reset          = ResetSignal("sys"),
                i_clkin             = ClockSignal("rgmii"),

                # PS GEM: MDIO
                i_mdio_gem_mdc      = mdio_mdc if mdio_emio else 0,
                o_mdio_gem_i        = mdio_i,
                i_mdio_gem_o        = mdio_o if mdio_emio else 1,
                i_mdio_gem_t        = mdio_t if mdio_emio else 1,
                # PS GEM: GMII
                o_gmii_tx_clk       = gmii_tx_clk,
                i_gmii_tx_en        = gmii_tx_en,
                i_gmii_txd          = gmii_txd,
                i_gmii_tx_er        = gmii_tx_er,
                o_gmii_crs          = gmii_crs,
                o_gmii_col          = gmii_col,
                o_gmii_rx_clk       = gmii_rx_clk,
                o_gmii_rx_dv        = gmii_rx_dv,
                o_gmii_rxd          = gmii_rxd,
                o_gmii_rx_er        = gmii_rx_er,
                # PHY: RGMII
                o_rgmii_txd         = pads.tx_data,
                o_rgmii_tx_ctl      = pads.tx_ctl,
                o_rgmii_txc         = pads.txc,
                i_rgmii_rxd         = pads.rx_data,
                i_rgmii_rx_ctl      = pads.rx_ctl,
                i_rgmii_rxc         = pads.rxc,
                # PHY: MDIO
                o_mdio_phy_mdc      = mdio_pads.mdc if mdio_emio else Open(),
                i_mdio_phy_i        = phys_mdio_i,
                o_mdio_phy_o        = phys_mdio_o,
                o_mdio_phy_t        = phys_mdio_t,

                o_ref_clk_out       = Open(),
                o_mmcm_locked_out   = Open(),
                o_gmii_clk_125m_out = Open(),
                o_gmii_clk_25m_out  = Open(),
                o_gmii_clk_2_5m_out = Open(),
                o_link_status       = Open(),
                o_clock_speed       = Open(2),
                o_duplex_status     = Open(),
                o_speed_mode        = Open(2),
            )
            self.specials += Instance(f"gem{n}", **mac_params)
            self.gem_mac[n] = ("rgmii", None)
        else:
            assert gt_location is not None
            assert clock_pads is not None and not isinstance(clock_pads, str)

            pcs_mdio_o = Signal()
            pcs_mdio_t = Signal()
            if mdio_emio:
                phys_mdio_i = Signal()
                self.specials += Instance("IOBUF",
                    i_I   = mdio_o,
                    o_O   = phys_mdio_i,
                    i_T   = mdio_t,
                    io_IO = mdio_pads.mdio,
                )
                self.comb += [
                    mdio_pads.mdc.eq(mdio_mdc),
                    mdio_i.eq(Mux(pcs_mdio_t, phys_mdio_i, pcs_mdio_o)),
                ]

            pwrgood         = Signal()
            status          = Signal(16)
            reset_done      = Signal(1)
            pma_reset_out   = Signal(1)
            mmcm_locked_out = Signal(1)
            gem_reset       = Signal()
            self.cd_sl_clk  = ClockDomain("sl_clk")


            sgmii_control = CSRStorage(fields=[
                CSRField("reset",        size=1, reset=0, description="SGMII reset control.", values=[
                    ("``0b0``", "Normal operations."),
                    ("``0b1``", "Reset mode."),
                ]),
                CSRField("tsu_inc_ctrl", size=2, reset=3, description="SGMII TSU increment control.", values=[
                    ("``0b00``", "Timer register increments based on the gem_tsu_ms value."),
                    ("``0b01``", "Timer register increments by an additional nanosecond."),
                    ("``0b10``", "Timer register increments by one nanosecond fewer."),
                    ("``0b11``", "Timer register increments as normal."),
                ])
            ])
            setattr(self, f"sgmii_control{n}", sgmii_control)

            sgmii_status = CSRStatus(fields=[
                CSRField("status",          size=16, offset=0,  description="SGMII status."),
                CSRField("pwrgood",         size=1,  offset=16, description="SGMII power-good status."),
                CSRField("reset_done",      size=1,  offset=17, description="SGMII reset done status."),
                CSRField("pma_reset_out",   size=1,  offset=18, description="SGMII PMA reset output status."),
                CSRField("mmcm_locked_out", size=1,  offset=19, description="SGMII MMCM locked status."),
            ])
            setattr(self, f"sgmii_status{n}", sgmii_status)

            if reset is not None:
                self.comb += gem_reset.eq(ResetSignal("sys") | sgmii_control.fields.reset | reset)
            else:
                self.comb += gem_reset.eq(ResetSignal("sys") | sgmii_control.fields.reset)

            self.comb += [
                sgmii_status.fields.status.eq(         status),
                sgmii_status.fields.pwrgood.eq(        pwrgood),
                sgmii_status.fields.reset_done.eq(     reset_done),
                sgmii_status.fields.pma_reset_out.eq(  pma_reset_out),
                sgmii_status.fields.mmcm_locked_out.eq(mmcm_locked_out),
            ]

            # FIXME: needs to add another PSU->FPGA Clock @50MHz
            from migen.genlib.resetsync import AsyncResetSynchronizer
            self.specials += [
                Instance("BUFGCE_DIV",
                    p_BUFGCE_DIVIDE = 2,
                    i_CE = 1,
                    i_I  = ClockSignal("sys"),
                    o_O  = ClockSignal("sl_clk"),
                ),
                AsyncResetSynchronizer(self.cd_sl_clk, ResetSignal("sys")),
            ]

            mac_params = dict(
                # Clk/Reset
                i_independent_clock_bufg = ClockSignal("sl_clk"),
                i_reset                  = gem_reset,              # Asynchronous reset for entire core
                o_userclk_out            = Open(),
                o_userclk2_out           = Open(),
                o_rxuserclk_out          = Open(),
                o_rxuserclk2_out         = Open(),

                # Transceiver Interface: Clk
                i_gtrefclk_p             = clock_pads.p,
                i_gtrefclk_n             = clock_pads.n,
                o_gtrefclk_out           = Open(),
                o_resetdone              = reset_done,             # The GT transceiver has completed its reset cycle

                # SGMII
                o_txp                    = pads.txp,               # Differential +ve of serial transmission from PMA to PMD.
                o_txn                    = pads.txn,               # Differential -ve of serial transmission from PMA to PMD.
                i_rxp                    = pads.rxp,               # Differential +ve for serial reception from PMD to PMA.
                i_rxn                    = pads.rxn,               # Differential -ve for serial reception from PMD to PMA.
                o_pma_reset_out          = pma_reset_out,          # transceiver PMA reset signal
                o_mmcm_locked_out        = mmcm_locked_out,        # MMCM Locked

                # PS GEM: GMII
                o_sgmii_clk_r            = Open(),
                o_sgmii_clk_f            = Open(),
                o_gmii_txclk             = gmii_tx_clk,
                o_gmii_rxclk             = gmii_rx_clk,
                i_gmii_txd               = gmii_txd,               # Transmit data from client MAC.
                i_gmii_tx_en             = gmii_tx_en,             # Transmit control signal from client MAC.
                i_gmii_tx_er             = gmii_tx_er,             # Transmit control signal from client MAC.
                o_gmii_rxd               = gmii_rxd,               # Received Data to client MAC.
                o_gmii_rx_dv             = gmii_rx_dv,             # Received control signal to client MAC.
                o_gmii_rx_er             = gmii_rx_er,             # Received control signal to client MAC.
                o_gmii_isolate           = Open(),                 # Tristate control to electrically isolate GMII.

                # PS GEM: MDIO
                i_mdc                    = mdio_mdc if mdio_emio else 0, # Management Data Clock
                i_mdio_i                 = mdio_o   if mdio_emio else 1, # Management Data In
                o_mdio_o                 = pcs_mdio_o,                   # Management Data Out
                o_mdio_t                 = pcs_mdio_t,                   # Management Data Tristate

                # Configuration
                i_phyaddr                = Constant(9, 5),
                i_configuration_vector   = Constant(0, 5),         # Alternative to MDIO interface.
                i_configuration_valid    = Constant(0, 1),         # Validation signal for Config vector
                o_an_interrupt           = Open(),                 # Interrupt to processor to signal that Auto-Negotiation has completed
                i_an_adv_config_vector   = Constant(55297, 16),    # Alternate interface to program REG4 (AN ADV)
                i_an_adv_config_val      = Constant(0, 1),         # Validation signal for AN ADV
                i_an_restart_config      = Constant(0, 1),         # Alternate signal to modify AN restart bit in REG0
                o_status_vector          = status,                 # Core status.

                o_gtpowergood            = pwrgood,
                i_signal_detect          = Constant(1, 1),         # Input from PMD to indicate presence of optical input.
            )

            if with_ptp:
                tsu_inc_ctrl  = Signal(2)
                tsu_timer_cnt = Signal(94)
                self.cpu_params.update({
                    # TSU
                    f"o_emio_enet{n}_enet_tsu_timer_cnt" : tsu_timer_cnt,
                    f"i_emio_enet{n}_tsu_inc_ctrl"       : tsu_inc_ctrl,
                })
                self.comb += [
                    tsu_inc_ctrl.eq(sgmii_control.fields.tsu_inc_ctrl),
                    self.pps[n].eq( tsu_timer_cnt[45])
                ]

            self.specials += Instance(f"gem{n}", **mac_params)
            self.gem_mac[n] = ("sgmii", gt_location)

    """
    Connect and Enables I2C controler (may be via PSU MIO or PL EMIO).
    Attributes
    ==========
    n: int
        controler ID 0/1
    pads_or_mio_group: Record or str:
        When pads is a Record, I2Cn controler is configured to uses EMIO
        When pads is a str, I2Cn controler is configured to uses PSU MIO. str must
        be "MIO xx .. yy"
    iotype: str
        IO type configuration (cmos/schmitt). This parameter is only
        used in MIO mode.
    slew: str
        IO slew rate (slow/fast/...). This parameter is only used in MIO mode.
    srcsel: str (optional, keyword-only) (Accepted values: DPLL/IOPLL/RPLL).
        PSU reference clock source. Empty keeps the default value.
    freq: float (optional, keyword-only)
        PSU reference clock frequency in MHz. Zero keeps the default value.
    """
    def add_i2c(self, n, pads_or_mio_group, iotype="cmos", slew="fast", *, srcsel="", freq=0):
        assert 0 <= n < 2 and not n in self.i2c_use
        assert pads_or_mio_group is not None
        assert freq >= 0

        # Mark as used.
        self.i2c_use.append(n)

        # Detect the IO type and parse the MIO pin endpoints.
        (io_type, pins) = self.detect_emio_mio_pins(pads_or_mio_group)

        # PSU configuration.
        self.add_psu_config({
            f"PSU__I2C{n}__PERIPHERAL__ENABLE" : 1,
            f"PSU__I2C{n}__PERIPHERAL__IO"     : io_type,
        })
        if srcsel:
            self.add_psu_config({f"PSU__CRL_APB__I2C{n}_REF_CTRL__SRCSEL": srcsel})
        if freq:
            self.add_psu_config({f"PSU__CRL_APB__I2C{n}_REF_CTRL__FREQMHZ": int(freq)})

        # Inject I2Cn configuration to use it via csv/json.
        LiteXContext.top.add_constant(f"CONFIG_PSU_I2C{n}_ENABLE", 1)
        LiteXContext.top.add_constant(f"CONFIG_PSU_I2C{n}_IO",     io_type)

        if io_type != "EMIO":
            self.add_mio_config(
                {i: "inout" for i in pins},
                iotype = iotype,
                slew   = slew,
                pullup = "pullup",
            )

        # I2Cn interface is only exposed when controller is set to EMIO.
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

            # PSU connections.
            self.cpu_params.update({
                f"i_emio_i2c{n}_scl_i" : scl.i,
                f"o_emio_i2c{n}_scl_o" : scl.o,
                f"o_emio_i2c{n}_scl_t" : scl.oe,
                f"i_emio_i2c{n}_sda_i" : sda.i,
                f"o_emio_i2c{n}_sda_o" : sda.o,
                f"o_emio_i2c{n}_sda_t" : sda.oe,
            })

    """
    Connect and Enables SPIn controler (may be via PSU MIO or PL EMIO).
    Attributes
    ==========
    n: int
        controler ID 0/1
    pads_or_mio_group: Record or str:
        When pads_or_mio_group is:
        - a Record, SPIn controler is configured to uses EMIO
        - a str, SPIn controler is configured to uses PSU MIO. str must
        be the name of the MIO group: "MIO xx .. yy"
    ss1_en: bool
        Enable second CS (ss1). Only used in MIO mode. With EMIO ss1_en is
        deduced by cs1_n in pads_or_mio_group
    ss2_en: bool
        Enable third CS (ss2). Only used in MIO mode. With EMIO ss2_en is
        deduced by cs2_n in pads_or_mio_group
    iotype: str
        IO type configuration (cmos/schmitt). This parameter is only
        used in MIO mode.
    slew: str
        IO slew rate (slow/fast/...). This parameter is only used in MIO mode.
    srcsel: str (optional, keyword-only) (Accepted values: DPLL/IOPLL/RPLL).
        PSU reference clock source.
    freq: float (optional, keyword-only)
        PSU reference clock frequency in MHz. Zero keeps the default value.
    """
    def add_spi(self, n, pads_or_mio_group, ss1_en=False, ss2_en=False, iotype="cmos", slew="slow", *,
        srcsel="IOPLL", freq=0):
        assert n < 2 and not n in self.spi_use
        assert pads_or_mio_group is not None

        # Mark as used.
        self.spi_use.append(n)

        # Detect the IO type and parse the MIO pin endpoints.
        (io_type, pins) = self.detect_emio_mio_pins(pads_or_mio_group)

        # In EMIO check if Record contains cs1_n/cs2_n
        if io_type == "EMIO":
            ss1_en = hasattr(pads_or_mio_group, "cs1_n")
            ss2_en = hasattr(pads_or_mio_group, "cs2_n")

        # PSU configuration.
        self.add_psu_config({
            f"PSU__SPI{n}__PERIPHERAL__ENABLE" : 1,
            f"PSU__SPI{n}__PERIPHERAL__IO"     : io_type,
            f"PSU__SPI{n}__GRP_SS1__ENABLE"    : {True: 1, False: 0}[ss1_en],
            f"PSU__SPI{n}__GRP_SS2__ENABLE"    : {True: 1, False: 0}[ss2_en],
        })

        if srcsel:
            self.add_psu_config({f"PSU__CRL_APB__SPI{n}_REF_CTRL__SRCSEL": srcsel})
        if freq:
            self.add_psu_config({f"PSU__CRL_APB__SPI{n}_REF_CTRL__FREQMHZ": int(freq)})

        # Inject SPIn configuration to use it via csv/json
        LiteXContext.top.add_constant(f"CONFIG_PSU_SPI{n}_ENABLE", 1)
        LiteXContext.top.add_constant(f"CONFIG_PSU_SPI{n}_IO",     io_type)

        # configures IOs associated to this interface
        if io_type != "EMIO":
            pins_name   = ['sclk', 'ss2', 'ss1', 'ss0', 'miso', 'mosi']
            pin_map     = zip(pins, pins_name)
            directions  = {
                p_i: ("out" if p_n in ("ss1", "ss2") else "inout")
                for p_i, p_n in pin_map
                if not ((p_n == "ss1" and not ss1_en) or (p_n == "ss2" and not ss2_en))
            }
            self.add_mio_config(
                directions = directions,
                iotype     = iotype,
                slew       = slew,
                pullup     = "pullup",
            )

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

            # PSU connections.
            # see Table 23-2 @ https://docs.amd.com/api/khub/documents/xzMsp_c5sG9J6A3u7NkJYQ/content
            self.cpu_params.update({
                # SCLK
                f"i_emio_spi{n}_sclk_i" : sclk.i,
                f"o_emio_spi{n}_sclk_o" : sclk.o,
                f"o_emio_spi{n}_sclk_t" : sclk.oe,
                # MOSI
                f"i_emio_spi{n}_s_i"    : mosi.i, # Yes _s_i is for MOSI
                f"o_emio_spi{n}_m_o"    : mosi.o,
                f"o_emio_spi{n}_mo_t"   : mosi.oe,
                # MISO
                f"i_emio_spi{n}_m_i"    : miso.i, # Yes _m_i is for MISO
                f"o_emio_spi{n}_s_o"    : miso.o,
                f"o_emio_spi{n}_so_t"   : miso.oe,
                # SS0
                f"i_emio_spi{n}_ss_i_n" : ss.i,
                f"o_emio_spi{n}_ss_o_n" : ss.o,
                f"o_emio_spi{n}_ss_n_t" : ss.oe,
            })
            if ss1_en:
                self.cpu_params.update({
                    f"o_emio_spi{n}_ss1_o_n" : pads_or_mio_group.cs1_n,
                })
            if ss2_en:
                self.cpu_params.update({
                    f"o_emio_spi{n}_ss2_o_n" : pads_or_mio_group.cs2_n,
                })

    """
    Connect and Enables UARTn controler (may be via PSU MIO or PL EMIO).
    Attributes
    ==========
    n: int
        controler ID 0/1
    pads_or_mio_group: Record or str:
        When pads_or_mio_group is:
        - a Record, UARTn controler is configured to uses EMIO
        - a str, UARTn controler is configured to uses PSU MIO. str must
        be the name of the MIO group: "MIO xx .. yy"
    iotype: str
        IO type configuration (cmos/schmitt). This parameter is only
        used in MIO mode.
    slew: str
        IO slew rate (slow/fast). This parameter is only used in MIO mode.
    srcsel: str (optional, keyword-only) (Accepted values: DPLL/IOPLL/RPLL).
        PSU reference clock source. Empty keeps the default value.
    freq: float (optional, keyword-only)
        PSU reference clock frequency in MHz. Zero keeps the default value.
    """
    def add_uart(self, n, pads_or_mio_group, iotype="cmos", slew="fast", *, srcsel="", freq=0):
        assert n < 2 and not n in self.uart_use
        assert pads_or_mio_group is not None
        assert freq >= 0

        # Mark as used.
        self.uart_use.append(n)

        # Detect the IO type and parse the MIO pin endpoints.
        (io_type, pins) = self.detect_emio_mio_pins(pads_or_mio_group)

        # PSU configuration.
        self.add_psu_config({
            f"PSU__UART{n}__PERIPHERAL__ENABLE" : 1,
            f"PSU__UART{n}__PERIPHERAL__IO"     : io_type,
            f"PSU__UART{n}__MODEM__ENABLE"      : 0, # FIXME
        })
        if srcsel:
            self.add_psu_config({f"PSU__CRL_APB__UART{n}_REF_CTRL__SRCSEL": srcsel})
        if freq:
            self.add_psu_config({f"PSU__CRL_APB__UART{n}_REF_CTRL__FREQMHZ": int(freq)})

        # Inject UARTn configuration to use it via csv/json
        LiteXContext.top.add_constant(f"CONFIG_PSU_UART{n}_ENABLE", 1)
        LiteXContext.top.add_constant(f"CONFIG_PSU_UART{n}_IO",     io_type)

        # configures IOs associated to this interface
        if io_type != "EMIO":
            # UART0 maps RX/TX, while UART1 maps TX/RX.
            directions = ("in", "out") if n == 0 else ("out", "in")
            self.add_mio_config(
                dict(zip(pins, directions)),
                iotype = iotype,
                slew   = slew,
                pullup = "pullup"
            )

        # UARTn interface is only exposed when controller is set to EMIO.
        if io_type == "EMIO":
            # PSU connections.
            self.cpu_params.update({
                f"i_emio_uart{n}_rxd" : pads_or_mio_group.rx,
                f"o_emio_uart{n}_txd" : pads_or_mio_group.tx,
            })

    """
    Enable SD0/SD1 through PSU MIO or PL EMIO.
    Attributes
    ==========
    n: int
        Controller ID (0/1).
    pads_or_mio_group: Record or str
        EMIO pads (clk, cmd, data) or MIO group ("MIO xx .. yy").
        Optional EMIO pads: cd, wp, pow, led, bus_volt[2:0].
    card_detect: int
        Active-low card detect: MIO pin id. Only used for MIO Mode.
        For EMIO mode the signal, if present, is shipped in
        pads_or_mio_group (cd). Forbidden for eMMC.
    write_protect: int
        Write protect: MIO pin id. Only used for MIO Mode.
        For EMIO mode the signal, if present, is shipped in
        pads_or_mio_group (wp). Forbidden for eMMC.
    power_control: int
        Bus power (or eMMC reset): MIO pin id. Only used for MIO Mode.
        For EMIO mode the signal, if present, is shipped in
        pads_or_mio_group (pow).
    iotype: str
        MIO input type (cmos/schmitt), unused for clk_out and bus_pow.
    slew: str
        MIO slew rate (slow/fast). cd_n and wp always use fast.
    slot_type: str (optional, keyword-only)
        SD 2.0, SD 3.0, SD 3.0 AUTODIR or eMMC.
    data_width: int (optional, keyword-only)
        Data Transfer Mode (4/8). Defaults to 4 for SD 2.0, 8 otherwise.
        eMMC supports either mode.
    srcsel: str (optional, keyword-only)
        PSU reference clock source. Empty keeps the default value.
    freq: float (optional, keyword-only)
        PSU reference clock frequency in MHz. Zero keeps the default value.
    """
    def add_sdio(self, n, pads_or_mio_group,
        card_detect   = None,
        write_protect = None,
        power_control = None,
        iotype        = "cmos",
        slew          = "fast",
        *,
        slot_type     = "SD 2.0",
        data_width    = None,
        srcsel        = "",
        freq          = 0
        ):
        assert 0 <= n < 2 and n not in self.sdio_use
        assert pads_or_mio_group is not None
        assert freq >= 0
        assert slot_type in ["SD 2.0", "SD 3.0", "SD 3.0 AUTODIR", "eMMC"]

        default_width = {True: 4, False: 8}[slot_type == "SD 2.0"]
        if data_width is None:
            data_width = default_width
        assert data_width in [4, 8]
        assert slot_type == "eMMC" or data_width == default_width

        # Detect the IO type and parse the MIO pin endpoints.
        (io_type, pins) = self.detect_emio_mio_pins(pads_or_mio_group)

        # For EMIO Mode, all three controls are EMIO too and are
        # included in pads_or_mio_group. Method parameters are
        # ignored.
        if io_type == "EMIO":
            card_detect   = getattr(pads_or_mio_group, "cd",  None)
            power_control = getattr(pads_or_mio_group, "pow", None)
            write_protect = getattr(pads_or_mio_group, "wp",  None)

        if slot_type == "eMMC":
            assert card_detect is None and write_protect is None

        # When controler is in EMIO Mode all Controls must also be in EMIO.
        card_detect_io   = "EMIO" if io_type == "EMIO" else f"MIO {card_detect}"
        write_protect_io = "EMIO" if io_type == "EMIO" else f"MIO {write_protect}"
        power_control_io = "EMIO" if io_type == "EMIO" else f"MIO {power_control}"

        # PSU configuration.
        self.sdio_use.append(n)
        config = {
            f"PSU__SD{n}__PERIPHERAL__ENABLE" : 1,
            f"PSU__SD{n}__PERIPHERAL__IO"     : io_type,
            # These two lines must be in this order, otherwise Vivado
            # removes the requested data_width !!!
            f"PSU__SD{n}__DATA_TRANSFER_MODE" : f"{data_width}Bit",
            f"PSU__SD{n}__SLOT_TYPE"          : slot_type,
            f"PSU__SD{n}__GRP_CD__ENABLE"     : int(card_detect   is not None),
            f"PSU__SD{n}__GRP_WP__ENABLE"     : int(write_protect is not None),
            f"PSU__SD{n}__GRP_POW__ENABLE"    : int(power_control is not None),
        }
        if card_detect is not None:
            config[f"PSU__SD{n}__GRP_CD__IO"]  = card_detect_io
        if write_protect is not None:
            config[f"PSU__SD{n}__GRP_WP__IO"]  = write_protect_io
        if power_control is not None:
            config[f"PSU__SD{n}__GRP_POW__IO"] = power_control_io
        if slot_type == "eMMC":
            config[f"PSU__SD{n}__RESET__ENABLE"] = int(power_control is not None)
        if srcsel:
            config[f"PSU__CRL_APB__SDIO{n}_REF_CTRL__SRCSEL"] = srcsel
        if freq:
            config[f"PSU__CRL_APB__SDIO{n}_REF_CTRL__FREQMHZ"] = int(freq)
        self.add_psu_config(config)

        # Inject SDn configuration to use it via csv/json.
        LiteXContext.top.add_constant(f"CONFIG_PSU_SD{n}_ENABLE", 1)
        LiteXContext.top.add_constant(f"CONFIG_PSU_SD{n}_IO",     io_type)

        if io_type != "EMIO":
            # Sanity check for control must be int and in allowed range pour MIO IDs.
            assert card_detect   is None or type(card_detect)   == int and card_detect   < 78
            assert power_control is None or type(power_control) == int and power_control < 78
            assert write_protect is None or type(write_protect) == int and write_protect < 78

            first, last = pins[0], pins[-1]
            # SD0 clock is first in banks 1/2, last in bank 0; SD1 clock is last.
            clk_pin = first if n == 0 and first != 13 else last
            self.add_mio_config(
                {i: "inout" for i in pins if i not in (clk_pin, power_control)},
                iotype=iotype, slew=slew, pullup="pullup",
            )
            self.add_mio_config({clk_pin: "out"}, slew=slew, pullup="pullup")

            if card_detect is not None:
                self.add_mio_config(
                    {card_detect: "in"}, iotype=iotype, slew="fast", pullup="pullup",
                )
            if write_protect is not None:
                self.add_mio_config(
                    {write_protect: "in"}, iotype=iotype, slew="fast", pullup="pullup",
                )
            if power_control is not None:
                self.add_mio_config(
                    {power_control: "out"}, slew=slew, pullup="pullup",
                )

            # End of configuration for MIO mode.
            return

        # EMIO connections.
        assert len(pads_or_mio_group.clk) == len(pads_or_mio_group.cmd) == 1
        assert len(pads_or_mio_group.data) == data_width
        if card_detect is not None:
            self.cpu_params[f"i_emio_sdio{n}_cd_n"] = card_detect
        if write_protect is not None:
            self.cpu_params[f"i_emio_sdio{n}_wp"] = write_protect
        if power_control is not None:
            self.cpu_params[f"o_emio_sdio{n}_buspower"] = power_control

        # Vivado exposes cmdena/dataena as active-high tristate controls.
        for name, pads in [("cmd", pads_or_mio_group.cmd), ("data", pads_or_mio_group.data)]:
            sd_i = Signal(len(pads))
            sd_o = Signal(len(pads))
            sd_t = Signal(len(pads))
            for i in range(len(pads)):
                self.specials += Instance("IOBUF",
                    i_I=sd_o[i], o_O=sd_i[i], i_T=sd_t[i], io_IO=pads[i],
                )
            self.cpu_params.update({
                f"i_emio_sdio{n}_{name}in"  : sd_i,
                f"o_emio_sdio{n}_{name}out" : sd_o,
                f"o_emio_sdio{n}_{name}ena" : sd_t,
            })

        self.cpu_params.update({
            f"o_emio_sdio{n}_clkout"     : pads_or_mio_group.clk,
            f"i_emio_sdio{n}_fb_clk_in"  : pads_or_mio_group.clk,
            f"o_emio_sdio{n}_ledcontrol" : getattr(pads_or_mio_group, "led", Open()),
            f"o_emio_sdio{n}_bus_volt"   : getattr(pads_or_mio_group, "bus_volt", Open(3)),
        })

    """
    Enable USBn through its USB 2.0 ULPI MIO interface.
    USB0 uses MIO 52 .. 63 and USB1 uses MIO 64 .. 75.
    USB3 can be enabled on GT Lane 0, 1 or 2 for USB0, and GT Lane 3 for USB1.
    Attributes
    ==========
    n: int
        Controller ID (0/1).
    reset: int (optional)
        MIO pin used to reset the USB controller.
    reset_polarity: str
        USB reset polarity ("Active Low" or "Active High").
    iotype: str
        MIO input type (cmos/schmitt). STP is fixed to cmos.
    slew: str
        MIO slew rate (slow/fast/...). CLK_IN, DIR and NXT are fixed to fast.
    gt_lane: int (optional, keyword-only)
        GT lane used to enable the USB 3.0 controller. None disables USB 3.0.
    ref_clk_sel: int (optional, keyword-only)
        USB3 GT reference clock selection (0 through 3).
    ref_clk_freq: float (optional, keyword-only)
        USB3 GT reference clock frequency in MHz. Zero keeps the default value.
    srcsel: str (optional, keyword-only)
        USB reference clock source. Empty keeps the default value.
    freq: float (optional, keyword-only)
        USB reference clock frequency in MHz. Zero keeps the default value.
    """
    def add_usb(self, n, reset=None, reset_polarity="Active Low", iotype="cmos", slew="fast", *,
        gt_lane=None, ref_clk_sel=None, ref_clk_freq=0, srcsel="", freq=0):
        assert 0 <= n < 2 and n not in self.usb_use
        assert reset is None or type(reset) is int and 0 <= reset < 78
        assert reset_polarity in ["Active Low", "Active High"]
        assert gt_lane is None or type(gt_lane) is int and gt_lane in ([0, 1, 2] if n == 0 else [3])
        assert ref_clk_sel is None or type(ref_clk_sel) is int and 0 <= ref_clk_sel <= 3
        assert ref_clk_freq in [0, 26, 52, 100]
        assert freq >= 0
        assert gt_lane is not None or (ref_clk_sel is None and not ref_clk_freq)
        assert self.config.get("PSU__USB__RESET__POLARITY", reset_polarity) == reset_polarity

        pins    = list(range(52 + 12*n, 64 + 12*n))
        io_type = f"MIO {pins[0]} .. {pins[-1]}"

        # PSU configuration.
        self.usb_use.append(n)
        config = {
            f"PSU__USB{n}__PERIPHERAL__ENABLE" : 1,
            f"PSU__USB{n}__PERIPHERAL__IO"     : io_type,
            f"PSU__USB{n}__RESET__ENABLE"      : int(reset is not None),
            "PSU__USB__RESET__POLARITY"        : reset_polarity,
            f"PSU__USB2_{n}__EMIO__ENABLE"     : 0,
        }
        if reset is not None:
            config[f"PSU__USB{n}__RESET__IO"] = f"MIO {reset}"
        if gt_lane is not None:
            if ref_clk_sel is not None:
                config[f"PSU__USB{n}__REF_CLK_SEL"] = f"Ref Clk{ref_clk_sel}"
            if ref_clk_freq:
                config[f"PSU__USB{n}__REF_CLK_FREQ"] = int(ref_clk_freq)
            config.update({
                f"PSU__USB3_{n}__PERIPHERAL__ENABLE" : 1,
                f"PSU__USB3_{n}__PERIPHERAL__IO"     : f"GT Lane{gt_lane}",
                f"PSU__USB3_{n}__EMIO__ENABLE"       : 0,
                "PSU__CRL_APB__USB3__ENABLE"         : 1,
                "PSU_USB3__DUAL_CLOCK_ENABLE"        : 1,
            })
        if srcsel:
            config[f"PSU__CRL_APB__USB{n}_BUS_REF_CTRL__SRCSEL"] = srcsel
        if freq:
            config[f"PSU__CRL_APB__USB{n}_BUS_REF_CTRL__FREQMHZ"] = int(freq)
        if gt_lane is not None:
            if srcsel:
                assert self.config.get("PSU__CRL_APB__USB3_DUAL_REF_CTRL__SRCSEL", srcsel) == srcsel
                config["PSU__CRL_APB__USB3_DUAL_REF_CTRL__SRCSEL"] = srcsel
            if freq:
                assert self.config.get("PSU__CRL_APB__USB3_DUAL_REF_CTRL__FREQMHZ", int(freq)) == int(freq)
                config["PSU__CRL_APB__USB3_DUAL_REF_CTRL__FREQMHZ"] = int(freq)
        self.add_psu_config(config)

        # Inject USBn configuration to use it via csv/json.
        LiteXContext.top.add_constant(f"CONFIG_PSU_USB{n}_ENABLE", 1)
        LiteXContext.top.add_constant(f"CONFIG_PSU_USB{n}_IO",     io_type)

        # USB ULPI pin order: clk_in, dir, data[2], nxt, data[0:1], stp, data[3:7].
        directions = ["in", "in", "inout", "in", "inout", "inout", "out"] + ["inout"] * 5
        # build iotype and slew default value
        iotypes    = [iotype] * len(pins)
        slews      = [slew] * len(pins)
        # for stp iotypes is fixed, for clk_in, dir and nxt slew is fixed.
        iotypes[6] = "cmos"
        for index in [0, 1, 3]:
            slews[index] = "fast"
        self.add_mio_config(dict(zip(pins, directions)),
            iotype = dict(zip(pins, iotypes)),
            slew   = dict(zip(pins, slews)),
            pullup = "pullup",
        )
        if reset is not None:
            self.add_mio_config({reset: "out"}, slew=slew, pullup="pullup")

    """
    Connect Signal,TSTriple or pads to the EMIO interface.
    Attributes
    ==========
    pads: physical pads (request/request_all), Signal(x), TSTriple or list of TSTriple.
    pads_type: str (signal, pads), default: pads
        pads means a physical signal, signal means any Signals internally
        defined (may be connected to a physical pad or a Core).
    pads_dir: str (in, out, inout)
        pads direction, only used for signals.
    """
    def add_gpios(self, pads, pads_type="pads", pads_dir="inout", *, iotype="", slew=""):
        assert pads is not None
        assert pads_type in ["signal", "pads"]
        assert pads_dir in ["in", "out", "inout"]
        assert len(pads) + self._emio_use <= len(self._emio_pads_i)

        def _connect_ios(p=None, p_i=None, p_o=None, p_t=None):
            if p is not None:
                assert p_i is None and p_o is None and p_t is None
                assert self._emio_use < len(self._emio_pads_i)

                # Use intermediate signals for IOBUF -> ZynqMP
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
                # GPIO T disables the output; TSTriple.oe enables it.
                self.comb += p_t.eq(~self._emio_pads_t[self._emio_use])
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
    Enable CANx peripheral (may be via PSU MIO or PL EMIO). Peripheral may be optionally set
    Attributes
    ==========
    n: int
        CAN id (0, 1)
    pads_or_mio_group: Record or str:
        When pads_or_mio_group is:
        - a Record, CANn controler is configured to uses EMIO
        - a str, CANn controler is configured to uses PSU MIO. str must
        be the name of the MIO group: "MIO xx .. yy"
    ext_clk: int or None
        When unset/None CAN is clocked by internal clock (IO PLL).
        value must be 0 <= ext_clk < 78.
    ext_clk_freq: float
        when ext_clk is set, external clock frequency (Hz)
    iotype: str
        IO type for the MIO pins (cmos/schmitt). This parameter is only
        used in MIO mode.
    slew: str
        IO slew rate (slow/fast/...). This parameter is only used in MIO mode.
    """
    def add_can(self, n, pads_or_mio_group, ext_clk=None, ext_clk_freq=None, iotype="cmos", slew="fast"):
        assert n < 2 and not n in self.can_use
        assert ext_clk is None or ext_clk < 78
        assert ext_clk is None or (ext_clk_freq is not None and ext_clk_freq > 0)
        assert pads_or_mio_group is not None

        # Mark as used
        self.can_use.append(n)

        # Detect the IO type and parse the MIO pin endpoints.
        (io_type, pins) = self.detect_emio_mio_pins(pads_or_mio_group)

        # PSU configuration.
        self.add_psu_config({
            f"PSU__CAN{n}__PERIPHERAL__ENABLE":       1,
            f"PSU__CAN{n}__PERIPHERAL__IO":           io_type,
            f"PSU__CAN{n}__GRP_CLK__ENABLE":          {True: 0,       False: 1}         [ext_clk is None],
            f"PSU__CRL_APB__CAN{n}_REF_CTRL__SRCSEL": {True: "IOPLL", False: "external"}[ext_clk is None],
        })

        if ext_clk is not None:
            self.add_psu_config({
                f"PSU__CAN{n}__GRP_CLK__IO"               : f"MIO {ext_clk}",
                f"PSU__CRL_APB__CAN{n}_REF_CTRL__FREQMHZ" : int(ext_clk_freq / 1e6),
            })

        # Inject CANn configuration to use it via csv/json.
        LiteXContext.top.add_constant(f"CONFIG_PSU_CAN{n}_ENABLE", 1)
        LiteXContext.top.add_constant(f"CONFIG_PSU_CAN{n}_IO",     io_type)

        # Configure IOs associated with this interface.
        if io_type != "EMIO":
            # CAN0 maps RX/TX, while CAN1 maps TX/RX.
            directions = ("in", "out") if n == 0 else ("out", "in")
            self.add_mio_config(
                dict(zip(pins, directions)),
                iotype = iotype,
                slew   = slew,
                pullup = "pullup"
            )

        if ext_clk is not None:
            self.add_mio_config({ext_clk: "in"}, iotype=iotype, slew=slew)

        # CANn interface is only exposed when controller is set to EMIO.
        if io_type == "EMIO":
            # PSU connections.
            self.cpu_params.update({
                f"i_emio_can{n}_phy_rx": pads_or_mio_group.rx,
                f"o_emio_can{n}_phy_tx": pads_or_mio_group.tx,
            })
    def do_finalize(self):
        if len(self.ps_tcl):
            self.ps_tcl.append("set_property -dict [list \\")
            for config, value in self.config.items():
                self.ps_tcl.append("CONFIG.{} {} \\".format(config, '{{' + str(value) + '}}'))
            self.ps_tcl.append(f"] [get_ips {self.ps_name}]")

            self.ps_tcl += [
                f"generate_target all [get_ips {self.ps_name}]",
                f"synth_ip [get_ips {self.ps_name}]"
            ]
            self.platform.toolchain.pre_synthesis_commands += self.ps_tcl
        self.specials += Instance(self.ps_name, **self.cpu_params)

        # ethernet

        if len(self.gem_mac):
            mac_tcl = []
            for i, (if_type, gt_location) in self.gem_mac.items():
                if if_type in ["MIO", "GT", "gmii"]:
                    continue
                ip_name = {"rgmii": "gmii_to_rgmii", "sgmii": "gig_ethernet_pcs_pma"}[if_type]
                mac_tcl.append(f"set gem{i} [create_ip -vendor xilinx.com -name {ip_name} -module_name gem{i}]")
                mac_tcl.append("set_property -dict [ list \\")
                if if_type == "rgmii":
                    # FIXME: when more this sequence differs for the first and others
                    mac_tcl.append("CONFIG.{} {} \\".format("C_EXTERNAL_CLOCK", '{{false}}'))
                    mac_tcl.append("CONFIG.{} {} \\".format("C_USE_IDELAY_CTRL", '{{true}}'))
                    mac_tcl.append("CONFIG.{} {} \\".format("C_PHYADDR", '{{' + str(8 + i) + '}}'))
                    mac_tcl.append("CONFIG.{} {} \\".format("RGMII_TXC_SKEW", '{{' + str(0) + '}}'))
                    mac_tcl.append("CONFIG.{} {} \\".format("SupportLevel", '{{Include_Shared_Logic_in_Core}}'))
                elif if_type == "sgmii":
                    mac_tcl.append("CONFIG.{} {} \\".format("DIFFCLK_BOARD_INTERFACE", '{{Custom}}'))
                    mac_tcl.append("CONFIG.{} {} \\".format("DrpClkRate",              '{{50.0000}}'))
                    mac_tcl.append("CONFIG.{} {} \\".format("EMAC_IF_TEMAC",           '{{GEM}}'))
                    mac_tcl.append("CONFIG.{} {} \\".format(f"GT_Location",             '{{' + gt_location + '}}'))
                    mac_tcl.append("CONFIG.{} {} \\".format("RefClkRate",              '{{156.25}}'))
                    mac_tcl.append("CONFIG.{} {} \\".format("Standard",                '{{SGMII}}'))
                    mac_tcl.append("CONFIG.{} {} \\".format("SupportLevel",            '{{Include_Shared_Logic_in_Core}}'))

                mac_tcl += [
                    f"] [get_ips gem{i}]",
                    f"generate_target all [get_ips gem{i}]",
                    f"synth_ip [get_ips gem{i}]"
                ]

            self.platform.toolchain.pre_synthesis_commands += mac_tcl
