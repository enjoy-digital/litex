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
        ("id",    id_width)
    ]

def w_description(data_width):
    return [
        ("data", data_width),
        ("strb", data_width//8)
    ]

def b_description(id_width):
    return [
        ("resp", 2),
        ("id", id_width)
    ]

def r_description(data_width, id_width):
    return [
        ("resp", 2),
        ("data", data_width),
        ("id", id_width)
    ]


class AXIInterface(Record):
    def __init__(self, data_width, address_width, id_width=1, clock_domain="sys"):
        self.data_width = data_width
        self.address_width = address_width
        self.id_width = id_width
        self.clock_domain = clock_domain

        self.aw = stream.Endpoint(ax_description(address_width, id_width))
        self.w = stream.Endpoint(w_description(data_width))
        self.b = stream.Endpoint(b_description(id_width))
        self.ar = stream.Endpoint(ax_description(address_width, id_width))
        self.r = stream.Endpoint(r_description(data_width, id_width))

# AXI to Wishbone ----------------------------------------------------------------------------------

class AXI2Wishbone(Module):
    def __init__(self, axi, wishbone, base_address):
        assert axi.data_width    == 32
        assert axi.address_width == 32

        _data       = Signal(axi.data_width)
        _read_addr  = Signal(32)
        _write_addr = Signal(32)

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
        axi_ar_addr = Signal(32)
        self.comb += axi_ar_addr.eq(axi.ar.addr - base_address)
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
