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
        ("lock",  2),
        ("prot",  3),
        ("cache", 4),
        ("qos",   4),
        ("id",    id_width)
    ]

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
    def __init__(self, ax_burst, ax_beat):

        # # #

        self.count = count = Signal(8)
        size = Signal(8 + 4)
        offset = Signal(8 + 4)

        # convert burst size to bytes
        cases = {}
        cases["default"] = size.eq(1024)
        for i in range(10):
            cases[i] = size.eq(2**i)
        self.comb += Case(ax_burst.size, cases)

        # fsm
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            ax_beat.valid.eq(ax_burst.valid),
            ax_beat.first.eq(1),
            ax_beat.last.eq(ax_burst.len == 0),
            ax_beat.addr.eq(ax_burst.addr),
            ax_beat.id.eq(ax_burst.id),
            If(ax_beat.valid & ax_beat.ready,
                If(ax_burst.len != 0,
                    NextState("BURST2BEAT")
                ).Else(
                    ax_burst.ready.eq(1)
                )
            ),
            NextValue(count, 1),
            NextValue(offset, size),
        )
        wrap_offset = Signal(8 + 4)
        self.sync += wrap_offset.eq((ax_burst.len - 1)*size)
        fsm.act("BURST2BEAT",
            ax_beat.valid.eq(1),
            ax_beat.first.eq(0),
            ax_beat.last.eq(count == ax_burst.len),
            If((ax_burst.burst == BURST_INCR) |
               (ax_burst.burst == BURST_WRAP),
                ax_beat.addr.eq(ax_burst.addr + offset)
            ).Else(
                ax_beat.addr.eq(ax_burst.addr)
            ),
            ax_beat.id.eq(ax_burst.id),
            If(ax_beat.valid & ax_beat.ready,
                If(ax_beat.last,
                    ax_burst.ready.eq(1),
                    NextState("IDLE")
                ),
                NextValue(count, count + 1),
                NextValue(offset, offset + size),
                If(ax_burst.burst == BURST_WRAP,
                    If(offset == wrap_offset,
                        NextValue(offset, 0)
                    )
                )
            )
        )

# AXI to Wishbone ----------------------------------------------------------------------------------

class AXI2Wishbone(Module):
    def __init__(self, axi, wishbone, base_address):
        assert axi.data_width    == len(wishbone.dat_r)
        assert axi.address_width == len(wishbone.adr) + 2

        _data       = Signal(axi.data_width)
        _read_addr  = Signal(axi.address_width)
        _write_addr = Signal(axi.address_width)

        self.comb += _read_addr.eq(axi.ar.addr - base_address)
        self.comb += _write_addr.eq(axi.aw.addr - base_address)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(axi.ar.valid,
                NextState("DO-READ")
            ).Elif(axi.aw.valid,
                NextState("DO-WRITE")
            )
        )
        fsm.act("DO-READ",
            wishbone.stb.eq(1),
            wishbone.cyc.eq(1),
            wishbone.adr.eq(_read_addr[2:]),
            If(wishbone.ack,
                NextValue(_data, wishbone.dat_r),
                NextState("SEND-READ-RESPONSE")
            )
        )
        fsm.act("SEND-READ-RESPONSE",
            axi.r.valid.eq(1),
            axi.r.last.eq(1),
            axi.r.resp.eq(RESP_OKAY),
            axi.r.id.eq(axi.ar.id),
            axi.r.data.eq(_data),
            If(axi.r.ready,
                axi.ar.ready.eq(1),
                NextState("IDLE")
            )
        )
        fsm.act("DO-WRITE",
            wishbone.stb.eq(1),
            wishbone.cyc.eq(1),
            wishbone.we.eq(1),
            wishbone.adr.eq(_write_addr[2:]),
            wishbone.sel.eq(axi.w.strb),
            wishbone.dat_w.eq(axi.w.data),
            If(wishbone.ack,
                NextState("SEND-WRITE-RESPONSE")
            )
        )
        fsm.act("SEND-WRITE-RESPONSE",
            axi.b.valid.eq(1),
            axi.b.resp.eq(RESP_OKAY),
            axi.b.id.eq(axi.aw.id),
            If(axi.b.ready,
                axi.aw.ready.eq(1),
                axi.w.ready.eq(1),
                NextState("IDLE")
            )
        )
