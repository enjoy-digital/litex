#
# This file is part of LiteX.
#
# Copyright (c) 2022 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen                  import *

from litex.soc.cores.cpu        import CPU
from litex.soc.interconnect     import axi
from litex.soc.interconnect.csr import *


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
        self.uart_use       = []          # UART reserved ports.
        self.can_use        = []          # CAN reserved/used ports.
        self.pps            = Signal(4)   # Optional PPS (with gemX and PTP enabled)

        # [ 7: 0]: PL_PS_Group0 [128:121]
        # [15: 8]: PL_PS_Group1 [143:136]
        self.interrupt      = Signal(16)

        self.cd_ps = ClockDomain()

        self.ps_name = "ps"
        self.ps_tcl = []
        self.config = {
            'PSU__FPGA_PL0_ENABLE'       : 1, # enable pl_clk0
            'PSU__USE__IRQ0'             : 1, # enable PL_PS_Group0
            'PSU__NUM_F2P0__INTR__INPUTS': 8,
            'PSU__USE__IRQ1'             : 1, # enable PL_PS_Group1
            'PSU__NUM_F2P1__INTR__INPUTS': 8,
            'PSU__USE__M_AXI_GP1'        : 0,
        }
        rst_n = Signal()
        self.cpu_params = dict(
            o_pl_clk0=ClockSignal("ps"),
            o_pl_resetn0=rst_n,
            i_pl_ps_irq0 = self.interrupt[0: 8],
            i_pl_ps_irq1 = self.interrupt[8:16]
        )

        # Use GP0 as peripheral bus / CSR
        self.pbus = self.add_axi_gp_master(0)
        self.periph_buses.append(self.pbus)

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

    """
    Enable GEMx peripheral.
    ==========
    n: int
        GEM id (0, 1, 2, 3)
    pads:
        Physicals pads.
    clock_pads:
        Physicals tx/rx clock pads (required for SGMII).
    if_type: str
        Physical ethernet interface (gmii, rgmii, sgmii).
    reset: Signal
        Reset signal between PS and converter (required for SGMII).
    gt_location: str
        for SGMII Pads location (XaYb) (Required for SGMII).
    with_ptp: bool
        Enable PTP support.
    """
    def add_ethernet(self, n=0,
        pads       = None,
        clock_pads = None,
        if_type    = "gmii",
        gt_location= None,
        reset      = None,
        with_ptp   = False):
        assert n < 3 and not n in self.gem_mac
        assert pads is not None
        assert if_type in ["gmii", "rgmii", "sgmii"]

        # psu configuration
        self.config[f"PSU__ENET{n}__PERIPHERAL__ENABLE"] = 1
        self.config[f"PSU__ENET{n}__PERIPHERAL__IO"]     = "EMIO"
        self.config[f"PSU__ENET{n}__GRP_MDIO__ENABLE"]   = 1
        self.config[f"PSU__ENET{n}__GRP_MDIO__IO"]       = "EMIO"
        if with_ptp:
            self.config[f"PSU__ENET{n}__PTP__ENABLE"]    = 1

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
        elif if_type == "rgmii":
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
            self.gem_mac[n] = ("rgmii", None)
        else:
            assert gt_location is not None

            pwrgood         = Signal()
            status          = Signal(16)
            reset_done      = Signal(1)
            pma_reset_out   = Signal(1)
            mmcm_locked_out = Signal(1)
            gem_reset       = Signal()
            self.cd_sl_clk  = ClockDomain("sl_clk")


            sgmii_control = CSRStorage(fields=[
                CSRField("reset", size=1, reset=0, values=[
                    ("``0b0``", "Normal operations."),
                    ("``0b1``", "Reset mode."),
                ]),
                CSRField("tsu_inc_ctrl", size=2, reset=3, values=[
                    ("``0b00``", "Timer register increments based on the gem_tsu_ms value."),
                    ("``0b01``", "Timer register increments by an additional nanosecond."),
                    ("``0b10``", "Timer register increments by one nanosecond fewer."),
                    ("``0b11``", "Timer register increments as normal."),
                ])
            ])
            setattr(self, f"sgmii_control{n}", sgmii_control)

            sgmii_status = CSRStatus(fields=[
                CSRField("status",          size=16, offset=0),
                CSRField("pwrgood",         size=1,  offset=16),
                CSRField("reset_done",      size=1,  offset=17),
                CSRField("pma_reset_out",   size=1,  offset=18),
                CSRField("mmcm_locked_out", size=1,  offset=19),
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
                i_mdc                    = mdio_mdc,               # Management Data Clock
                i_mdio_i                 = mdio_o,                 # Management Data In
                o_mdio_o                 = mdio_i,                 # Management Data Out
                o_mdio_t                 = Open(),                 # Management Data Tristate

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

        # PSU configuration.
        self.config[f"PSU__CAN{n}__PERIPHERAL__ENABLE"] = 1
        self.config[f"PSU__CAN{n}__PERIPHERAL__IO"]     = "EMIO"
        self.config[f"PSU__CAN{n}__GRP_CLK__ENABLE"]    = {True: 0, False: 1}[ext_clk == None]

        if ext_clk:
            self.config[f"PSU__CAN{n}__GRP_CLK__IO"]               = f"MIO {ext_clk}"
            self.config[f"PSU__CRL_APB__CAN{n}_REF_CTRL__FREQMHZ"] = int(clk_freq / 1e6)

        # PS7 connections.
        self.cpu_params.update({
            f"i_emio_can{n}_phy_rx": pads.rx,
            f"o_emio_can{n}_phy_tx": pads.tx,
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
