#
# This file is part of LiteX.
#
# Copyright (c) 2022-2023 MoTeC
# Copyright (c) 2022-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *
from litex.gen.genlib.misc import WaitTimer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *
from litex.soc.interconnect import stream
from litex.soc.interconnect import wishbone

# Constants / Layouts / Helpers --------------------------------------------------------------------

_nslots_max = 16

# SPI Layout
def spi_layout(data_width=32, be_width=4, cs_width=1):
    return [
        ("data", data_width),
        ("be",   be_width),
        ("cs",   cs_width)
    ]

# SPI Slot Constants.

SPI_SLOT_MODE_0             = 0b00
SPI_SLOT_MODE_3             = 0b11

SPI_SLOT_LENGTH_32B         = 0b00
SPI_SLOT_LENGTH_16B         = 0b01
SPI_SLOT_LENGTH_8B          = 0b10

SPI_SLOT_BITORDER_MSB_FIRST = 0b0
SPI_SLOT_BITORDER_LSB_FIRST = 0b1

# SPI Master ---------------------------------------------------------------------------------------

class SPIMaster(LiteXModule):
    """4-wire SPI Master

    Provides a simple and minimal hardware SPI Master with Mode0 to Mode3 support.
    """
    def __init__(self, pads, data_width, sys_clk_freq, clk_settle_time=20e-9):
        # Config.
        self.loopback    = Signal()
        self.clk_divider = Signal(16)
        self.mode        = Signal(2)

        # Interface.
        self.start  = Signal()
        self.length = Signal(8)
        self.done   = Signal()
        self.irq    = Signal()
        self.mosi   = Signal(data_width)
        self.miso   = Signal(data_width)
        self.cs     = Signal(len(pads.cs_n))

        # # #

        # Signals ----------------------------------------------------------------------------------
        # CPHA — SPI Clock Phase Bit
        # 1 = Sampling of data at even edges (2,4,6,...,16) of the SCK clock
        # 0 = Sampling of data at odd edges (1,3,5,...,15) of the SCK clock
        cpha       = self.mode[0]
        # CPOL — SPI Clock Polarity Bit
        # 1 = Active-low. In idle state SCK is high: odd edges are falling
        # 0 = Active-high. In idle state SCK is low: odd edges are rising
        cpol       = self.mode[1]

        clk        = Signal()
        clk_d      = Signal()
        clk_enable = Signal()
        clk_run    = Signal()
        clk_count  = Signal(16)
        clk_odd    = Signal()
        clk_even   = Signal()

        data_count = Signal(8)

        mosi_shift = Signal()
        mosi_data  = Signal(data_width)

        miso       = Signal()
        miso_shift = Signal()
        miso_data  = Signal(data_width)

        # Chip Select generation -------------------------------------------------------------------

        self.sync += pads.cs_n.eq(~self.cs)
        # TODO: need to guarantee cs_n remains asserted for 1/2 SCK after edge 16
        # at the end of a transfer, however next byte for this transfer can start
        # in this region

        # Clk Generation ---------------------------------------------------------------------------

        clk_settle = WaitTimer(int(sys_clk_freq*clk_settle_time))
        self.submodules += clk_settle

        clk_fsm = FSM(reset_state="IDLE")
        self.submodules += clk_fsm
        clk_fsm.act("IDLE",
            If(self.start,
                NextState("SETTLE")
            )
        )
        clk_fsm.act("SETTLE",
            clk_settle.wait.eq(1),
            If(clk_settle.done,
                NextState("RUN")
            )
        )
        clk_fsm.act("RUN",
            clk_enable.eq(1),
            If(self.done,
                NextState("IDLE")
            )
        )
        self.sync += [
            If(clk_enable,
                clk_count.eq(clk_count + 1),
                If(clk_count == self.clk_divider[1:],
                    clk.eq(~clk),
                    clk_count.eq(0)
                ),
                If(clk_odd,
                    clk_run.eq(1))
            ).Else(
                clk.eq(0),
                clk_count.eq(0),
                clk_run.eq(0)
            )
        ]
        self.comb += pads.clk.eq((clk & ~self.done) ^ cpol)
        self.sync += clk_d.eq(clk)
        self.comb += [
            If(clk_enable,
                clk_odd.eq(  clk  & ~clk_d),
                clk_even.eq(~clk  &  clk_d),
            )
        ]

        # Master FSM -------------------------------------------------------------------------------

        self.master_fsm = master_fsm = FSM(reset_state="IDLE")
        master_fsm.act("IDLE",
            self.done.eq(1),
            If(self.start,
                self.done.eq(0),
                NextState("RUN")
            ),
            NextValue(data_count, 0),
        )
        master_fsm.act("RUN",
            clk_enable.eq(1),
            # regardless of CPHA update data_count on even edge
            If(clk_even,
                NextValue(data_count, data_count + 1),
                If(data_count == (self.length - 1),
                    self.irq.eq(1),
                    NextState("IDLE")
                )
            )
        )

        # Master Out Slave In (MOSI) generation ----------------------------------------------------
        #  - Shift on clk odd edge (** but not the first one **) for:
        #    - Mode 1 & 3 (CPHA=1)
        #  - Shift on clk even edge for:
        #    - Mode 0 & 2 (CPHA=0)

        self.comb += Case(cpha, {
            0b0 : mosi_shift.eq(clk_even),
            0b1 : mosi_shift.eq(clk_odd & clk_run),
        })
        self.sync += [
            If(self.start,
                mosi_data.eq(self.mosi)
            ).Elif(mosi_shift,
                mosi_data.eq(Cat(Signal(), mosi_data))
            ),
        ]
        self.comb += pads.mosi.eq(mosi_data[-1])

        # Master In Slave Out (MISO) capture -------------------------------------------------------
        #  - Clocked out by slave on odd edge, so captured on even edge for:
        #     - Mode 1 & 3 (CPHA=1)
        #  - Clocked out by slave on even edge, so captured on odd edge for:
        #     - Mode 0 & 2 (CPHA=0)
        # NOTE: The data capture should occur on the subsequent clock edge.  E.g. for CPHA=1,
        #       falling clock edge is bit of data clocked out. On the subsequent raising
        #       edge the MISO data should be captured.

        self.comb += Case(cpha, {
            0b0 : miso_shift.eq(clk_odd),
            0b1 : miso_shift.eq(clk_even),
        })
        self.comb += Case(self.loopback, {
            0b0 : miso.eq(pads.miso),
            0b1 : miso.eq(pads.mosi),
        })
        self.sync += [
            If(miso_shift,
                miso_data.eq(Cat(miso, miso_data))
            )
        ]
        self.comb += self.miso.eq(miso_data)

# SPI FIFO -----------------------------------------------------------------------------------------

@ResetInserter()
class SPIFIFO(LiteXModule):
    def __init__(self, data_width=32, nslots=1, depth=32):
        self.fifo = stream.SyncFIFO(layout=spi_layout(
            data_width = data_width,
            be_width   = data_width//8,
            cs_width   = nslots
        ), depth=depth, buffered=True)
        for name in ["level", "sink", "source"]:
            setattr(self, name, getattr(self.fifo, name))

# SPI Ctrl -----------------------------------------------------------------------------------------

class SPICtrl(LiteXModule):
    autocsr_exclude = {"ev"}
    def __init__(self, nslots=1,
        # TX.
        default_tx_enable = 0b1,
        # RX.
        default_rx_enable = 0b1,
        # Slots.
        default_slot_enable   = 0b1,
        default_slot_mode     = SPI_SLOT_MODE_3,
        default_slot_length   = SPI_SLOT_LENGTH_32B,
        default_slot_bitorder = SPI_SLOT_BITORDER_MSB_FIRST,
        default_slot_loopback = 0b1,
        default_slot_divider  = 2,
    ):
        self.nslots        = nslots
        self.slot_controls = []
        self.slot_status   = []

        # Create TX/RX Control/Status registers.
        self.tx_control  = CSRStorage(fields=[
            CSRField("enable", size=1, offset=0, values=[
                    ("``0b0``", "TX Disabled."),
                    ("``0b1``", "TX Enabled."),
            ], reset=default_tx_enable),
            CSRField("threshold", size=16, offset=16, description="TX_FIFO IRQ Threshold.", reset=0)
        ])
        self.tx_status  = CSRStatus(fields=[
            CSRField("ongoing", size=1, offset=0, values=[
                    ("``0b0``", "TX Xfer idle."),
                    ("``0b1``", "TX Xfer ongoing."),
            ]),
            CSRField("empty", size=1, offset=1, values=[
                    ("``0b0``", "TX FIFO Empty."),
                    ("``0b1``", "TX FIFO Empty."),
            ]),
            CSRField("full", size=1, offset=2, values=[
                    ("``0b0``", "TX FIFO Full."),
                    ("``0b1``", "TX FIFO Full."),
            ]),
            CSRField("level", size=16, offset=16, description="TX FIFO Level.")
        ])
        self.rx_control  = CSRStorage(fields=[
            CSRField("enable", size=1, offset=0, values=[
                    ("``0b0``", "RX Disabled."),
                    ("``0b1``", "RX Enabled."),
            ], reset=default_rx_enable),
            CSRField("threshold", size=16, offset=16, description="RX_FIFO IRQ Threshold.", reset=0)
        ])
        self.rx_status  = CSRStatus(fields=[
            CSRField("ongoing", size=1, offset=0, values=[
                    ("``0b0``", "RX Xfer idle."),
                    ("``0b1``", "RX Xfer ongoing."),
            ]),
            CSRField("empty", size=1, offset=1, values=[
                    ("``0b0``", "RX FIFO Empty."),
                    ("``0b1``", "RX FIFO Empty."),
            ]),
            CSRField("full", size=1, offset=2, values=[
                    ("``0b0``", "RX FIFO Full."),
                    ("``0b1``", "RX FIFO Full."),
            ]),
            CSRField("level", size=16, offset=16, description="RX FIFO Level.")
        ])

        # Create IRQ registers.
        self.ev = EventManager()
        self.ev.tx = EventSourceProcess(edge="rising")
        self.ev.rx = EventSourceProcess(edge="rising")
        self.ev.finalize()
        self.comb += [
            # TX IRQ when FIFO's level <= TX Threshold.
            self.ev.tx.trigger.eq(self.tx_status.fields.level <= self.tx_control.fields.threshold),
            # RX IRQ when FIFO's level > RX Threshold.
            self.ev.rx.trigger.eq(self.rx_status.fields.level > self.rx_control.fields.threshold),
        ]

        # Create Slots Control/Status registers.
        for slot in range(nslots):
            control = CSRStorage(name=f"slot_control{slot}", fields=[
                CSRField("enable", size=1, offset=0, values=[
                    ("``0b0``", "Slot Disabled."),
                    ("``0b1``", "Slot Enabled."),
                ], reset=default_slot_enable),
                CSRField("mode", size=2, offset=1, values=[
                    ("``0b00``", "SPI Mode 0 (CPOL=0, CPHA=0)."),
                    ("``0b01``", "SPI Mode 1 (CPOL=0, CPHA=1)."),
                    ("``0b10``", "SPI Mode 2 (CPOL=1, CPHA=0)."),
                    ("``0b11``", "SPI Mode 3 (CPOL=1, CPHA=1)."),
                ], reset=default_slot_mode),
                CSRField("length", size=2, offset=3, values=[
                    ("``0b00``", "32-bit Max."),
                    ("``0b01``", "16-bit Max."),
                    ("``0b10``", " 8-bit Max."),
                    ("``0b11``", "Reserved."),
                ], reset=default_slot_length),
                CSRField("bitorder", size=1, offset=5, values=[
                    ("``0b0``", "MSB-First."),
                    ("``0b1``", "LSB-First."),
                ], reset=default_slot_bitorder),
                CSRField("loopback", size=1, offset=6, values=[
                    ("``0b0``", "Loopback Disabled."),
                    ("``0b1``", "Loopback Enabled."),
                ], reset=default_slot_loopback),
                CSRField("divider", size=16, offset=16, values=[
                    ("``0x0000``", "Reserved."),
                    ("``0x0001``", "Reserved."),
                    ("``0x0002``", "SPI-Clk = Sys-Clk/2."),
                    ("``0x0004``", "SPI-Clk = Sys-Clk/4."),
                    ("``0xxxxx``", "SPI-Clk = Sys-Clk/xxxxx."),
                ], reset=default_slot_divider)
            ])
            status = CSRStatus(name=f"slot_status{slot}") # CHECKME: Useful?
            setattr(self, f"slot_control{slot}", control)
            setattr(self, f"slot_status{slot}",  status)
            self.slot_controls.append(control)
            self.slot_status.append(status)

    def get_ctrl(self, name, slot=None, cs=None):
        assert not ((slot is None) and (cs is None))
        if cs is None:
            cs = Signal(self.nslots)
            self.comb += cs.eq(1<<slot)
        bits  = len(getattr(self.slot_controls[0].fields, name))
        ctrl  = Signal(bits)
        cases = {}
        for i in range(self.nslots):
            cases[1<<i] = ctrl.eq(getattr(self.slot_controls[i].fields, name))
        self.comb += Case(cs, cases)
        return ctrl

# SPI TX MMAP --------------------------------------------------------------------------------------

class SPITXMMAP(LiteXModule):
    def __init__(self, ctrl, data_width=32, nslots=1, origin=0x0000_0000):
        self.bus    = bus    = wishbone.Interface(data_width=data_width)
        self.source = source = stream.Endpoint(spi_layout(
            data_width = data_width,
            be_width   = data_width//8,
            cs_width   = nslots
        ))

        # # #

        valid_slot = Signal()
        valid_sel  = Signal()

        # Compute/Check Slot.
        slot = (bus.adr - origin//(data_width//8))
        self.comb += valid_slot.eq(slot < nslots)

        # Get Slot Enable.
        slot_enable = ctrl.get_ctrl("enable", slot=slot)

        # Check Sel.
        self.comb += Case(bus.sel, {
            0b0001 : valid_sel.eq(1), #  8-bit aligned access.
            0b0011 : valid_sel.eq(1), # 16-bit aligned access.
            0b1111 : valid_sel.eq(1), # 32-bit aligned access.
        })

        # FSM.
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(bus.stb & bus.cyc & bus.we,
                # Return error on invalid access.
                If(~valid_slot | ~valid_sel,
                    NextState("ERROR")
                # Return error when slot is disabled.
                ).Elif(~slot_enable,
                    NextState("ERROR")
                # Return error when downstream is not ready.
                ).Elif(~source.ready,
                    NextState("ERROR")
                # Else Write.
                ).Else(
                    NextState("WRITE")
                )
            )
        )
        fsm.act("WRITE",
            source.valid.eq(1),
            source.data.eq(bus.dat_w),
            source.be.eq(bus.sel),
            source.cs.eq(1<<slot),
            If(source.ready,
                NextState("ACK")
            )
        )
        fsm.act("ACK",
            bus.ack.eq(1),
            NextState("IDLE")
        )
        fsm.act("ERROR",
            bus.ack.eq(1),
            bus.err.eq(1),
            NextState("IDLE")
        )

# SPI RX MMAP --------------------------------------------------------------------------------------

class SPIRXMMAP(LiteXModule):
    def __init__(self, ctrl, data_width=32, nslots=1, origin=0x0000_0000):
        self.bus  = bus  = wishbone.Interface(data_width=data_width)
        self.sink = sink = stream.Endpoint(spi_layout(
            data_width = data_width,
            be_width   = data_width//8,
            cs_width   = nslots
        ))

        # # #

        valid_slot = Signal()

        # Compute/Check Slot.
        slot = (bus.adr - origin//(data_width//8))
        self.comb += valid_slot.eq(slot < nslots)

        # Get Slot Enable.
        slot_enable = ctrl.get_ctrl("enable", slot=slot)

        # FSM.
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(bus.stb & bus.cyc & ~bus.we,
                # Return error on invalid access.
                If(~valid_slot,
                    NextState("ERROR")
                # Return error when slot is disabled.
                ).Elif(~slot_enable,
                    NextState("ERROR")
                # Return error when upstream is not valid.
                ).Elif(~sink.valid,
                    NextState("ERROR")
                # Else Send.
                ).Else(
                    NextState("READ")
                )
            )
        )
        fsm.act("READ",
            If(sink.valid & (sink.cs == (1<<slot)),
                NextState("ACK")
            ).Else(
                NextState("ERROR")
            )
        )
        fsm.act("ACK",
            sink.ready.eq(1),
            bus.ack.eq(1),
            bus.dat_r.eq(sink.data),
            NextState("IDLE")
        )
        fsm.act("ERROR",
            bus.ack.eq(1),
            bus.err.eq(1),
            NextState("IDLE")
        )

# SPI Engine ---------------------------------------------------------------------------------------

class SPIEngine(LiteXModule):
    def __init__(self, pads, ctrl, data_width, sys_clk_freq, default_enable=0b1):
        self.sink = sink = stream.Endpoint(spi_layout(
            data_width = data_width,
            be_width   = data_width//8,
            cs_width   = len(pads.cs_n)
        ))
        self.source = source = stream.Endpoint(spi_layout(
            data_width = data_width,
            be_width   = data_width//8,
            cs_width   = len(pads.cs_n)
        ))

        self.control  = CSRStorage(fields=[
            CSRField("enable", size=1, offset=0, values=[
                    ("``0b0``", "SPI Engine Disabled."),
                    ("``0b1``", "SPI Engine Enabled."),
            ], reset=default_enable),
        ])

        # # #

        # SPI Master.
        self.spi = spi = SPIMaster(
            pads         = pads,
            data_width   = data_width,
            sys_clk_freq = sys_clk_freq,
        )

        # SPI Generic Controls.
        self.comb += [
            spi.clk_divider.eq(ctrl.get_ctrl("divider",  cs=sink.cs)),
            spi.loopback.eq(   ctrl.get_ctrl("loopback", cs=sink.cs)),
            spi.mode.eq(       ctrl.get_ctrl("mode",     cs=sink.cs)),
        ]

        # SPI Length.
        spi_length     = Signal(8)
        spi_length_max = Signal(8)
        self.comb += Case(sink.be, {
            0b0001 : spi_length.eq( 8), #  8-bit access.
            0b0011 : spi_length.eq(16), # 16-bit access.
            0b1111 : spi_length.eq(32), # 32-bit access.
        })
        self.comb += Case(ctrl.get_ctrl("length",  cs=sink.cs), {
            SPI_SLOT_LENGTH_32B : spi_length_max.eq(32), # 32-bit access max.
            SPI_SLOT_LENGTH_16B : spi_length_max.eq(16), # 16-bit access max.
            SPI_SLOT_LENGTH_8B  : spi_length_max.eq( 8), #  8-bit access max.
        })
        self.comb += spi.length.eq(spi_length)
        self.comb += [
            spi.length.eq(spi_length_max),
            If(spi_length <= spi_length_max,
                spi.length.eq(spi_length)
            )
        ]

        # SPI CS. (Use Manual CS to allow back-to-back Xfers).
        self.comb += If(self.control.fields.enable & sink.valid,
            spi.cs.eq(sink.cs)
        )

        # SPI Bitorder.
        spi_bitorder = Signal()
        self.comb += spi_bitorder.eq(ctrl.get_ctrl("bitorder", cs=sink.cs))

        # Control-Path.
        self.fsm = fsm = FSM(reset_state="START")
        fsm.act("START",
            If(self.control.fields.enable & sink.valid,
                spi.start.eq(1),
                NextState("XFER")
            )
        )
        fsm.act("XFER",
            If(spi.done,
                NextState("END")
            )
        )
        fsm.act("END",
            source.valid.eq(1),
            source.cs.eq(sink.cs),
            source.be.eq(sink.be),
            If(source.ready,
                sink.ready.eq(1),
                NextState("START")
            )
        )

        # Data-Path.
        self.comb += [
            # MSB First.
            If(spi_bitorder == SPI_SLOT_BITORDER_MSB_FIRST,
                # TX copy/bitshift.
                Case(spi_length, {
                     8 : spi.mosi[24:32].eq(sink.data[0: 8]),
                    16 : spi.mosi[16:32].eq(sink.data[0:16]),
                    32 : spi.mosi[ 0:32].eq(sink.data[0:32]),
                }),
                # RX copy.
                source.data.eq(spi.miso)
            ),
            # LSB First.
            If(spi_bitorder == SPI_SLOT_BITORDER_LSB_FIRST,
                # TX copy.
                spi.mosi.eq(sink.data[::-1]),
                # RX copy/bitshift.
                Case(spi_length, {
                     8 : source.data[0: 8].eq(spi.miso[::-1][24:32]),
                    16 : source.data[0:16].eq(spi.miso[::-1][16:32]),
                    32 : source.data[0:32].eq(spi.miso[::-1][ 0:32]),
                })
            )
        ]

# SPIMMAP ------------------------------------------------------------------------------------------

class SPIMMAP(LiteXModule):
    def __init__(self, pads, data_width, sys_clk_freq,
        tx_origin = 0x0000_0000,
        rx_origin = 0x0000_0000,
        tx_fifo_depth = 32,
        rx_fifo_depth = 32,
    ):
        nslots = len(pads.cs_n)
        assert nslots <= _nslots_max

        # Ctrl (Control/Status/IRQ) ----------------------------------------------------------------

        self.ctrl = ctrl = SPICtrl(nslots=nslots)
        self.ev              = ctrl.ev

        # TX ---------------------------------------------------------------------------------------

        # TX MMAP.
        # --------
        self.tx_mmap = tx_mmap = SPITXMMAP(
            ctrl       = ctrl,
            data_width = data_width,
            nslots     = nslots,
            origin     = tx_origin,
        )

        # TX FIFO.
        # --------
        self.tx_fifo = tx_fifo = SPIFIFO(
            data_width = data_width,
            nslots     = nslots,
            depth      = tx_fifo_depth,
        )
        self.comb += [
            # Control.
            tx_fifo.reset.eq(~ctrl.tx_control.fields.enable),
            # Status.
            ctrl.tx_status.fields.empty.eq(~tx_fifo.source.valid),
            ctrl.tx_status.fields.full.eq( ~tx_fifo.sink.ready),
            ctrl.tx_status.fields.level.eq(tx_fifo.level),
        ]

        # RX ---------------------------------------------------------------------------------------

        # RX FIFO.
        # --------
        self.rx_fifo = rx_fifo = SPIFIFO(
            data_width = data_width,
            nslots     = nslots,
            depth      = rx_fifo_depth,
        )
        self.comb += [
            # Control.
            rx_fifo.reset.eq(~ctrl.rx_control.fields.enable),
            # Status.
            ctrl.rx_status.fields.empty.eq(~rx_fifo.source.valid),
            ctrl.rx_status.fields.full.eq( ~rx_fifo.sink.ready),
            ctrl.rx_status.fields.level.eq(rx_fifo.level),
        ]

        # RX MMAP.
        # --------
        self.rx_mmap = rx_mmap = SPIRXMMAP(
            ctrl       = ctrl,
            data_width = data_width,
            nslots     = nslots,
            origin     = rx_origin,
        )

        # TX / RX Engine ---------------------------------------------------------------------------

        self.tx_rx_engine = tx_rx_engine = SPIEngine(
            pads         = pads,
            ctrl         = ctrl,
            data_width   = data_width,
            sys_clk_freq = sys_clk_freq,
        )
        self.comb += ctrl.tx_status.fields.ongoing.eq(~tx_rx_engine.spi.done)
        self.comb += ctrl.rx_status.fields.ongoing.eq(~tx_rx_engine.spi.done)

        # Pipelines --------------------------------------------------------------------------------

        self.submodules += stream.Pipeline(
            tx_mmap,
            tx_fifo,
            tx_rx_engine
        )
        self.submodules += stream.Pipeline(
            tx_rx_engine,
            rx_fifo,
            rx_mmap
        )
