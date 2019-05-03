"""AXI4 support for LiteX"""

from migen import *

from litex.soc.interconnect import stream

# AXI Definition -----------------------------------------------------------------------------------

BURST_FIXED    = 0b00
BURST_INCR     = 0b01
BURST_WRAP     = 0b10
BURST_RESERVED = 0b11

RESP_OKAY   = 0b00
RESP_EXOKAY = 0b01
RESP_SLVERR = 0b10
RESP_DECERR = 0b11

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
        self.data_width = data_width
        self.address_width = address_width
        self.id_width = id_width
        self.clock_domain = clock_domain

        self.aw = stream.Endpoint(ax_description(address_width, id_width))
        self.w = stream.Endpoint(w_description(data_width, id_width))
        self.b = stream.Endpoint(b_description(id_width))
        self.ar = stream.Endpoint(ax_description(address_width, id_width))
        self.r = stream.Endpoint(r_description(data_width, id_width))

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
        self.comb += beat_wrap.eq(ax_burst.len*beat_size)

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

# AXI to Wishbone ----------------------------------------------------------------------------------

class AXI2Wishbone(Module):
    def __init__(self, axi, wishbone, base_address=0x00000000):
        wishbone_adr_shift = log2_int(axi.data_width//8)
        assert axi.data_width    == len(wishbone.dat_r)
        assert axi.address_width == len(wishbone.adr) + wishbone_adr_shift


        ax_buffer = stream.Buffer(ax_description(axi.address_width, axi.id_width))
        ax_burst = stream.Endpoint(ax_description(axi.address_width, axi.id_width))
        ax_beat = stream.Endpoint(ax_description(axi.address_width, axi.id_width))
        self.comb += ax_burst.connect(ax_buffer.sink)
        ax_burst2beat = AXIBurst2Beat(ax_buffer.source, ax_beat)
        self.submodules += ax_buffer, ax_burst2beat

        _data       = Signal(axi.data_width)
        _addr  = Signal(axi.address_width)

        self.comb += _addr.eq(ax_beat.addr - base_address)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(axi.ar.valid,
                axi.ar.connect(ax_burst),
                NextState("DO-READ")
            ).Elif(axi.aw.valid,
                axi.aw.connect(ax_burst),
                NextState("DO-WRITE")
            )
        )
        fsm.act("DO-READ",
            wishbone.stb.eq(1),
            wishbone.cyc.eq(1),
            wishbone.adr.eq(_addr[wishbone_adr_shift:]),
            If(wishbone.ack,
                NextValue(_data, wishbone.dat_r),
                NextState("SEND-READ-RESPONSE")
            )
        )
        fsm.act("SEND-READ-RESPONSE",
            axi.r.valid.eq(1),
            axi.r.resp.eq(RESP_OKAY),
            axi.r.id.eq(ax_beat.id),
            axi.r.data.eq(_data),
            If(axi.r.ready,
                ax_beat.ready.eq(1),
                If(ax_beat.last,
                    axi.r.last.eq(1),
                    NextState("IDLE"),
                ).Else(
                    NextState("DO-READ")
                )
            )
        )
        fsm.act("DO-WRITE",
            wishbone.stb.eq(axi.w.valid),
            wishbone.cyc.eq(axi.w.valid),
            wishbone.we.eq(1),
            wishbone.adr.eq(_addr[wishbone_adr_shift:]),
            wishbone.sel.eq(axi.w.strb),
            wishbone.dat_w.eq(axi.w.data),
            If(wishbone.ack,
                ax_beat.ready.eq(1),
                axi.w.ready.eq(1),
                If(ax_beat.last,
                    ax_beat.ready.eq(0),
                    NextState("SEND-WRITE-RESPONSE")
                )
            )
        )
        fsm.act("SEND-WRITE-RESPONSE",
            axi.b.valid.eq(1),
            axi.b.resp.eq(RESP_OKAY),
            axi.b.id.eq(ax_beat.id),
            If(axi.b.ready,
                ax_beat.ready.eq(1),
                NextState("IDLE")
            )
        )
