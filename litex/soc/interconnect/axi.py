# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

"""AXI4 Full/Lite support for LiteX"""

from migen import *

from litex.soc.interconnect import stream

# AXI Definition -----------------------------------------------------------------------------------

BURST_FIXED    = 0b00
BURST_INCR     = 0b01
BURST_WRAP     = 0b10
BURST_RESERVED = 0b11

RESP_OKAY      = 0b00
RESP_EXOKAY    = 0b01
RESP_SLVERR    = 0b10
RESP_DECERR    = 0b11

def ax_description(address_width, id_width):
    return [
        ("addr",  address_width),
        ("burst", 2), # Burst type
        ("len",   8), # Number of data (-1) transfers (up to 256)
        ("size",  4), # Number of bytes (-1) of each data transfer (up to 1024 bits)
        ("lock",  2), # *
        ("prot",  3), # *
        ("cache", 4), # *
        ("qos",   4), # *
        ("id",    id_width)
    ]
    # * present for interconnect with others cores but not used by LiteX.

def w_description(data_width, id_width):
    return [
        ("data", data_width),
        ("strb", data_width//8),
        ("id",   id_width)
    ]

def b_description(id_width):
    return [
        ("resp", 2),
        ("id",   id_width)
    ]

def r_description(data_width, id_width):
    return [
        ("resp", 2),
        ("data", data_width),
        ("id",   id_width)
    ]

class AXIInterface(Record):
    def __init__(self, data_width, address_width, id_width=1, clock_domain="sys"):
        self.data_width    = data_width
        self.address_width = address_width
        self.id_width      = id_width
        self.clock_domain  = clock_domain

        self.aw = stream.Endpoint(ax_description(address_width, id_width))
        self.w  = stream.Endpoint(w_description(data_width, id_width))
        self.b  = stream.Endpoint(b_description(id_width))
        self.ar = stream.Endpoint(ax_description(address_width, id_width))
        self.r  = stream.Endpoint(r_description(data_width, id_width))

# AXI Lite Definition -----------------------------------------------------------------------------------

def ax_lite_description(address_width):
    return [("addr",  address_width)]

def w_lite_description(data_width):
    return [
        ("data", data_width),
        ("strb", data_width//8)
    ]

def b_lite_description():
    return [("resp", 2)]

def r_lite_description(data_width):
    return [
        ("resp", 2),
        ("data", data_width)
    ]

class AXILiteInterface(Record):
    def __init__(self, data_width, address_width, clock_domain="sys"):
        self.data_width    = data_width
        self.address_width = address_width
        self.clock_domain  = clock_domain

        self.aw = stream.Endpoint(ax_lite_description(address_width))
        self.w  = stream.Endpoint(w_lite_description(data_width))
        self.b  = stream.Endpoint(b_lite_description())
        self.ar = stream.Endpoint(ax_lite_description(address_width))
        self.r  = stream.Endpoint(r_lite_description(data_width))

# AXI Bursts to Beats ------------------------------------------------------------------------------

class AXIBurst2Beat(Module):
    def __init__(self, ax_burst, ax_beat, capabilities={BURST_FIXED, BURST_INCR, BURST_WRAP}):
        assert BURST_FIXED in capabilities

        # # #

        beat_count  = Signal(8)
        beat_size   = Signal(8 + 4)
        beat_offset = Signal(8 + 4)
        beat_wrap   = Signal(8 + 4)

        # compute parameters
        self.comb += beat_size.eq(1 << ax_burst.size)
        self.comb += beat_wrap.eq(ax_burst.len << ax_burst.size)

        # combinatorial logic
        self.comb += [
            ax_beat.valid.eq(ax_burst.valid | ~ax_beat.first),
            ax_beat.first.eq(beat_count == 0),
            ax_beat.last.eq(beat_count == ax_burst.len),
            ax_beat.addr.eq(ax_burst.addr + beat_offset),
            ax_beat.id.eq(ax_burst.id),
            If(ax_beat.ready,
                If(ax_beat.last,
                    ax_burst.ready.eq(1)
                )
            )
        ]

        # synchronous logic
        self.sync += [
            If(ax_beat.valid & ax_beat.ready,
                If(ax_beat.last,
                    beat_count.eq(0),
                    beat_offset.eq(0)
                ).Else(
                    beat_count.eq(beat_count + 1),
                    If(((ax_burst.burst == BURST_INCR) & (BURST_INCR in capabilities)) |
                       ((ax_burst.burst == BURST_WRAP) & (BURST_WRAP in capabilities)),
                        beat_offset.eq(beat_offset + beat_size)
                    )
                ),
                If((ax_burst.burst == BURST_WRAP) & (BURST_WRAP in capabilities),
                    If(beat_offset == beat_wrap,
                        beat_offset.eq(0)
                    )
                )
            )
        ]


# AXI to AXI Lite ----------------------------------------------------------------------------------

class AXI2AXILite(Module):
    # Note: Since this AXI bridge will mostly be used to target buses that are not supporting
    # simultaneous writes/reads, to reduce ressource usage the AXIBurst2Beat module is shared
    # between writes/reads.
    def __init__(self, axi, axi_lite):
        assert axi.data_width    == axi_lite.data_width
        assert axi.address_width == axi_lite.address_width

        ax_buffer = stream.Buffer(ax_description(axi.address_width, axi.id_width))
        ax_burst  = stream.Endpoint(ax_description(axi.address_width, axi.id_width))
        ax_beat   = stream.Endpoint(ax_description(axi.address_width, axi.id_width))
        self.comb += ax_burst.connect(ax_buffer.sink)
        ax_burst2beat = AXIBurst2Beat(ax_buffer.source, ax_beat)
        self.submodules += ax_buffer, ax_burst2beat

        _data         = Signal(axi.data_width)
        _cmd_done     = Signal()
        _last_ar_aw_n = Signal()

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            NextValue(_cmd_done, 0),
            If(axi.ar.valid & axi.aw.valid,
                # If last access was a read, do a write
                If(_last_ar_aw_n,
                    axi.aw.connect(ax_burst),
                    NextValue(_last_ar_aw_n, 0),
                    NextState("WRITE")
                # If last access was a write, do a read
                ).Else(
                    axi.ar.connect(ax_burst),
                    NextValue(_last_ar_aw_n, 1),
                    NextState("READ"),
                )
            ).Elif(axi.ar.valid,
                axi.ar.connect(ax_burst),
                NextValue(_last_ar_aw_n, 1),
                NextState("READ"),
            ).Elif(axi.aw.valid,
                axi.aw.connect(ax_burst),
                NextValue(_last_ar_aw_n, 0),
                NextState("WRITE")
            )
        )
        fsm.act("READ",
            # cmd
            axi_lite.ar.valid.eq(ax_beat.valid & ~_cmd_done),
            axi_lite.ar.addr.eq(ax_beat.addr),
            ax_beat.ready.eq(axi_lite.ar.ready & ~_cmd_done),
            If(ax_beat.valid & ax_beat.last,
                If(axi_lite.ar.ready,
                    ax_beat.ready.eq(0),
                    NextValue(_cmd_done, 1)
                )
            ),
            # data
            axi.r.valid.eq(axi_lite.r.valid),
            axi.r.last.eq(_cmd_done),
            axi.r.resp.eq(RESP_OKAY),
            axi.r.id.eq(ax_beat.id),
            axi.r.data.eq(axi_lite.r.data),
            axi_lite.r.ready.eq(axi.r.ready),
            # exit
            If(axi.r.valid & axi.r.last & axi.r.ready,
                ax_beat.ready.eq(1),
                NextState("IDLE")
            )
        )
        # always accept write responses
        self.comb += axi_lite.b.ready.eq(1)
        fsm.act("WRITE",
            # cmd
            axi_lite.aw.valid.eq(ax_beat.valid & ~_cmd_done),
            axi_lite.aw.addr.eq(ax_beat.addr),
            ax_beat.ready.eq(axi_lite.aw.ready & ~_cmd_done),
            If(ax_beat.valid & ax_beat.last,
                If(axi_lite.aw.ready,
                    ax_beat.ready.eq(0),
                    NextValue(_cmd_done, 1)
                )
            ),
            # data
            axi_lite.w.valid.eq(axi.w.valid),
            axi_lite.w.data.eq(axi.w.data),
            axi_lite.w.strb.eq(axi.w.strb),
            axi.w.ready.eq(axi_lite.w.ready),
            # exit
            If(axi.w.valid & axi.w.last & axi.w.ready,
                NextState("WRITE-RESP")
            )
        )
        fsm.act("WRITE-RESP",
            axi.b.valid.eq(1),
            axi.b.resp.eq(RESP_OKAY),
            axi.b.id.eq(ax_beat.id),
            If(axi.b.ready,
                ax_beat.ready.eq(1),
                NextState("IDLE")
            )
        )

# AXI Lite to Wishbone -----------------------------------------------------------------------------

class AXILite2Wishbone(Module):
    def __init__(self, axi_lite, wishbone, base_address=0x00000000):
        wishbone_adr_shift = log2_int(axi_lite.data_width//8)
        assert axi_lite.data_width    == len(wishbone.dat_r)
        assert axi_lite.address_width == len(wishbone.adr) + wishbone_adr_shift

        _data         = Signal(axi_lite.data_width)
        _r_addr       = Signal(axi_lite.address_width)
        _w_addr       = Signal(axi_lite.address_width)
        _last_ar_aw_n = Signal()
        self.comb += _r_addr.eq(axi_lite.ar.addr - base_address)
        self.comb += _w_addr.eq(axi_lite.aw.addr - base_address)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(axi_lite.ar.valid & axi_lite.aw.valid,
                # If last access was a read, do a write
                If(_last_ar_aw_n,
                    NextValue(_last_ar_aw_n, 0),
                    NextState("DO-WRITE")
                # If last access was a write, do a read
                ).Else(
                    NextValue(_last_ar_aw_n, 1),
                    NextState("DO-READ")
                )
            ).Elif(axi_lite.ar.valid,
                NextValue(_last_ar_aw_n, 1),
                NextState("DO-READ")
            ).Elif(axi_lite.aw.valid,
                NextValue(_last_ar_aw_n, 0),
                NextState("DO-WRITE")
            )
        )
        fsm.act("DO-READ",
            wishbone.stb.eq(1),
            wishbone.cyc.eq(1),
            wishbone.adr.eq(_r_addr[wishbone_adr_shift:]),
            If(wishbone.ack,
                axi_lite.ar.ready.eq(1),
                NextValue(_data, wishbone.dat_r),
                NextState("SEND-READ-RESPONSE")
            )
        )
        fsm.act("SEND-READ-RESPONSE",
            axi_lite.r.valid.eq(1),
            axi_lite.r.resp.eq(RESP_OKAY),
            axi_lite.r.data.eq(_data),
            If(axi_lite.r.ready,
                NextState("IDLE")
            )
        )
        fsm.act("DO-WRITE",
            wishbone.stb.eq(axi_lite.w.valid),
            wishbone.cyc.eq(axi_lite.w.valid),
            wishbone.we.eq(1),
            wishbone.adr.eq(_w_addr[wishbone_adr_shift:]),
            wishbone.sel.eq(axi_lite.w.strb),
            wishbone.dat_w.eq(axi_lite.w.data),
            If(wishbone.ack,
                axi_lite.aw.ready.eq(1),
                axi_lite.w.ready.eq(1),
                NextState("SEND-WRITE-RESPONSE")
            )
        )
        fsm.act("SEND-WRITE-RESPONSE",
            axi_lite.b.valid.eq(1),
            axi_lite.b.resp.eq(RESP_OKAY),
            If(axi_lite.b.ready,
                NextState("IDLE")
            )
        )

# AXI to Wishbone ----------------------------------------------------------------------------------

class AXI2Wishbone(Module):
    def __init__(self, axi, wishbone, base_address=0x00000000):
        axi_lite          = AXILiteInterface(axi.data_width, axi.address_width)
        axi2axi_lite      = AXI2AXILite(axi, axi_lite)
        axi_lite2wishbone = AXILite2Wishbone(axi_lite, wishbone, base_address)
        self.submodules += axi2axi_lite, axi_lite2wishbone
