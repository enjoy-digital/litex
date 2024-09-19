#
# This file is part of LiteX.
#
# Copyright (c) 2019-2024 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2024 MoTeC <www.motec.com.au>
# SPDX-License-Identifier: BSD-2-Clause

from migen.genlib.cdc    import MultiReg
from migen.fhdl.specials import Tristate

from litex.gen import *

from litex.build.io import SDROutput, SDRInput

from litex.soc.interconnect.csr import *
from litex.soc.interconnect     import stream
from litex.soc.interconnect     import wishbone

"""
HyperRAM Core.

Provides a HyperRAM Core with PHY, Core logic, and optional CSR interface for LiteX-based systems.
Supports variable latency, configurable clocking (4:1, 2:1), and burst operations.

Features:
- 8-bit or 16-bit Data-Width
- Variable latency: "fixed" or "variable".
- Configurable clock ratios: 4:1 or 2:1.
- Burst read/write support.
- Wishbone bus interface.
- Optional CSR interface for configuration.
"""

# HyperRAM Layout ----------------------------------------------------------------------------------

# IOs.
# ----
def hyperam_ios_layout(data_width=8):
    """IO layout for HyperRAM PHY."""
    return [
        ("rst_n",   1),
        ("clk",     1),
        ("cs_n",    1),
        ("dq_o",    data_width),
        ("dq_oe",   1),
        ("dq_i",    data_width),
        ("rwds_o",  data_width//8),
        ("rwds_oe", 1),
        ("rwds_i",  data_width//8),
    ]

# PHY.
# ----
def hyperram_phy_tx_layout(data_width=8):
    """Transmit layout for HyperRAM PHY."""
    return [
        ("cmd",     1),
        ("dat_w",   1),
        ("dat_r",   1),
        ("dq",      data_width),
        ("dq_oe",   1),
        ("rwds",    data_width//8),
        ("rwds_oe", 1),
    ]

def hyperram_phy_rx_layout(data_width=8):
    """Receive layout for HyperRAM PHY."""
    return [
        ("dq", data_width),
    ]

# Core.
# -----
def hyperram_core_tx_layout(data_width=8):
    """Transmit layout for HyperRAM Core."""
    return [
        ("dq",   data_width),
        ("rwds", data_width//8),
    ]

def hyperram_core_rx_layout(data_width=8):
    """"Receive layout for HyperRAM Core."""
    return [
        ("dq", data_width),
    ]

# HyperRAM Clk Gen ---------------------------------------------------------------------------------

class HyperRAMClkGen(LiteXModule):
    """
    HyperRAM Clock Generator Module.

    This module generates the necessary clock signals for the HyperRAM at configurable ratios
    (4:1, 2:1). It handles phase management and output clock signal generation to synchronize
    HyperRAM operations.
    """
    def __init__(self):
        self.phase       = Signal(2)
        self.rise        = Signal()
        self.fall        = Signal()
        self.cd_hyperram = ClockDomain()

        # # #

        # Clk Phase Generation from 4X Sys Clk.
        self.sync += self.phase.eq(self.phase + 1)
        self.comb += [
            self.rise.eq(self.phase == 0b11),
            self.fall.eq(self.phase == 0b01),
        ]

        # HyperRAM Clk Generation.
        self.comb += Case(self.phase, {
            0 : self.cd_hyperram.clk.eq(0),
            1 : self.cd_hyperram.clk.eq(1),
            2 : self.cd_hyperram.clk.eq(1),
            3 : self.cd_hyperram.clk.eq(0),
        })

# HyperRAM SDR PHY ---------------------------------------------------------------------------------

class HyperRAMSDRPHY(LiteXModule):
    """
    HyperRAM Single Data Rate (SDR) PHY Module.

    This module provides a physical interface layer for HyperRAM using a Single Data Rate
    (SDR) approach. It manages data transmission and reception, IO connections, and clock
    generation for the HyperRAM interface.

    Parameters:
    - pads    : External pads to connect the PHY signals.
    - dq_i_cd : Clock domain for data input signals.
    """
    def __init__(self, pads, dq_i_cd="sys"):
        self.data_width = data_width = self.get_data_width(pads)
        self.sink       =       sink = stream.Endpoint(hyperram_phy_tx_layout(data_width)) # TX.
        self.source     =     source = stream.Endpoint(hyperram_phy_rx_layout(data_width)) # RX.
        self.ios        =        ios = Record(hyperam_ios_layout(data_width))              # IOs.

        # # #

        # Parameters.
        # -----------
        assert data_width in [8, 16]

        # Clk Gen.
        # --------
        self.clk_gen = clk_gen = HyperRAMClkGen()

        # Clk/CS/DQ/RWDS Output.
        # ----------------------
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            ios.cs_n.eq(1),
            If(sink.valid & clk_gen.rise,
                NextState("RUN")
            )
        )
        fsm.act("RUN",
            If(sink.valid,
                ios.clk.eq(1),
                ios.dq_o.eq(   sink.dq),
                ios.dq_oe.eq(  sink.dq_oe),
                ios.rwds_o.eq( sink.rwds),
                ios.rwds_oe.eq(sink.rwds_oe),
                If(clk_gen.rise | clk_gen.fall,
                    sink.ready.eq(1)
                ),
            ).Else(
                NextState("END")
             )
        )
        fsm.act("END",
            source.valid.eq(1),
            source.last.eq(1),
            If(source.ready,
                NextState("IDLE")
            )
        )

        # DQ Input.
        # ---------
        rwds_i    = ios.rwds_i[0]
        rwds_i_d  = Signal()
        dq_i      = ios.dq_i
        _sync = getattr(self.sync, dq_i_cd)
        _sync += rwds_i_d.eq(rwds_i)
        self.comb += [
            # When waiting a DQ read...
            If(sink.valid & sink.dat_r,
                # Sample DQ on RWDS edge.
                If(rwds_i ^ rwds_i_d,
                    source.valid.eq(1),
                    source.dq.eq(dq_i),
                )
            )
        ]

        # Connect IOs to Pads.
        # --------------------
        self.connect_to_pads(pads, dq_i_cd)

    def get_data_width(self, pads):
        """Returns data width based on pads."""
        if not hasattr(pads.dq, "oe"):
            return len(pads.dq)
        else:
            return len(pads.dq.o)

    def connect_to_pads(self, pads, dq_i_cd):
        """Connects PHY signals to external pads."""
        with_tristate = not hasattr(pads, "dq_oe") and not hasattr(pads, "rwds_oe")

        # CS.
        # ---
        self.specials += MultiReg(i=self.ios.cs_n, o=pads.cs_n, n=1)

        # Rst Output.
        # -----------
        self.specials += MultiReg(i=self.ios.rst_n, o=pads.rst_n, n=1)

        # Clk Output.
        # -----------
        # Single Ended Clk.
        if hasattr(pads, "clk"):
            self.specials += MultiReg(i=self.ios.clk & ClockSignal("hyperram"), o=pads.clk, n=3)
        # Differential Clk.
        elif hasattr(pads, "clk_p"):
            self.specials += MultiReg(i=  self.ios.clk & ClockSignal("hyperram"),  o=pads.clk_p, n=3)
            self.specials += MultiReg(i=~(self.ios.clk & ClockSignal("hyperram")), o=pads.clk_n, n=3)
        else:
            raise ValueError

        # DQ Output/Input.
        # ----------------
        if with_tristate:
            dq_o  = Signal(self.data_width)
            dq_oe = Signal()
            dq_i  = Signal(self.data_width)
            self.specials += Tristate(pads.dq,
                o   = dq_o,
                oe  = dq_oe,
                i   = dq_i,
            )
        else:
            dq_o  = pads.dq_o
            dq_oe = pads.dq_oe
            dq_i  = pads.dq_i
        self.specials += MultiReg(i=self.ios.dq_oe, o=dq_oe, n=3)
        for n in range(self.data_width):
            self.specials += [
                MultiReg(i=self.ios.dq_o[n], o=dq_o[n], n=3),
                MultiReg(o=self.ios.dq_i[n], i=dq_i[n], n=1, odomain=dq_i_cd),
            ]

        # RDWS Output/Input.
        # ------------------
        if with_tristate:
            rwds_o  = Signal(self.data_width//8)
            rwds_oe = Signal()
            rwds_i  = Signal(self.data_width//8)
            self.specials += Tristate(pads.rwds,
                o   = rwds_o,
                oe  = rwds_oe,
                i   = rwds_i,
            )
        else:
            rwds_o  = pads.rwds_o
            rwds_oe = pads.rwds_oe
            rwds_i  = pads.rwds_i
        self.specials += MultiReg(i=self.ios.rwds_oe, o=rwds_oe, n=3)
        for n in range(self.data_width//8):
            self.specials += [
                MultiReg(i=self.ios.rwds_o[n], o=rwds_o[n], n=3),
                MultiReg(o=self.ios.rwds_i[n], i=rwds_i[n], n=1, odomain=dq_i_cd),
            ]

# HyperRAM Core ------------------------------------------------------------------------------------

class HyperRAMCore(LiteXModule):
    """
    HyperRAM Core Logic Module

    This module implements the main logic for HyperRAM memory operations, supporting variable
    latency, configurable clocking, and a Wishbone interface for data transfer. It manages read and
    write operations and interacts with the PHY layer for memory access.

    Parameters:
    - phy           : SDR PHY interface for data transmission and reception.
    - latency       : Default latency setting.
    - latency_mode  : Latency mode "fixed" or "variable".
    - clk_ratio     : Clock ratio "4:1" or "2:1".
    - with_bursting : Enable or disable burst mode.
    """
    def __init__(self, phy, latency=7, latency_mode="fixed", clk_ratio="4:1", with_bursting=True):
        self.bus    = bus    = wishbone.Interface(data_width=32, address_width=32, addressing="word")
        self.reg    = reg    = wishbone.Interface(data_width=16, address_width=4,  addressing="word")
        self.source = source = stream.Endpoint(hyperram_phy_tx_layout(phy.data_width)) # TX.
        self.sink   = sink   = stream.Endpoint(hyperram_phy_rx_layout(phy.data_width)) # RX.

        # # #

        # Config/Reg Interface.
        # ---------------------
        self.rst          = Signal(reset=0)
        self.latency      = Signal(8, reset=latency)
        self.latency_mode = Signal(reset={"fixed": 0b0, "variable": 0b1}[latency_mode])

        # Signals.
        # --------
        self.cmd           = cmd           = Signal(48)
        self.cycles        = cycles        = Signal(8)
        self.latency_x2    = latency_x2    = Signal()
        self.bus_latch     = bus_latch     = Signal()
        self.bus_cti       = bus_cti       = Signal(3)
        self.bus_we        = bus_we        = Signal()
        self.bus_sel       = bus_sel       = Signal(4)
        self.bus_adr       = bus_adr       = Signal(32)
        self.bus_dat_w     = bus_dat_w     = Signal(32)
        self.burst_w       = burst_w       = Signal()
        self.burst_r       = burst_r       = Signal()
        self.burst_r_first = burst_r_first = Signal()

        # PHY.
        # ----
        self.comb += phy.ios.rst_n.eq(~self.rst)

        # Converters.
        # -----------
        self.cmd_tx_conv = cmd_tx_conv = stream.Converter(48, 8, reverse=True)
        self.reg_tx_conv = reg_tx_conv = stream.StrideConverter(
            description_from = hyperram_core_tx_layout(16),
            description_to   = hyperram_core_tx_layout(8),
            reverse          = True
        )
        self.reg_rx_conv = reg_rx_conv = stream.StrideConverter(
            description_from = hyperram_core_rx_layout(8),
            description_to   = hyperram_core_rx_layout(16),
            reverse          = True
        )
        self.dat_tx_conv = dat_tx_conv = stream.StrideConverter(
            description_from = hyperram_core_tx_layout(32),
            description_to   = hyperram_core_tx_layout(phy.data_width),
            reverse          = True
        )
        self.dat_rx_conv = dat_rx_conv = stream.StrideConverter(
            description_from = hyperram_core_rx_layout(phy.data_width),
            description_to   = hyperram_core_rx_layout(32),
            reverse          = True
        )
        self.comb += [
            If(reg.stb & ~reg.we,
                sink.connect(reg_rx_conv.sink),
            ).Else(
                sink.connect(dat_rx_conv.sink),
            ),
            dat_rx_conv.source.ready.eq(1), # Always ready.
            reg_rx_conv.source.ready.eq(1), # Always ready.
        ]

        # Command/Address Gen.
        # --------------------
        ashift = {8:1, 16:0}[phy.data_width]
        self.comb += [
            # Register Command Gen.
            If(reg.stb,
                cmd[47].eq(~reg.we), # R/W#.
                cmd[46].eq(1),       # Register Space.
                cmd[45].eq(1),       # Burst Type (Linear).
                Case(reg.adr, {
                    0 : cmd[0:40].eq(0x00_00_00_00_00), # Identification Register 0 (Read Only).
                    1 : cmd[0:40].eq(0x00_00_00_00_01), # Identification Register 1 (Read Only).
                    2 : cmd[0:40].eq(0x00_01_00_00_00), # Configuration Register 0.
                    3 : cmd[0:40].eq(0x00_01_00_00_01), # Configuration Register 1.
                }),
            # Data Command Gen.
            ).Else(
                cmd[47].eq(~bus.we),                   # R/W#.
                cmd[46].eq(0),                         # Memory Space.
                cmd[45].eq(1),                         # Burst Type (Linear).
                cmd[    16:45].eq(bus.adr[3-ashift:]), # Row & Upper Column Address.
                cmd[ashift: 3].eq(bus.adr),            # Lower Column Address.
            )
        ]

        # FSM.
        # ----
        self.fsm = fsm = FSM(reset_state="IDLE")

        # IDLE State.
        fsm.act("IDLE",
            If((bus.cyc & bus.stb) | reg.stb,
                NextState("CMD-ADDRESS")
            )
        )

        # Cmd/Address State.
        fsm.act("CMD-ADDRESS",
            cmd_tx_conv.sink.valid.eq(1),
            cmd_tx_conv.sink.data.eq(cmd),
            cmd_tx_conv.source.connect(source, keep={"valid", "ready"}),
            source.cmd.eq(1),
            source.dq.eq(cmd_tx_conv.source.data),
            source.dq_oe.eq(1),
            If(cmd_tx_conv.sink.ready,
                If(reg.stb & reg.we,
                    NextState("REG-WRITE")
                ).Else(
                    NextState("LATENCY-WAIT")
                )
            )
        )

        # Latency Wait State.
        fsm.act("LATENCY-WAIT",
            # Sample rwds_i here (FSM is ahead) to determine X1 or X2 latency.
            If(cycles == 0,
                NextValue(latency_x2, phy.ios.rwds_i[0] | (latency_mode == "fixed"))
            ),
            source.valid.eq(1),
            If(source.ready,
                NextValue(cycles, cycles + 1),
                # Wait for 1X/2X Latency...
                # Latency Count starts 1 HyperRAM Clk before the end of the Cmd.
                If(cycles == (2*((self.latency_x2 + 1)*self.latency - 1) - 1),
                    If(reg.stb & ~reg.we,
                        NextState("REG-READ")
                    ).Else(
                        bus_latch.eq(1),
                        # Bus Write.
                        If(bus.we,
                            bus.ack.eq(1),
                            NextState("DAT-WRITE")
                        # Bus Read.
                        ).Else(
                            NextValue(burst_r_first, 1),
                            NextState("DAT-READ")
                        )
                    )
                )
            )
        )

        # Register Write State.
        fsm.act("REG-WRITE",
            reg_tx_conv.sink.valid.eq(1),
            reg_tx_conv.sink.dq.eq(reg.dat_w),
            reg_tx_conv.source.connect(source),
            source.dat_w.eq(1),
            source.dq_oe.eq(1),
            If(reg_tx_conv.sink.ready,
                reg.ack.eq(1),
                NextState("END")
            )
        )

        # Register Read State.
        fsm.act("REG-READ",
            source.valid.eq(1),
            source.dat_r.eq(1),
            If(reg_rx_conv.source.valid,
                reg.ack.eq(1),
                reg.dat_r.eq(reg_rx_conv.source.dq),
                NextState("END"),
            )
        )

        # Data Write State.
        self.sync += [
            If(bus_latch,
                bus_cti.eq(bus_cti),
                bus_we.eq(bus.we),
                bus_sel.eq(bus.sel),
                bus_adr.eq(bus.adr),
                bus_dat_w.eq(bus.dat_w),
            )
        ]
        self.comb += burst_w.eq(
            # Notified Incrementing Burst.
            (bus_cti == 0b010) |
            # Detected Incrementing Burst.
            ((bus.we == bus_we) & (bus.adr == (bus_adr + 1))),
        )
        fsm.act("DAT-WRITE",
            dat_tx_conv.sink.valid.eq(1),
            dat_tx_conv.sink.dq.eq(bus_dat_w),
            dat_tx_conv.sink.rwds.eq(~bus_sel),
            dat_tx_conv.source.connect(source),
            source.dq_oe.eq(1),
            source.rwds_oe.eq(1),
            source.dat_w.eq(1),
            If(dat_tx_conv.sink.ready,
                # Ack while Incrementing Burst ongoing...
                bus.ack.eq(with_bursting & bus.cyc & bus.stb & burst_w),
                # If Ack, stay in DAT-WRITE.
                If(bus.ack,
                    bus_latch.eq(1),
                    NextState("DAT-WRITE")
                # ..else exit.
                ).Else(
                    NextState("END")
                )
            )
        )

        # Data Read State.
        self.comb += burst_r.eq(
            # Notified Incrementing Burst.
            (bus_cti == 0b10) |
            # Detected Incrementing Burst.
            ((bus.we == bus_we) & (bus.adr == (bus_adr + 1))),
        )
        fsm.act("DAT-READ",
            source.valid.eq(1),
            source.dat_r.eq(1),
            If(dat_rx_conv.source.valid,
                NextValue(burst_r_first, 0),
                # Ack on first or while Incrementing Burst ongoing...
                bus.ack.eq(burst_r_first | (with_bursting & bus.cyc & bus.stb & burst_r)),
                bus.dat_r.eq(dat_rx_conv.source.dq),
                # If Ack, stay in DAT-READ to anticipate next read...
                If(bus.ack,
                    bus_latch.eq(1),
                    NextState("DAT-READ")
                # ..else exit.
                ).Else(
                    NextState("END")
                )
            )
        )
        fsm.act("END",
            NextValue(cycles, cycles + 1),
            If(cycles == 8, # FIXME.
                NextState("IDLE")
            )
        )
        fsm.finalize()
        self.sync += If(fsm.next_state != fsm.state, cycles.eq(0))

# HyperRAM -----------------------------------------------------------------------------------------

class HyperRAM(LiteXModule):
    """
    HyperRAM Top-Level Module.

    This module integrates the PHY and Core modules to provide a complete interface for HyperRAM
    communication in LiteX-based systems. It supports configurable latency, clock ratio, and an
    optional CSR interface for advanced configuration and status monitoring.

    Parameters:
    - pads         : External pads for the HyperRAM interface.
    - latency      : Default latency setting.
    - latency_mode : Latency mode "fixed" or "variable".
    - sys_clk_freq : System clock frequency.
    - clk_ratio    : Clock ratio "4:1" or "2:1".
    - with_csr     : Include CSR support.
    - dq_i_cd      : Clock domain for data input.
    """
    def __init__(self, pads, latency=7, latency_mode="fixed", sys_clk_freq=100e6, clk_ratio="4:1", with_bursting=True, with_csr=True, dq_i_cd=None):
        self.bus  = bus = wishbone.Interface(data_width=32, address_width=32, addressing="word")

        # # #

        # Parameters.
        # -----------
        self.pads      = pads
        self.clk_ratio = clk_ratio
        assert latency_mode in ["fixed", "variable"]
        assert clk_ratio    in ["4:1", "2:1"]

        # PHY.
        # ----
        phy_cd = {
            "4:1": "sys",
            "2:1": "sys2x",
        }[clk_ratio]
        if dq_i_cd is None:
            dq_i_cd = phy_cd
        self.phy = phy = ClockDomainsRenamer(phy_cd)(HyperRAMSDRPHY(pads=pads, dq_i_cd=dq_i_cd))

        # FIFOs.
        # ------
        self.tx_fifo = tx_fifo = ClockDomainsRenamer(phy_cd)(stream.SyncFIFO(hyperram_phy_tx_layout(phy.data_width), 4))
        self.rx_fifo = rx_fifo = ClockDomainsRenamer(phy_cd)(stream.SyncFIFO(hyperram_phy_rx_layout(phy.data_width), 4))

        # CDCs.
        # -----
        self.tx_cdc = tx_cdc = stream.ClockDomainCrossing(
            layout = hyperram_phy_tx_layout(phy.data_width),
            cd_from = "sys",
            cd_to   = phy_cd,
            depth   = 4,
        )
        self.rx_cdc = rx_cdc = stream.ClockDomainCrossing(
            layout = hyperram_phy_rx_layout(phy.data_width),
            cd_from = dq_i_cd,
            cd_to   = "sys",
            depth   = 4,
        )

        # Core.
        # -----
        self.core = core = HyperRAMCore(
            phy           = phy,
            latency       = latency,
            latency_mode  = latency_mode,
            clk_ratio     = clk_ratio,
            with_bursting = with_bursting,
        )
        self.comb += bus.connect(core.bus)

        # Pipelines.
        # ---------
        self.tx_pipeline = stream.Pipeline(
            core,
            tx_cdc,
            tx_fifo,
            phy,
        )
        self.rx_pipeline = stream.Pipeline(
            phy,
            rx_fifo,
            rx_cdc,
            core,
        )

        # CSRs.
        # -----
        if with_csr:
            self.add_csr(default_latency=latency, latency_mode=latency_mode)

    def add_csr(self, default_latency=7, latency_mode="fixed"):
        # Config/Status Interface.
        # ------------------------
        self.config = CSRStorage(fields=[
            CSRField("rst",     offset=0, size=1, pulse=True, description="HyperRAM Rst."),
            CSRField("latency", offset=8, size=8,             description="HyperRAM Latency (X1).", reset=default_latency),
        ])
        self.comb += [
            self.core.rst.eq(    self.config.fields.rst),
            self.core.latency.eq(self.config.fields.latency),
        ]
        self.status = CSRStatus(fields=[
            CSRField("latency_mode", offset=0, size=1, values=[
                ("``0b0``", "Fixed Latency."),
                ("``0b1``", "Variable Latency."),
            ], reset={"fixed": 0b0, "variable": 0b1}[latency_mode]),
            CSRField("clk_ratio", offset=1, size=4, values=[
                ("``4``", "HyperRAM Clk = Sys Clk/4."),
                ("``2``", "HyperRAM Clk = Sys Clk/2."),
            ], reset={"4:1": 4, "2:1": 2}[self.clk_ratio]),
        ])

        # Reg Interface.
        # --------------
        self.reg_control = CSRStorage(fields=[
            CSRField("write", offset=0, size=1, pulse=True, description="Issue Register Write."),
            CSRField("read",  offset=1, size=1, pulse=True, description="Issue Register Read."),
            CSRField("addr",  offset=8, size=2, values=[
                ("``0b00``", "Identification Register 0 (Read Only)."),
                ("``0b01``", "Identification Register 1 (Read Only)."),
                ("``0b10``", "Configuration Register 0."),
                ("``0b11``", "Configuration Register 1."),
            ]),
        ])
        self.reg_status = CSRStatus(fields=[
            CSRField("done", offset=0, size=1, description="Register Access Done."),
        ])
        self.reg_wdata = CSRStorage(16, description="Register Write Data.")
        self.reg_rdata = CSRStatus( 16, description="Register Read Data.")

        self.reg_fsm = reg_fsm = FSM(reset_state="IDLE")
        reg_fsm.act("IDLE",
            self.reg_status.fields.done.eq(1),
            If(self.reg_control.fields.write,
                NextState("WRITE"),
            ).Elif(self.reg_control.fields.read,
                NextState("READ"),
            )
        )
        reg_fsm.act("WRITE",
            self.core.reg.stb.eq(1),
            self.core.reg.we.eq(1),
            self.core.reg.adr.eq(self.reg_control.fields.addr),
            self.core.reg.dat_w.eq(self.reg_wdata.storage),
            If(self.core.reg.ack,
                NextState("IDLE"),
            )
        )
        reg_fsm.act("READ",
            self.core.reg.stb.eq(1),
            self.core.reg.we.eq(0),
            self.core.reg.adr.eq(self.reg_control.fields.addr),
            If(self.core.reg.ack,
                NextValue(self.reg_rdata.status, self.core.reg.dat_r),
                NextState("IDLE"),
            )
        )
