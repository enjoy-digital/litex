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
from litex.soc.interconnect     import axi
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
- Wishbone, AXI-Lite or AXI4-Full bus interface.
- Optional CSR interface for configuration.
"""

HYPERRAM_LATENCIES     = list(range(3, 8))
HYPERRAM_LATENCY_MODES = ["fixed", "variable"]
HYPERRAM_CLK_RATIOS    = ["4:1", "2:1"]
HYPERRAM_BUS_STANDARDS = ["wishbone", "axi-lite", "axi"]


def check_hyperram_latency(latency):
    if latency not in HYPERRAM_LATENCIES:
        raise ValueError("Unsupported HyperRAM latency: {}.".format(latency))


# HyperRAM Layout ----------------------------------------------------------------------------------

def _check_hyperram_layout_width(data_width):
    if data_width not in [8, 16]:
        raise ValueError("HyperRAM only supports 8-bit or 16-bit data buses.")


def _get_signal_width(signal):
    try:
        return len(signal)
    except TypeError:
        return 1


# IOs.
# ----
def hyperram_ios_layout(data_width=8):
    """IO layout for HyperRAM PHY."""
    _check_hyperram_layout_width(data_width)
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

hyperam_ios_layout = hyperram_ios_layout

# PHY.
# ----
def hyperram_phy_tx_layout(data_width=8):
    """Transmit layout for HyperRAM PHY."""
    _check_hyperram_layout_width(data_width)
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
    _check_hyperram_layout_width(data_width)
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

# HyperRAM Native Port -----------------------------------------------------------------------------

class HyperRAMNativePort:
    """Internal word-addressed request/response port shared by the bus frontends."""
    def __init__(self):
        self.req_valid = Signal()
        self.req_ready = Signal()
        self.req_write = Signal()
        self.req_addr  = Signal(32)
        self.req_wdata = Signal(32)
        self.req_sel   = Signal(4)
        self.req_burst = Signal()

        self.rsp_valid = Signal()
        self.rsp_ready = Signal()
        self.rsp_rdata = Signal(32)

# HyperRAM Wishbone Frontend -----------------------------------------------------------------------

class HyperRAMWishboneFrontend(LiteXModule):
    def __init__(self, bus, port):
        pending_read  = Signal()
        pending_write = Signal()
        read_accept   = Signal()
        write_accept  = Signal()

        # # #

        self.comb += [
            read_accept.eq( port.req_valid & port.req_ready & ~bus.we),
            write_accept.eq(port.req_valid & port.req_ready &  bus.we),

            port.req_valid.eq(bus.cyc & bus.stb & ~pending_read & ~pending_write),
            port.req_write.eq(bus.we),
            port.req_addr.eq(bus.adr),
            port.req_wdata.eq(bus.dat_w),
            port.req_sel.eq(bus.sel),
            port.req_burst.eq(bus.cti == wishbone.CTI_BURST_INCREMENTING),
            port.rsp_ready.eq(1),
        ]

        self.sync += [
            # Writes can receive their native response in the same cycle they are accepted.
            # Reads always use one pending slot so dat_r is only driven on the ack cycle.
            If(read_accept & ~port.rsp_valid,
                pending_read.eq(1)
            ).Elif(port.rsp_valid & pending_read,
                pending_read.eq(0)
            ),
            If(write_accept & ~port.rsp_valid,
                pending_write.eq(1)
            ).Elif(port.rsp_valid & pending_write,
                pending_write.eq(0)
            ),
        ]

        self.comb += [
            If(pending_read | read_accept,
                bus.ack.eq(port.rsp_valid),
                bus.dat_r.eq(port.rsp_rdata),
            ).Elif(pending_write | write_accept,
                bus.ack.eq(port.rsp_valid),
            ).Else(
                bus.ack.eq(0),
            )
        ]

# HyperRAM AXI-Lite Frontend -----------------------------------------------------------------------

class HyperRAMAXILiteFrontend(LiteXModule):
    def __init__(self, bus, port):
        last_ar_aw = Signal()
        w_addr     = Signal(32)

        # # #

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            # AXI-Lite has independent AW/W channels; latch AW first, then wait for W.
            If(bus.ar.valid & bus.aw.valid,
                If(last_ar_aw,
                    bus.aw.ready.eq(1),
                    NextValue(w_addr, bus.aw.addr[2:]),
                    NextValue(last_ar_aw, 0),
                    NextState("WRITE-DATA")
                ).Else(
                    port.req_valid.eq(1),
                    port.req_write.eq(0),
                    port.req_addr.eq(bus.ar.addr[2:]),
                    port.req_sel.eq(0xf),
                    If(port.req_ready,
                        bus.ar.ready.eq(1),
                        NextValue(last_ar_aw, 1),
                        NextState("READ-RESP")
                    )
                )
            ).Elif(bus.ar.valid,
                port.req_valid.eq(1),
                port.req_write.eq(0),
                port.req_addr.eq(bus.ar.addr[2:]),
                port.req_sel.eq(0xf),
                If(port.req_ready,
                    bus.ar.ready.eq(1),
                    NextValue(last_ar_aw, 1),
                    NextState("READ-RESP")
                )
            ).Elif(bus.aw.valid,
                bus.aw.ready.eq(1),
                NextValue(w_addr, bus.aw.addr[2:]),
                NextValue(last_ar_aw, 0),
                NextState("WRITE-DATA")
            )
        )
        fsm.act("WRITE-DATA",
            port.req_valid.eq(bus.w.valid),
            port.req_write.eq(1),
            port.req_addr.eq(w_addr),
            port.req_wdata.eq(bus.w.data),
            port.req_sel.eq(bus.w.strb),
            If(port.req_ready,
                bus.w.ready.eq(1),
                NextState("WRITE-DONE")
            )
        )
        fsm.act("WRITE-DONE",
            # Return B only after the native core accepted the write data.
            port.rsp_ready.eq(1),
            If(port.rsp_valid,
                NextState("WRITE-RESP")
            )
        )
        fsm.act("WRITE-RESP",
            bus.b.valid.eq(1),
            bus.b.resp.eq(axi.RESP_OKAY),
            If(bus.b.ready,
                NextState("IDLE")
            )
        )
        fsm.act("READ-RESP",
            port.rsp_ready.eq(bus.r.ready),
            bus.r.valid.eq(port.rsp_valid),
            bus.r.resp.eq(axi.RESP_OKAY),
            bus.r.data.eq(port.rsp_rdata),
            If(port.rsp_valid & bus.r.ready,
                NextState("IDLE")
            )
        )

# HyperRAM AXI Frontend ----------------------------------------------------------------------------

class HyperRAMAXIFrontend(LiteXModule):
    def __init__(self, bus, port):
        if bus.data_width != 32:
            raise ValueError("HyperRAM AXI front-end only supports 32-bit data-width.")

        addr       = Signal(32)
        length     = Signal(8)
        beat_count = Signal(8)
        req_count  = Signal(8)
        req_done   = Signal()
        burst      = Signal(2)
        txn_id     = Signal(len(bus.aw.id))
        resp       = Signal(2)
        last_ar_aw = Signal()

        last      = Signal()
        wrap_mask = Signal(32)
        next_addr = Signal(32)

        # # #

        def is_wrap_len_ok(channel):
            return (
                (channel.len ==  1) |
                (channel.len ==  3) |
                (channel.len ==  7) |
                (channel.len == 15)
            )

        def is_access_ok(channel):
            # The native HyperRAM datapath is 32-bit word-addressed; reject accesses that would
            # require width conversion or unaligned byte steering outside this frontend.
            return (
                (channel.size == log2_int(bus.data_width//8)) &
                (channel.burst != axi.BURST_RESERVED) &
                (channel.addr[:log2_int(bus.data_width//8)] == 0) &
                ((channel.burst != axi.BURST_WRAP) | is_wrap_len_ok(channel))
            )

        self.comb += [
            last.eq(beat_count == length),
            wrap_mask.eq(0),
            Case(length, {
                 1 : wrap_mask.eq(0x07),
                 3 : wrap_mask.eq(0x0f),
                 7 : wrap_mask.eq(0x1f),
                15 : wrap_mask.eq(0x3f),
            }),
            next_addr.eq(addr),
            If(burst == axi.BURST_INCR,
                next_addr.eq(addr + (bus.data_width//8))
            ).Elif(burst == axi.BURST_WRAP,
                # WRAP bursts are presented as individual native beats since HyperRAM only keeps
                # an incrementing linear burst open.
                next_addr.eq((addr & ~wrap_mask) | ((addr + (bus.data_width//8)) & wrap_mask))
            ),
        ]

        self.fsm = fsm = FSM(reset_state="IDLE")

        def capture_aw():
            return [
                bus.aw.ready.eq(1),
                NextValue(addr,       bus.aw.addr),
                NextValue(length,     bus.aw.len),
                NextValue(beat_count, 0),
                NextValue(burst,      bus.aw.burst),
                NextValue(txn_id,     bus.aw.id),
                NextValue(resp,       Mux(is_access_ok(bus.aw), axi.RESP_OKAY, axi.RESP_SLVERR)),
                NextValue(last_ar_aw, 0),
                NextState("WRITE")
            ]

        def capture_ar():
            return [
                bus.ar.ready.eq(1),
                NextValue(addr,       bus.ar.addr),
                NextValue(length,     bus.ar.len),
                NextValue(beat_count, 0),
                NextValue(req_count,  0),
                NextValue(req_done,   0),
                NextValue(burst,      bus.ar.burst),
                NextValue(txn_id,     bus.ar.id),
                NextValue(resp,       Mux(is_access_ok(bus.ar), axi.RESP_OKAY, axi.RESP_SLVERR)),
                NextValue(last_ar_aw, 1),
                NextState("READ")
            ]

        def advance_or_finish(response_state):
            return If(last | bus.w.last,
                If(bus.w.last != last,
                    NextValue(resp, axi.RESP_SLVERR)
                ),
                NextState(response_state)
            ).Else(
                NextValue(addr,       next_addr),
                NextValue(beat_count, beat_count + 1)
            )

        fsm.act("IDLE",
            If(bus.ar.valid & bus.aw.valid,
                If(last_ar_aw,
                    *capture_aw(),
                ).Else(
                    *capture_ar(),
                )
            ).Elif(bus.ar.valid,
                *capture_ar(),
            ).Elif(bus.aw.valid,
                *capture_aw(),
            )
        )

        fsm.act("WRITE",
            # Native writes produce one response per accepted beat. Keep rsp_ready asserted so
            # intermediate burst beats do not stall, and use the final response for the AXI B beat.
            port.rsp_ready.eq(1),
            If(resp != axi.RESP_OKAY,
                # Unsupported writes are drained from W and answered with SLVERR without touching
                # the native port.
                bus.w.ready.eq(1),
                If(bus.w.valid,
                    advance_or_finish("WRITE-RESP")
                )
            ).Else(
                port.req_valid.eq(bus.w.valid),
                port.req_write.eq(1),
                port.req_addr.eq(addr[2:]),
                port.req_wdata.eq(bus.w.data),
                port.req_sel.eq(bus.w.strb),
                port.req_burst.eq((burst == axi.BURST_INCR) & ~last),
                bus.w.ready.eq(port.req_ready),
                If(bus.w.valid & port.req_ready,
                    If(last | bus.w.last,
                        If(bus.w.last != last,
                            NextValue(resp, axi.RESP_SLVERR)
                        ),
                        If(port.rsp_valid,
                            NextState("WRITE-RESP")
                        ).Else(
                            NextState("WRITE-DONE")
                        )
                    ).Else(
                        NextValue(addr,       next_addr),
                        NextValue(beat_count, beat_count + 1)
                    )
                )
            )
        )
        fsm.act("WRITE-DONE",
            port.rsp_ready.eq(1),
            If(port.rsp_valid,
                NextState("WRITE-RESP")
            )
        )
        fsm.act("WRITE-RESP",
            bus.b.valid.eq(1),
            bus.b.resp.eq(resp),
            bus.b.id.eq(txn_id),
            If(bus.b.ready,
                NextState("IDLE")
            )
        )

        fsm.act("READ",
            If(resp != axi.RESP_OKAY,
                # Unsupported reads still return the requested number of beats with SLVERR.
                bus.r.valid.eq(1),
                bus.r.resp.eq(resp),
                bus.r.data.eq(0),
                bus.r.last.eq(last),
                bus.r.id.eq(txn_id),
                If(bus.r.ready,
                    If(last,
                        NextState("IDLE")
                    ).Else(
                        NextValue(beat_count, beat_count + 1)
                    )
                )
            ).Else(
                port.req_valid.eq(~req_done),
                port.req_write.eq(0),
                port.req_addr.eq(addr[2:]),
                port.req_sel.eq(0xf),
                port.req_burst.eq((burst == axi.BURST_INCR) & (req_count != length)),
                port.rsp_ready.eq(bus.r.ready),
                bus.r.valid.eq(port.rsp_valid),
                bus.r.resp.eq(axi.RESP_OKAY),
                bus.r.data.eq(port.rsp_rdata),
                bus.r.last.eq(last),
                bus.r.id.eq(txn_id),
                If(port.req_ready,
                    If(req_count == length,
                        NextValue(req_done, 1)
                    ).Else(
                        NextValue(addr,      next_addr),
                        NextValue(req_count, req_count + 1)
                    )
                ),
                If(port.rsp_valid & bus.r.ready,
                    If(last,
                        NextState("IDLE")
                    ).Else(
                        NextValue(beat_count, beat_count + 1)
                    )
                )
            )
        )

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
        self.ios        =        ios = Record(hyperram_ios_layout(data_width))             # IOs.

        # # #

        # Parameters.
        # -----------
        _check_hyperram_layout_width(data_width)

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
        if hasattr(pads, "dq"):
            if hasattr(pads.dq, "oe"):
                data_width = _get_signal_width(pads.dq.o)
            else:
                data_width = _get_signal_width(pads.dq)
        elif all(hasattr(pads, name) for name in ["dq_o", "dq_i", "dq_oe"]):
            data_width = _get_signal_width(pads.dq_o)
            if _get_signal_width(pads.dq_i) != data_width:
                raise ValueError("HyperRAM DQ input/output widths must match.")
        else:
            raise ValueError("HyperRAM pads must provide dq or dq_o/dq_i/dq_oe signals.")

        if hasattr(pads, "rwds"):
            if hasattr(pads.rwds, "oe"):
                rwds_width = _get_signal_width(pads.rwds.o)
            else:
                rwds_width = _get_signal_width(pads.rwds)
        elif all(hasattr(pads, name) for name in ["rwds_o", "rwds_i", "rwds_oe"]):
            rwds_width = _get_signal_width(pads.rwds_o)
            if _get_signal_width(pads.rwds_i) != rwds_width:
                raise ValueError("HyperRAM RWDS input/output widths must match.")
        else:
            raise ValueError("HyperRAM pads must provide rwds or rwds_o/rwds_i/rwds_oe signals.")

        if rwds_width != data_width//8:
            raise ValueError("HyperRAM RWDS width must be data_width/8.")
        return data_width

    def connect_to_pads(self, pads, dq_i_cd):
        """Connects PHY signals to external pads."""
        with_tristate = hasattr(pads, "dq") and hasattr(pads, "rwds") and \
            not hasattr(pads, "dq_oe") and not hasattr(pads, "rwds_oe")
        with_split_io = all(hasattr(pads, name) for name in [
            "dq_o",   "dq_i",   "dq_oe",
            "rwds_o", "rwds_i", "rwds_oe",
        ])
        if not (with_tristate or with_split_io):
            raise ValueError("HyperRAM pads must use tristate or split input/output signals.")

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
        elif hasattr(pads, "clk_p") and hasattr(pads, "clk_n"):
            self.specials += MultiReg(i=  self.ios.clk & ClockSignal("hyperram"),  o=pads.clk_p, n=3)
            self.specials += MultiReg(i=~(self.ios.clk & ClockSignal("hyperram")), o=pads.clk_n, n=3)
        elif hasattr(pads, "clk_p") or hasattr(pads, "clk_n"):
            raise ValueError("HyperRAM differential clock pads must provide clk_p and clk_n.")
        else:
            raise ValueError("HyperRAM pads must provide clk or clk_p/clk_n.")

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

        # RWDS Output/Input.
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
    latency, configurable clocking, and Wishbone/AXI frontends for data transfer. It manages read
    and write operations and interacts with the PHY layer for memory access.

    Parameters:
    - phy            : SDR PHY interface for data transmission and reception.
    - latency        : Default latency setting.
    - latency_mode   : Latency mode "fixed" or "variable".
    - clk_ratio      : Clock ratio "4:1" or "2:1".
    - with_bursting  : Enable or disable burst mode.
    - bus_standard   : Memory bus standard: "wishbone", "axi-lite" or "axi".
    - axi_id_width   : AXI ID width when bus_standard is "axi".
    - cs_high_cycles : Number of sys_clk cycles between commands.
    """
    def __init__(self, phy, latency=7, latency_mode="fixed", clk_ratio="4:1",
        with_bursting=True, bus_standard="wishbone", axi_id_width=1, cs_high_cycles=9):
        if bus_standard not in HYPERRAM_BUS_STANDARDS:
            raise ValueError("Unsupported HyperRAM bus standard: {}.".format(bus_standard))
        if axi_id_width <= 0:
            raise ValueError("HyperRAM AXI ID width must be positive.")
        if cs_high_cycles < 1:
            raise ValueError("HyperRAM CS high cycles must be positive.")
        wishbone_bus = bus_standard == "wishbone"

        self.port   = port   = HyperRAMNativePort()
        self.reg    = reg    = wishbone.Interface(data_width=16, address_width=4,  addressing="word")
        self.source = source = stream.Endpoint(hyperram_phy_tx_layout(phy.data_width)) # TX.
        self.sink   = sink   = stream.Endpoint(hyperram_phy_rx_layout(phy.data_width)) # RX.

        bus_cls = {
            "wishbone": wishbone.Interface,
            "axi-lite": axi.AXILiteInterface,
            "axi"     : axi.AXIInterface,
        }[bus_standard]
        bus_kwargs = {
            "data_width"    : 32,
            "address_width" : 32,
        }
        if bus_standard == "wishbone":
            bus_kwargs["addressing"] = "word"
            bus_kwargs["bursting"]   = with_bursting
        if bus_standard == "axi":
            bus_kwargs["id_width"] = axi_id_width
            bus_kwargs["bursting"] = with_bursting
        self.bus = bus = bus_cls(**bus_kwargs)

        self.frontend = {
            "wishbone": HyperRAMWishboneFrontend,
            "axi-lite": HyperRAMAXILiteFrontend,
            "axi"     : HyperRAMAXIFrontend,
        }[bus_standard](bus, port)

        # # #

        check_hyperram_latency(latency)
        if latency_mode not in HYPERRAM_LATENCY_MODES:
            raise ValueError("Unsupported HyperRAM latency mode: {}.".format(latency_mode))
        if clk_ratio not in HYPERRAM_CLK_RATIOS:
            raise ValueError("Unsupported HyperRAM clock ratio: {}.".format(clk_ratio))

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
            reg_rx_conv.source.ready.eq(1), # Always ready.
        ]
        if wishbone_bus:
            # Preserve the pre-AXI Wishbone datapath behavior: the RX converter was always drained.
            self.comb += dat_rx_conv.source.ready.eq(1)

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
                cmd[47].eq(~bus_we),                       # R/W#.
                cmd[46].eq(0),                             # Memory Space.
                cmd[45].eq(1),                             # Burst Type (Linear).
                cmd[    16:45].eq(bus_adr[3-ashift:]),     # Row & Upper Column Address.
                cmd[ashift: 3].eq(bus_adr),                # Lower Column Address.
            )
        ]

        # FSM.
        # ----
        self.fsm = fsm = FSM(reset_state="IDLE")

        # IDLE State.
        fsm.act("IDLE",
            If(reg.stb,
                NextState("CMD-ADDRESS")
            ).Elif(port.req_valid,
                port.req_ready.eq(1),
                bus_latch.eq(1),
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
                        # Bus Write.
                        If(bus_we,
                            # Write responses are generated when data can enter the write path.
                            # This preserves Wishbone ack timing and gives AXI a completion point.
                            port.rsp_valid.eq(1),
                            If(port.rsp_ready,
                                NextState("DAT-WRITE")
                            )
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
                bus_cti.eq(Mux(port.req_burst, wishbone.CTI_BURST_INCREMENTING, wishbone.CTI_BURST_END)),
                bus_we.eq(port.req_write),
                bus_sel.eq(port.req_sel),
                bus_adr.eq(port.req_addr),
                bus_dat_w.eq(port.req_wdata),
            )
        ]
        write_burst = bus_cti == wishbone.CTI_BURST_INCREMENTING
        if wishbone_bus:
            write_burst = write_burst | bus_we
        self.comb += burst_w.eq(
            write_burst &
            port.req_valid &
            (port.req_write == bus_we) &
            (port.req_addr == (bus_adr + 1)),
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
                # Continue while Incrementing Burst ongoing. The next beat is accepted only when
                # the converter is ready so the HyperRAM command can remain open.
                If(with_bursting & burst_w & port.req_valid,
                    port.req_ready.eq(1),
                    port.rsp_valid.eq(1),
                    If(port.rsp_ready,
                        bus_latch.eq(1),
                        NextState("DAT-WRITE")
                    )
                # ..else exit.
                ).Else(
                    NextState("END")
                )
            )
        )

        # Data Read State.
        read_burst = (bus_cti == wishbone.CTI_BURST_INCREMENTING)
        if wishbone_bus:
            # Wishbone masters such as VexRiscv-SMP can issue adjacent cache-line reads without
            # CTI burst tags. Allow these reads to keep the HyperRAM command open, but keep writes
            # explicit-only to avoid merging classic write cycles.
            read_burst = read_burst | ~bus_we
        self.comb += burst_r.eq(
            read_burst &
            port.req_valid &
            ~port.req_write &
            ~bus_we &
            (port.req_addr == (bus_adr + 1)),
        )
        fsm.act("DAT-READ",
            source.valid.eq(1),
            source.dat_r.eq(1),
            If(dat_rx_conv.source.valid,
                port.rsp_valid.eq(1),
                port.rsp_rdata.eq(dat_rx_conv.source.dq),
                *([] if wishbone_bus else [dat_rx_conv.source.ready.eq(port.rsp_ready)]),
                If(port.rsp_ready,
                    NextValue(burst_r_first, 0),
                    # If continuing burst, stay in DAT-READ to anticipate next read...
                    If(with_bursting & burst_r & port.req_valid,
                        NextValue(burst_r_first, 0),
                        port.req_ready.eq(1),
                        bus_latch.eq(1),
                        NextState("DAT-READ")
                    ).Elif(burst_r_first,
                        # The legacy Wishbone path always kept the RX converter ready. Drain one
                        # additional beat after a single read to preserve that external waveform.
                        NextValue(burst_r_first, 0),
                        NextState("DAT-READ-DRAIN")
                    # ..else exit.
                    ).Else(
                        NextState("END")
                    )
                )
            )
        )
        fsm.act("DAT-READ-DRAIN",
            source.valid.eq(1),
            source.dat_r.eq(1),
            *([] if wishbone_bus else [dat_rx_conv.source.ready.eq(1)]),
            If(dat_rx_conv.source.valid,
                # Wishbone masters normally present the next burst address after the ack cycle.
                # This drain beat gives that registered next request a chance to keep the
                # HyperRAM command open without a combinatorial rsp_valid -> req_valid path.
                If(with_bursting & burst_r & port.req_valid,
                    port.rsp_valid.eq(1),
                    port.rsp_rdata.eq(dat_rx_conv.source.dq),
                    If(port.rsp_ready,
                        port.req_ready.eq(1),
                        bus_latch.eq(1),
                        NextState("DAT-READ")
                    )
                ).Else(
                    NextState("END")
                )
            )
        )
        fsm.act("END",
            NextValue(cycles, cycles + 1),
            If(cycles == (cs_high_cycles - 1),
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
    - bus_standard   : Memory bus standard: "wishbone", "axi-lite" or "axi".
    - axi_id_width   : AXI ID width when bus_standard is "axi".
    - cs_high_cycles : Number of sys_clk cycles between commands.
    - with_csr       : Include CSR support.
    - dq_i_cd        : Clock domain for data input.
    """
    def __init__(self, pads, latency=7, latency_mode="fixed", sys_clk_freq=100e6,
        clk_ratio="4:1", with_bursting=True, bus_standard="wishbone", axi_id_width=1,
        cs_high_cycles=9, with_csr=True, dq_i_cd=None):
        # Parameters.
        # -----------
        check_hyperram_latency(latency)
        self.pads         = pads
        self.clk_ratio    = clk_ratio
        self.bus_standard = bus_standard
        if latency_mode not in HYPERRAM_LATENCY_MODES:
            raise ValueError("Unsupported HyperRAM latency mode: {}.".format(latency_mode))
        if clk_ratio not in HYPERRAM_CLK_RATIOS:
            raise ValueError("Unsupported HyperRAM clock ratio: {}.".format(clk_ratio))

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
            bus_standard  = bus_standard,
            axi_id_width  = axi_id_width,
            cs_high_cycles = cs_high_cycles,
        )
        self.bus = core.bus

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
            CSRField("latency", offset=8, size=8, reset=default_latency,
                description="HyperRAM Latency (X1)."),
        ])
        self.comb += [
            self.core.rst.eq(    self.config.fields.rst),
            self.core.latency.eq(self.config.fields.latency),
        ]
        self.status = CSRStatus(fields=[
            CSRField("latency_mode", offset=0, size=1, description="HyperRAM latency mode.", values=[
                ("``0b0``", "Fixed Latency."),
                ("``0b1``", "Variable Latency."),
            ], reset={"fixed": 0b0, "variable": 0b1}[latency_mode]),
            CSRField("clk_ratio", offset=1, size=4, description="HyperRAM clock ratio.", values=[
                ("``4``", "HyperRAM Clk = Sys Clk/4."),
                ("``2``", "HyperRAM Clk = Sys Clk/2."),
            ], reset={"4:1": 4, "2:1": 2}[self.clk_ratio]),
        ])

        # Reg Interface.
        # --------------
        self.reg_control = CSRStorage(fields=[
            CSRField("write", offset=0, size=1, pulse=True, description="Issue Register Write."),
            CSRField("read",  offset=1, size=1, pulse=True, description="Issue Register Read."),
            CSRField("addr",  offset=8, size=2, description="Register access address.", values=[
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
