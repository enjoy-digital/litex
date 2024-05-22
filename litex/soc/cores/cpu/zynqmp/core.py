#
# This file is part of LiteX.
#
# Copyright (c) 2022 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex.soc.cores.cpu import CPU
from litex.soc.interconnect import axi


# Zynq MP ------------------------------------------------------------------------------------------

class ZynqMP(CPU):
    variants             = ["standard"]
    category             = "hardcore"
    family               = "aarch64"
    name                 = "zynqmp"
    human_name           = "Zynq Ultrascale+ MPSoC"
    data_width           = 64
    endianness           = "little"
    reset_address        = 0xc000_0000
    gcc_triple           = "aarch64-none-elf"
    gcc_flags            = ""
    linker_output_format = "elf64-littleaarch64"
    nop                  = "nop"
    io_regions           = {  # Origin, Length.
        0x8000_0000: 0x00_4000_0000,
        0xe000_0000: 0xff_2000_0000  # TODO: there are more details here
    }
    csr_decode           = True # AXI address is decoded in AXI2Wishbone, offset needs to be added in Software.

    @property
    def mem_map(self):
        return {
            "sram": 0x0000_0000,  # DDR low in fact
            "rom":  0xc000_0000,  # Quad SPI memory
        }

    def __init__(self, platform, variant, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.platform = platform
        self.reset          = Signal()
        self.periph_buses   = []          # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses   = []          # Memory buses (Connected directly to LiteDRAM).
        self.axi_gp_masters = [None] * 3  # General Purpose AXI Masters.
        self.gem_mac        = []          # GEM MAC reserved ports.
        self.i2c_use        = []          # I2c reserved ports.
        self.uart_use       = []          # UART reserved ports.

        self.cd_ps = ClockDomain()

        self.ps_name = "ps"
        self.ps_tcl = []
        self.config = {'PSU__FPGA_PL0_ENABLE': 1}  # enable pl_clk0
        rst_n = Signal()
        self.cpu_params = dict(
            o_pl_clk0=ClockSignal("ps"),
            o_pl_resetn0=rst_n
        )
        self.comb += ResetSignal("ps").eq(~rst_n)
        self.ps_tcl.append(f"set ps [create_ip -vendor xilinx.com -name zynq_ultra_ps_e -module_name {self.ps_name}]")

    def set_preset(self, preset):
        preset = os.path.abspath(preset)
        self.ps_tcl.append(f"source {preset}")
        self.ps_tcl.append("set psu_cfg [apply_preset IPINST]")
        self.ps_tcl.append("set_property -dict $psu_cfg [get_ips {}]".format(self.ps_name))

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

    def add_ethernet(self, n=0, pads=None, if_type="gmii"):
        assert n < 3 and not n in self.gem_mac
        assert pads is not None

        # psu configuration
        self.config[f"PSU__ENET{n}__PERIPHERAL__ENABLE"] = 1
        self.config[f"PSU__ENET{n}__PERIPHERAL__IO"]     = "EMIO"
        self.config[f"PSU__ENET{n}__GRP_MDIO__ENABLE"]   = 1
        self.config[f"PSU__ENET{n}__GRP_MDIO__IO"]       = "EMIO"

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

        # psu MDIO connection
        mdio_mdc = Signal()
        mdio_i   = Signal()
        mdio_o   = Signal()
        mdio_t   = Signal()
        self.cpu_params.update({
            f"o_emio_enet{n}_mdio_mdc" : mdio_mdc,
            f"i_emio_enet{n}_mdio_i"   : mdio_i,
            f"o_emio_enet{n}_mdio_o"   : mdio_o,
            f"o_emio_enet{n}_mdio_t"   : mdio_t,
        })

        if if_type == "gmii":
            self.comb += pads.mdc.eq(mdio_mdc)

            self.specials += Instance("IOBUF",
                i_I   = mdio_o,
                o_O   = mdio_i,
                i_T   = mdio_t,
                io_IO = pads.mdio
            )
        else:
            phys_mdio_i = Signal()
            phys_mdio_o = Signal()
            phys_mdio_t = Signal()

            self.specials += Instance("IOBUF",
                i_I   = phys_mdio_o,
                o_O   = phys_mdio_i,
                i_T   = phys_mdio_t,
                io_IO = pads.mdio
            )

            self.comb += pads.rst_n.eq(~ResetSignal("sys"))

            mac_params = dict(
                i_tx_reset          = ResetSignal("sys"),
                i_rx_reset          = ResetSignal("sys"),
                i_clkin             = ClockSignal("rgmii"),

                # PS GEM: MDIO
                i_mdio_gem_mdc      = mdio_mdc,
                o_mdio_gem_i        = mdio_i,
                i_mdio_gem_o        = mdio_o,
                i_mdio_gem_t        = mdio_t,
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
                o_mdio_phy_mdc      = pads.mdc,
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
            self.gem_mac.append(n)

    def add_i2c(self, n, pads):
        assert n < 2 and not n in self.i2c_use
        assert pads is not None

        # PSU configuration.
        self.config[f"PSU__I2C{n}__PERIPHERAL__ENABLE"] = 1
        self.config[f"PSU__I2C{n}__PERIPHERAL__IO"]     = "EMIO"

        # Signals.
        scl_i   = Signal()
        scl_o   = Signal()
        scl_t   = Signal()
        sda_i   = Signal()
        sda_o   = Signal()
        sda_t   = Signal()

        # PSU connections.
        self.specials += [
            Instance("IOBUF",
                i_I   = sda_o,
                o_O   = sda_i,
                i_T   = sda_t,
                io_IO = pads.sda
            ),
            Instance("IOBUF",
                i_I   = scl_o,
                o_O   = scl_i,
                i_T   = scl_t,
                io_IO = pads.scl
            ),
        ]

        self.cpu_params.update({
            f"i_emio_i2c{n}_scl_i" : scl_i,
            f"o_emio_i2c{n}_scl_o" : scl_o,
            f"o_emio_i2c{n}_scl_t" : scl_t,
            f"i_emio_i2c{n}_sda_i" : sda_i,
            f"o_emio_i2c{n}_sda_o" : sda_o,
            f"o_emio_i2c{n}_sda_t" : sda_t,
        })

    def add_uart(self, n, pads):
        assert n < 2 and not n in self.uart_use
        assert pads is not None

        self.config[f"PSU__UART{n}__PERIPHERAL__ENABLE"] = 1
        self.config[f"PSU__UART{n}__PERIPHERAL__IO"]     = "EMIO"

        self.cpu_params.update({
            f"i_emio_uart{n}_rxd" : pads.rx,
            f"o_emio_uart{n}_txd" : pads.tx,
        })

    def add_gpios(self, pads):
        assert pads is not None

        # Parameters.
        pads_len = len(pads)

        # PSU configuration.
        self.config["PSU__GPIO_EMIO__PERIPHERAL__ENABLE"] = 1
        self.config["PSU__GPIO_EMIO__PERIPHERAL__IO"]     = len(pads)

        # Signals.
        gpio_i = Signal(pads_len)
        gpio_o = Signal(pads_len)
        gpio_t = Signal(pads_len)

        # PSU connections.
        for i in range(pads_len):
            self.specials += Instance("IOBUF",
                i_I   = gpio_o[i],
                o_O   = gpio_i[i],
                i_T   = gpio_t[i],
                io_IO = pads[i]
            )

        self.cpu_params.update({
            "i_emio_gpio_i" : gpio_i,
            "o_emio_gpio_o" : gpio_o,
            "o_emio_gpio_t" : gpio_t,
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
            for i in self.gem_mac:
                mac_tcl.append(f"set gem{i} [create_ip -vendor xilinx.com -name gmii_to_rgmii -module_name gem{i}]")
                mac_tcl.append("set_property -dict [ list \\")
                # FIXME: when more this sequence differs for the first and others
                mac_tcl.append("CONFIG.{} {} \\".format("C_EXTERNAL_CLOCK", '{{false}}'))
                mac_tcl.append("CONFIG.{} {} \\".format("C_USE_IDELAY_CTRL", '{{true}}'))
                mac_tcl.append("CONFIG.{} {} \\".format("C_PHYADDR", '{{' + str(8 + i) + '}}'))
                mac_tcl.append("CONFIG.{} {} \\".format("RGMII_TXC_SKEW", '{{' + str(0) + '}}'))
                mac_tcl.append("CONFIG.{} {} \\".format("SupportLevel", '{{Include_Shared_Logic_in_Core}}'))
                mac_tcl += [
                    f"] [get_ips gem{i}]",
                    f"generate_target all [get_ips gem{i}]",
                    f"synth_ip [get_ips gem{i}]"
                ]
            self.platform.toolchain.pre_synthesis_commands += mac_tcl
