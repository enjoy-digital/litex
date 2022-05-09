#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""AXI4 Full/Lite support for LiteX"""

from migen import *
from migen.genlib import roundrobin
from migen.genlib.misc import split, displacer, chooser, WaitTimer

from litex.soc.interconnect import stream
from litex.build.generic_platform import *

from litex.soc.interconnect import csr_bus

# AXI Definition -----------------------------------------------------------------------------------

BURST_FIXED    = 0b00
BURST_INCR     = 0b01
BURST_WRAP     = 0b10
BURST_RESERVED = 0b11

RESP_OKAY      = 0b00
RESP_EXOKAY    = 0b01
RESP_SLVERR    = 0b10
RESP_DECERR    = 0b11

AXSIZE = {
     1 : 0b000,
     2 : 0b001,
     4 : 0b010,
     8 : 0b011,
    16 : 0b100,
    32 : 0b110,
    64 : 0b111,
}

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

def _connect_axi(master, slave, keep=None, omit=None):
    channel_modes = {
        "aw": "master",
        "w" : "master",
        "b" : "slave",
        "ar": "master",
        "r" : "slave",
    }
    r = []
    for channel, mode in channel_modes.items():
        if mode == "master":
            m, s = getattr(master, channel), getattr(slave, channel)
        else:
            s, m = getattr(master, channel), getattr(slave, channel)
        r.extend(m.connect(s, keep=keep, omit=omit))
    return r

def connect_to_pads(bus, pads, mode="master", axi_full=False):
    assert mode in ["slave", "master"]
    r = []
    def swap_mode(mode): return "master" if mode == "slave" else "slave"
    channel_modes = {
        "aw": mode,
        "w" : mode,
        "b" : swap_mode(mode),
        "ar": mode,
        "r" : swap_mode(mode),
    }
    for channel, mode in channel_modes.items():
        ch = getattr(bus, channel)
        sig_list = [("valid", 1)] + ch.description.payload_layout
        if channel in ["w", "r"] and axi_full:
            sig_list += [("last",  1)]
        for name, width in sig_list:
            sig  = getattr(ch, name)
            pad  = getattr(pads, channel + name)
            if mode == "master":
                r.append(pad.eq(sig))
            else:
                r.append(sig.eq(pad))
        for name, width in [("ready", 1)]:
            sig  = getattr(ch, name)
            pad  = getattr(pads, channel + name)
            if mode == "master":
                r.append(sig.eq(pad))
            else:
                r.append(pad.eq(sig))
    return r

def _axi_layout_flat(axi):
    # yields tuples (channel, name, direction)
    def get_dir(channel, direction):
        if channel in ["b", "r"]:
            return {DIR_M_TO_S: DIR_S_TO_M, DIR_S_TO_M: DIR_M_TO_S}[direction]
        return direction
    for ch in ["aw", "w", "b", "ar", "r"]:
        channel = getattr(axi, ch)
        for group in channel.layout:
            if len(group) == 3:
                name, _, direction = group
                yield ch, name, get_dir(ch, direction)
            else:
                _, subgroups = group
                for subgroup in subgroups:
                    name, _, direction = subgroup
                    yield ch, name, get_dir(ch, direction)

class AXIInterface:
    def __init__(self, data_width=32, address_width=32, id_width=1, clock_domain="sys"):
        self.data_width    = data_width
        self.address_width = address_width
        self.id_width      = id_width
        self.clock_domain  = clock_domain

        self.aw = stream.Endpoint(ax_description(address_width, id_width))
        self.w  = stream.Endpoint(w_description(data_width, id_width))
        self.b  = stream.Endpoint(b_description(id_width))
        self.ar = stream.Endpoint(ax_description(address_width, id_width))
        self.r  = stream.Endpoint(r_description(data_width, id_width))

    def connect_to_pads(self, pads, mode="master"):
        return connect_to_pads(self, pads, mode, axi_full=True)

    def get_ios(self, bus_name="wb"):
        subsignals = []
        for channel in ["aw", "w", "b", "ar", "r"]:
            for name in ["valid", "ready"] + (["last"] if channel in ["w", "r"] else []):
                subsignals.append(Subsignal(channel + name, Pins(1)))
            for name, width in getattr(self, channel).description.payload_layout:
                subsignals.append(Subsignal(channel + name, Pins(width)))
        ios = [(bus_name , 0) + tuple(subsignals)]
        return ios

    def connect(self, slave, **kwargs):
        return _connect_axi(self, slave, **kwargs)

    def layout_flat(self):
        return list(_axi_layout_flat(self))

# AXI Lite Definition ------------------------------------------------------------------------------

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

class AXILiteInterface:
    def __init__(self, data_width=32, address_width=32, clock_domain="sys", name=None, bursting=False):
        self.data_width    = data_width
        self.address_width = address_width
        self.clock_domain  = clock_domain
        if bursting is not False:
            raise NotImplementedError("AXI-Lite does not support bursting")

        self.aw = stream.Endpoint(ax_lite_description(address_width), name=name)
        self.w  = stream.Endpoint(w_lite_description(data_width), name=name)
        self.b  = stream.Endpoint(b_lite_description(), name=name)
        self.ar = stream.Endpoint(ax_lite_description(address_width), name=name)
        self.r  = stream.Endpoint(r_lite_description(data_width), name=name)

    def get_ios(self, bus_name="wb"):
        subsignals = []
        for channel in ["aw", "w", "b", "ar", "r"]:
            for name in ["valid", "ready"]:
                subsignals.append(Subsignal(channel + name, Pins(1)))
            for name, width in getattr(self, channel).description.payload_layout:
                subsignals.append(Subsignal(channel + name, Pins(width)))
        ios = [(bus_name , 0) + tuple(subsignals)]
        return ios

    def connect_to_pads(self, pads, mode="master"):
        return connect_to_pads(self, pads, mode)

    def connect(self, slave, **kwargs):
        return _connect_axi(self, slave, **kwargs)

    def layout_flat(self):
        return list(_axi_layout_flat(self))

    def write(self, addr, data, strb=None):
        if strb is None:
            strb = 2**len(self.w.strb) - 1
        # aw + w
        yield self.aw.valid.eq(1)
        yield self.aw.addr.eq(addr)
        yield self.w.data.eq(data)
        yield self.w.valid.eq(1)
        yield self.w.strb.eq(strb)
        yield
        while not (yield self.aw.ready):
            yield
        yield self.aw.valid.eq(0)
        yield self.aw.addr.eq(0)
        while not (yield self.w.ready):
            yield
        yield self.w.valid.eq(0)
        yield self.w.strb.eq(0)
        # b
        yield self.b.ready.eq(1)
        while not (yield self.b.valid):
            yield
        resp = (yield self.b.resp)
        yield self.b.ready.eq(0)
        return resp

    def read(self, addr):
        # ar
        yield self.ar.valid.eq(1)
        yield self.ar.addr.eq(addr)
        yield
        while not (yield self.ar.ready):
            yield
        yield self.ar.valid.eq(0)
        # r
        yield self.r.ready.eq(1)
        while not (yield self.r.valid):
            yield
        data = (yield self.r.data)
        resp = (yield self.r.resp)
        yield self.r.ready.eq(0)
        return (data, resp)

# AXI Stream Definition ----------------------------------------------------------------------------

class AXIStreamInterface(stream.Endpoint):
    def __init__(self, data_width=32, keep_width=0, user_width=0):
        self.data_width = data_width
        self.keep_width = keep_width
        self.user_width = user_width
        payload_layout = [("data", data_width)]
        if self.keep_width:
            payload_layout += [("keep", keep_width)]
        param_layout   = []
        if self.user_width:
            param_layout += [("user", user_width)]
        stream.Endpoint.__init__(self, stream.EndpointDescription(payload_layout, param_layout))

    def get_ios(self, bus_name="axi"):
        subsignals = [
            Subsignal("tvalid", Pins(1)),
            Subsignal("tlast",  Pins(1)),
            Subsignal("tready", Pins(1)),
            Subsignal("tdata",  Pins(self.data_width)),
        ]
        if self.keep_width:
            subsignals += [Subsignal("tkeep", Pins(self.keep_width))]
        if self.user_width:
            subsignals += [Subsignal("tuser", Pins(self.user_width))]
        ios = [(bus_name , 0) + tuple(subsignals)]
        return ios

    def connect_to_pads(self, pads, mode="master"):
        assert mode in ["slave", "master"]
        r = []
        if mode == "master":
            r.append(pads.tvalid.eq(self.valid))
            r.append(self.ready.eq(pads.tready))
            r.append(pads.tlast.eq(self.last))
            r.append(pads.tdata.eq(self.data))
            if self.keep_width:
                r.append(pads.tkeep.eq(self.keep))
            if self.user_width:
                r.append(pads.tuser.eq(self.user))
        if mode == "slave":
            r.append(self.valid.eq(pads.tvalid))
            r.append(pads.tready.eq(self.ready))
            r.append(self.last.eq(pads.tlast))
            r.append(self.data.eq(pads.tdata))
            if self.keep_width:
                r.append(self.keep.eq(pads.tkeep))
            if self.user_width:
                r.append(self.user.eq(pads.tuser))
        return r

# AXI Bursts to Beats ------------------------------------------------------------------------------

class AXIBurst2Beat(Module):
    def __init__(self, ax_burst, ax_beat, capabilities={BURST_FIXED, BURST_INCR, BURST_WRAP}):
        assert BURST_FIXED in capabilities

        # # #

        beat_count  = Signal(8)
        beat_size   = Signal(8 + 4)
        beat_offset = Signal((8 + 4 + 1, True))
        beat_wrap   = Signal(8 + 4)

        # Compute parameters
        self.comb += beat_size.eq(1 << ax_burst.size)
        self.comb += beat_wrap.eq(ax_burst.len << ax_burst.size)

        # Combinatorial logic
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

        # Synchronous logic
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
                    If((ax_beat.addr & beat_wrap) == beat_wrap,
                        beat_offset.eq(beat_offset - beat_wrap)
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
            # ar (read command)
            axi_lite.ar.valid.eq(ax_beat.valid & ~_cmd_done),
            axi_lite.ar.addr.eq(ax_beat.addr),
            ax_beat.ready.eq(axi_lite.ar.ready & ~_cmd_done),
            If(ax_beat.valid & ax_beat.last,
                If(axi_lite.ar.ready,
                    ax_beat.ready.eq(0),
                    NextValue(_cmd_done, 1)
                )
            ),
            # r (read data & response)
            axi.r.valid.eq(axi_lite.r.valid),
            axi.r.last.eq(_cmd_done),
            axi.r.resp.eq(RESP_OKAY),
            axi.r.id.eq(ax_beat.id),
            axi.r.data.eq(axi_lite.r.data),
            axi_lite.r.ready.eq(axi.r.ready),
            # Exit
            If(axi.r.valid & axi.r.last & axi.r.ready,
                ax_beat.ready.eq(1),
                NextState("IDLE")
            )
        )
        # Always accept write responses.
        self.comb += axi_lite.b.ready.eq(1)
        fsm.act("WRITE",
            # aw (write command)
            axi_lite.aw.valid.eq(ax_beat.valid & ~_cmd_done),
            axi_lite.aw.addr.eq(ax_beat.addr),
            ax_beat.ready.eq(axi_lite.aw.ready & ~_cmd_done),
            If(ax_beat.valid & ax_beat.last,
                If(axi_lite.aw.ready,
                    ax_beat.ready.eq(0),
                    NextValue(_cmd_done, 1)
                )
            ),
            # w (write data)
            axi_lite.w.valid.eq(axi.w.valid),
            axi_lite.w.data.eq(axi.w.data),
            axi_lite.w.strb.eq(axi.w.strb),
            axi.w.ready.eq(axi_lite.w.ready),
            # Exit
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

# AXI Lite to AXI ----------------------------------------------------------------------------------

class AXILite2AXI(Module):
    def __init__(self, axi_lite, axi, write_id=0, read_id=0, prot=0, burst_type="INCR"):
        assert isinstance(axi_lite, AXILiteInterface)
        assert isinstance(axi, AXIInterface)
        assert axi_lite.data_width == axi.data_width
        assert axi_lite.address_width == axi.address_width

        # n bytes, encoded as log2(n)
        burst_size = log2_int(axi.data_width // 8)
        # Burst type has no meaning as we use burst length of 1, but AXI slaves may require certain
        # type of bursts, so it is probably safest to use INCR in general.
        burst_type = {
            "FIXED": 0b00,
            "INCR":  0b01,
            "WRAP":  0b10,
        }[burst_type]

        self.comb += [
            # aw (write command)
            axi.aw.valid.eq(axi_lite.aw.valid),
            axi_lite.aw.ready.eq(axi.aw.ready),
            axi.aw.addr.eq(axi_lite.aw.addr),
            axi.aw.burst.eq(burst_type),
            axi.aw.len.eq(0),  # 1 transfer per burst
            axi.aw.size.eq(burst_size),
            axi.aw.lock.eq(0),  # Normal access
            axi.aw.prot.eq(prot),
            axi.aw.cache.eq(0b0011),  # Normal Non-cacheable Bufferable
            axi.aw.qos.eq(0),
            axi.aw.id.eq(write_id),

            # w (write data)
            axi.w.valid.eq(axi_lite.w.valid),
            axi_lite.w.ready.eq(axi.w.ready),
            axi.w.data.eq(axi_lite.w.data),
            axi.w.strb.eq(axi_lite.w.strb),
            axi.w.last.eq(1),

            # b (write response)
            axi_lite.b.valid.eq(axi.b.valid),
            axi_lite.b.resp.eq(axi.b.resp),
            axi.b.ready.eq(axi_lite.b.ready),

            # ar (read command)
            axi.ar.valid.eq(axi_lite.ar.valid),
            axi_lite.ar.ready.eq(axi.ar.ready),
            axi.ar.addr.eq(axi_lite.ar.addr),
            axi.ar.burst.eq(burst_type),
            axi.ar.len.eq(0),
            axi.ar.size.eq(burst_size),
            axi.ar.lock.eq(0),
            axi.ar.prot.eq(prot),
            axi.ar.cache.eq(0b0011),
            axi.ar.qos.eq(0),
            axi.ar.id.eq(read_id),

            # r (read response & data)
            axi_lite.r.valid.eq(axi.r.valid),
            axi_lite.r.resp.eq(axi.r.resp),
            axi_lite.r.data.eq(axi.r.data),
            axi.r.ready.eq(axi_lite.r.ready),
        ]

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
            wishbone.sel.eq(2**len(wishbone.sel) - 1),
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

# Wishbone to AXILite ------------------------------------------------------------------------------

class Wishbone2AXILite(Module):
    def __init__(self, wishbone, axi_lite, base_address=0x00000000):
        wishbone_adr_shift = log2_int(axi_lite.data_width//8)
        assert axi_lite.data_width    == len(wishbone.dat_r)
        assert axi_lite.address_width == len(wishbone.adr) + wishbone_adr_shift

        _cmd_done  = Signal()
        _data_done = Signal()
        _addr      = Signal(len(wishbone.adr))
        self.comb += _addr.eq(wishbone.adr - base_address//4)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            NextValue(_cmd_done,  0),
            NextValue(_data_done, 0),
            If(wishbone.stb & wishbone.cyc,
                If(wishbone.we,
                    NextState("WRITE")
                ).Else(
                    NextState("READ")
                )
            )
        )
        fsm.act("WRITE",
            # aw (write command)
            axi_lite.aw.valid.eq(~_cmd_done),
            axi_lite.aw.addr[wishbone_adr_shift:].eq(_addr),
            If(axi_lite.aw.valid & axi_lite.aw.ready,
                NextValue(_cmd_done, 1)
            ),
            # w (write data)
            axi_lite.w.valid.eq(~_data_done),
            axi_lite.w.data.eq(wishbone.dat_w),
            axi_lite.w.strb.eq(wishbone.sel),
            If(axi_lite.w.valid & axi_lite.w.ready,
                NextValue(_data_done, 1),
            ),
            # b (write response)
            axi_lite.b.ready.eq(_cmd_done & _data_done),
            If(axi_lite.b.valid & axi_lite.b.ready,
                If(axi_lite.b.resp == RESP_OKAY,
                    wishbone.ack.eq(1),
                    NextState("IDLE")
                ).Else(
                    NextState("ERROR")
                )
            )
        )
        fsm.act("READ",
            # ar (read command)
            axi_lite.ar.valid.eq(~_cmd_done),
            axi_lite.ar.addr[wishbone_adr_shift:].eq(_addr),
            If(axi_lite.ar.valid & axi_lite.ar.ready,
                NextValue(_cmd_done, 1)
            ),
            # r (read data & response)
            axi_lite.r.ready.eq(_cmd_done),
            If(axi_lite.r.valid & axi_lite.r.ready,
                If(axi_lite.r.resp == RESP_OKAY,
                    wishbone.dat_r.eq(axi_lite.r.data),
                    wishbone.ack.eq(1),
                    NextState("IDLE"),
                ).Else(
                    NextState("ERROR")
                )
            )
        )
        fsm.act("ERROR",
            wishbone.ack.eq(1),
            wishbone.err.eq(1),
            NextState("IDLE")
        )

# Wishbone to AXI ----------------------------------------------------------------------------------

class Wishbone2AXI(Module):
    def __init__(self, wishbone, axi, base_address=0x00000000):
        axi_lite          = AXILiteInterface(axi.data_width, axi.address_width)
        wishbone2axi_lite = Wishbone2AXILite(wishbone, axi_lite, base_address)
        axi_lite2axi      = AXILite2AXI(axi_lite, axi)
        self.submodules += wishbone2axi_lite, axi_lite2axi

# AXILite to CSR -----------------------------------------------------------------------------------

def axi_lite_to_simple(axi_lite, port_adr, port_dat_r, port_dat_w=None, port_we=None):
    """Connection of AXILite to simple bus with 1-cycle latency, such as CSR bus or Memory port"""
    bus_data_width = axi_lite.data_width
    adr_shift      = log2_int(bus_data_width//8)
    do_read        = Signal()
    do_write       = Signal()
    last_was_read  = Signal()

    comb = []
    if port_dat_w is not None:
        comb.append(port_dat_w.eq(axi_lite.w.data))
    if port_we is not None:
        if len(port_we) > 1:
            for i in range(bus_data_width//8):
                comb.append(port_we[i].eq(axi_lite.w.valid & axi_lite.w.ready & axi_lite.w.strb[i]))
        else:
            comb.append(port_we.eq(axi_lite.w.valid & axi_lite.w.ready & (axi_lite.w.strb != 0)))

    fsm = FSM()
    fsm.act("START-TRANSACTION",
        # If the last access was a read, do a write, and vice versa.
        If(axi_lite.aw.valid & axi_lite.ar.valid,
            do_write.eq(last_was_read),
            do_read.eq(~last_was_read),
        ).Else(
            do_write.eq(axi_lite.aw.valid),
            do_read.eq(axi_lite.ar.valid),
        ),
        # Start reading/writing immediately not to waste a cycle.
        If(do_write,
            port_adr.eq(axi_lite.aw.addr[adr_shift:]),
            If(axi_lite.w.valid,
                axi_lite.aw.ready.eq(1),
                axi_lite.w.ready.eq(1),
                NextState("SEND-WRITE-RESPONSE")
            )
        ).Elif(do_read,
            port_adr.eq(axi_lite.ar.addr[adr_shift:]),
            axi_lite.ar.ready.eq(1),
            NextState("SEND-READ-RESPONSE"),
        )
    )
    fsm.act("SEND-READ-RESPONSE",
        NextValue(last_was_read, 1),
        # As long as we have correct address port.dat_r will be valid.
        port_adr.eq(axi_lite.ar.addr[adr_shift:]),
        axi_lite.r.data.eq(port_dat_r),
        axi_lite.r.resp.eq(RESP_OKAY),
        axi_lite.r.valid.eq(1),
        If(axi_lite.r.ready,
            NextState("START-TRANSACTION")
        )
    )
    fsm.act("SEND-WRITE-RESPONSE",
        NextValue(last_was_read, 0),
        axi_lite.b.valid.eq(1),
        axi_lite.b.resp.eq(RESP_OKAY),
        If(axi_lite.b.ready,
            NextState("START-TRANSACTION")
        )
    )
    return fsm, comb

class AXILite2CSR(Module):
    def __init__(self, axi_lite=None, bus_csr=None, register=False):
        # TODO: unused register argument
        if axi_lite is None:
            axi_lite = AXILiteInterface()
        if bus_csr is None:
            bus_csr = csr_bus.Interface()

        self.axi_lite = axi_lite
        self.csr      = bus_csr

        fsm, comb = axi_lite_to_simple(
            axi_lite   = self.axi_lite,
            port_adr   = self.csr.adr,
            port_dat_r = self.csr.dat_r,
            port_dat_w = self.csr.dat_w,
            port_we    = self.csr.we)
        self.submodules.fsm = fsm
        self.comb += comb

# AXILite SRAM -------------------------------------------------------------------------------------

class AXILiteSRAM(Module):
    def __init__(self, mem_or_size, read_only=None, init=None, bus=None, name=None):
        if bus is None:
            bus = AXILiteInterface()
        self.bus = bus

        bus_data_width = len(self.bus.r.data)
        if isinstance(mem_or_size, Memory):
            assert(mem_or_size.width <= bus_data_width)
            self.mem = mem_or_size
        else:
            self.mem = Memory(bus_data_width, mem_or_size//(bus_data_width//8), init=init, name=name)

        if read_only is None:
            if hasattr(self.mem, "bus_read_only"):
                read_only = self.mem.bus_read_only
            else:
                read_only = False

        # # #

        # Create memory port
        port = self.mem.get_port(write_capable=not read_only, we_granularity=8,
            mode=READ_FIRST if read_only else WRITE_FIRST)
        self.specials += self.mem, port

        # Generate write enable signal
        if not read_only:
            self.comb += port.dat_w.eq(self.bus.w.data),
            self.comb += [port.we[i].eq(self.bus.w.valid & self.bus.w.ready & self.bus.w.strb[i])
                for i in range(bus_data_width//8)]

        # Transaction logic
        fsm, comb = axi_lite_to_simple(
            axi_lite   = self.bus,
            port_adr   = port.adr,
            port_dat_r = port.dat_r,
            port_dat_w = port.dat_w if not read_only else None,
            port_we    = port.we if not read_only else None)
        self.submodules.fsm = fsm
        self.comb += comb

# AXI Data Width Converter -------------------------------------------------------------------------

class AXIUpConverter(Module):
    def __init__(self, axi_from, axi_to):
        dw_from  = len(axi_from.r.data)
        dw_to    = len(axi_to.r.data)
        ratio    = int(dw_to//dw_from)
        assert dw_from*ratio == dw_to

        # # #

        # Note: Assuming size of "axi_from" burst >= "axi_to" data_width.

        # Write path -------------------------------------------------------------------------------

        # AW Channel.
        self.comb += [
            axi_from.aw.connect(axi_to.aw, omit={"len", "size"}),
            axi_to.aw.len.eq( axi_from.aw.len >> log2_int(ratio)),
            axi_to.aw.size.eq(axi_from.aw.size + log2_int(ratio)),
        ]

        # W Channel.
        w_converter = stream.StrideConverter(
            description_from = [("data", dw_from), ("strb", dw_from//8)],
            description_to   = [("data",   dw_to), ("strb",   dw_to//8)],
        )
        self.submodules += w_converter
        self.comb += axi_from.w.connect(w_converter.sink, omit={"id"})
        self.comb += w_converter.source.connect(axi_to.w)
        self.comb += axi_to.w.id.eq(axi_from.w.id)

        # B Channel.
        self.comb += axi_to.b.connect(axi_from.b)

        # Read path --------------------------------------------------------------------------------

        # AR Channel.
        self.comb += [
            axi_from.ar.connect(axi_to.ar, omit={"len", "size"}),
            axi_to.ar.len.eq( axi_from.ar.len >> log2_int(ratio)),
            axi_to.ar.size.eq(axi_from.ar.size + log2_int(ratio)),
        ]

        # R Channel.
        r_converter = stream.StrideConverter(
            description_from = [("data",   dw_to)],
            description_to   = [("data", dw_from)],
        )
        self.submodules += r_converter
        self.comb += axi_to.r.connect(r_converter.sink, omit={"id", "resp"})
        self.comb += r_converter.source.connect(axi_from.r)
        self.comb += axi_from.r.resp.eq(axi_to.r.resp)
        self.comb += axi_from.r.id.eq(axi_to.r.id)

# AXILite Data Width Converter ---------------------------------------------------------------------

class _AXILiteDownConverterWrite(Module):
    def __init__(self, master, slave):
        assert isinstance(master, AXILiteInterface) and isinstance(slave, AXILiteInterface)
        dw_from      = len(master.w.data)
        dw_to        = len(slave.w.data)
        ratio        = dw_from//dw_to

        skip         = Signal()
        counter      = Signal(max=ratio)
        aw_ready     = Signal()
        w_ready      = Signal()
        resp         = Signal.like(master.b.resp)

        # # #

        # Data path
        self.comb += [
            slave.aw.addr.eq(master.aw.addr + counter*(dw_to//8)),
            Case(counter, {i: slave.w.data.eq(master.w.data[i*dw_to:]) for i in range(ratio)}),
            Case(counter, {i: slave.w.strb.eq(master.w.strb[i*dw_to//8:]) for i in range(ratio)}),
            master.b.resp.eq(resp),
        ]

        # Control Path
        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.submodules.fsm = fsm
        # Reset the converter state if master breaks a request, we can do that as
        # aw.valid and w.valid are kept high in CONVERT and RESPOND-SLAVE, and
        # acknowledged only when moving to RESPOND-MASTER, and then b.valid is 1.
        self.comb += fsm.reset.eq(~((master.aw.valid | master.w.valid) | master.b.valid))

        fsm.act("IDLE",
            NextValue(counter, 0),
            NextValue(resp, RESP_OKAY),
            If(master.aw.valid & master.w.valid,
                NextState("CONVERT")
            )
        )
        fsm.act("CONVERT",
            skip.eq(slave.w.strb == 0),
            slave.aw.valid.eq(~skip & ~aw_ready),
            slave.w.valid.eq(~skip & ~w_ready),
            If(slave.aw.ready,
                NextValue(aw_ready, 1)
            ),
            If(slave.w.ready,
                NextValue(w_ready, 1)
            ),
            # When skipping, we just increment the counter.
            If(skip,
                NextValue(counter, counter + 1),
                # Corner-case: when the last word is being skipped, we must send the response.
                If(counter == (ratio - 1),
                    master.aw.ready.eq(1),
                    master.w.ready.eq(1),
                    NextState("RESPOND-MASTER")
                )
            # Write current word and wait for write response.
            ).Elif((slave.aw.ready | aw_ready) & (slave.w.ready | w_ready),
                NextState("RESPOND-SLAVE")
            )
        )
        fsm.act("RESPOND-SLAVE",
            NextValue(aw_ready, 0),
            NextValue(w_ready, 0),
            If(slave.b.valid,
                slave.b.ready.eq(1),
                # Errors are sticky, so the first one is always sent.
                If((resp == RESP_OKAY) & (slave.b.resp != RESP_OKAY),
                    NextValue(resp, slave.b.resp)
                ),
                If(counter == (ratio - 1),
                    master.aw.ready.eq(1),
                    master.w.ready.eq(1),
                    NextState("RESPOND-MASTER")
                ).Else(
                    NextValue(counter, counter + 1),
                    NextState("CONVERT")
                )
            )
        )
        fsm.act("RESPOND-MASTER",
            NextValue(aw_ready, 0),
            NextValue(w_ready, 0),
            master.b.valid.eq(1),
            If(master.b.ready,
                NextState("IDLE")
            )
        )

class _AXILiteDownConverterRead(Module):
    def __init__(self, master, slave):
        assert isinstance(master, AXILiteInterface) and isinstance(slave, AXILiteInterface)
        dw_from      = len(master.r.data)
        dw_to        = len(slave.r.data)
        ratio        = dw_from//dw_to

        skip         = Signal()
        counter      = Signal(max=ratio)
        resp         = Signal.like(master.r.resp)

        # # #

        # Data path
        # Shift the data word
        r_data = Signal(dw_from, reset_less=True)
        self.sync += If(slave.r.ready, r_data.eq(master.r.data))
        self.comb += master.r.data.eq(Cat(r_data[dw_to:], slave.r.data))
        # Connect address, resp
        self.comb += [
            slave.ar.addr.eq(master.ar.addr + counter*(dw_to//8)),
            master.r.resp.eq(resp),
        ]

        # Control Path
        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.submodules.fsm = fsm
        # Reset the converter state if master breaks a request, we can do that as
        # ar.valid is high in CONVERT and RESPOND-SLAVE, and r.valid in RESPOND-MASTER.
        self.comb += fsm.reset.eq(~(master.ar.valid | master.r.valid))

        fsm.act("IDLE",
            NextValue(counter, 0),
            NextValue(resp, RESP_OKAY),
            If(master.ar.valid,
                NextState("CONVERT")
            )
        )
        fsm.act("CONVERT",
            slave.ar.valid.eq(1),
            If(slave.ar.ready,
                NextState("RESPOND-SLAVE")
            )
        )
        fsm.act("RESPOND-SLAVE",
            If(slave.r.valid,
                # Errors are sticky, so the first one is always sent.
                If((resp == RESP_OKAY) & (slave.r.resp != RESP_OKAY),
                    NextValue(resp, slave.r.resp)
                ),
                # On last word acknowledge ar and hold slave.r.valid until we get master.r.ready.
                If(counter == (ratio - 1),
                    master.ar.ready.eq(1),
                    NextState("RESPOND-MASTER")
                # Acknowledge the response and continue conversion.
                ).Else(
                    slave.r.ready.eq(1),
                    NextValue(counter, counter + 1),
                    NextState("CONVERT")
                )
            )
        )
        fsm.act("RESPOND-MASTER",
            master.r.valid.eq(1),
            If(master.r.ready,
                slave.r.ready.eq(1),
                NextState("IDLE")
            )
        )

class AXILiteDownConverter(Module):
    def __init__(self, master, slave):
        self.submodules.write = _AXILiteDownConverterWrite(master, slave)
        self.submodules.read  = _AXILiteDownConverterRead(master, slave)

class AXILiteUpConverter(Module):
    # TODO: we could try joining multiple master accesses into single slave access would require
    # checking if address changes and a way to flush on single access
    def __init__(self, master, slave):
        assert isinstance(master, AXILiteInterface) and isinstance(slave, AXILiteInterface)
        dw_from      = len(master.r.data)
        dw_to        = len(slave.r.data)
        ratio        = dw_to//dw_from
        master_align = log2_int(master.data_width//8)
        slave_align  = log2_int(slave.data_width//8)

        wr_word   = Signal(log2_int(ratio))
        rd_word   = Signal(log2_int(ratio))
        wr_word_r = Signal(log2_int(ratio))
        rd_word_r = Signal(log2_int(ratio))

        # # #

        self.comb += master.connect(slave, omit={"addr", "strb", "data"})

        # Address
        self.comb += [
            slave.aw.addr[slave_align:].eq(master.aw.addr[slave_align:]),
            slave.ar.addr[slave_align:].eq(master.ar.addr[slave_align:]),
        ]

        # Data path
        wr_cases, rd_cases = {}, {}
        for i in range(ratio):
            strb_from = i     * dw_from//8
            strb_to   = (i+1) * dw_from//8
            data_from = i     * dw_from
            data_to   = (i+1) * dw_from
            wr_cases[i] = [
                slave.w.strb[strb_from:strb_to].eq(master.w.strb),
                slave.w.data[data_from:data_to].eq(master.w.data),
            ]
            rd_cases[i] = [
                master.r.data.eq(slave.r.data[data_from:data_to]),
            ]

        # Switch current word based on the last valid master address.
        self.sync += If(master.aw.valid, wr_word_r.eq(wr_word))
        self.sync += If(master.ar.valid, rd_word_r.eq(rd_word))
        self.comb += [
            Case(master.aw.valid, {
                0: wr_word.eq(wr_word_r),
                1: wr_word.eq(master.aw.addr[master_align:slave_align]),
            }),
            Case(master.ar.valid, {
                0: rd_word.eq(rd_word_r),
                1: rd_word.eq(master.ar.addr[master_align:slave_align]),
            }),
        ]

        self.comb += Case(wr_word, wr_cases)
        self.comb += Case(rd_word, rd_cases)

class AXILiteConverter(Module):
    """AXILite data width converter"""
    def __init__(self, master, slave):
        self.master = master
        self.slave = slave

        # # #

        dw_from = len(master.r.data)
        dw_to   = len(slave.r.data)
        ratio   = dw_from/dw_to

        if ratio > 1:
            self.submodules += AXILiteDownConverter(master, slave)
        elif ratio < 1:
            self.submodules += AXILiteUpConverter(master, slave)
        else:
            self.comb += master.connect(slave)

# AXILite Clock Domain Crossing --------------------------------------------------------------------

class AXILiteClockDomainCrossing(Module):
    """AXILite Clock Domain Crossing"""
    def __init__(self, master, slave, cd_from="sys", cd_to="sys"):
        # Same Clock Domain, direct connection.
        if cd_from == cd_to:
            self.comb += [
                # Write.
                master.aw.connect(slave.aw),
                master.w.connect(slave.w),
                slave.b.connect(master.b),
                # Read.
                master.ar.connect(slave.ar),
                slave.r.connect(master.r),
            ]
        # Clock Domain Crossing.
        else:
            # Write.
            aw_cdc = stream.ClockDomainCrossing(master.aw.description, cd_from,   cd_to)
            w_cdc  = stream.ClockDomainCrossing(master.w.description,  cd_from,   cd_to)
            b_cdc  = stream.ClockDomainCrossing(master.b.description,    cd_to, cd_from)
            self.submodules += aw_cdc, w_cdc, b_cdc
            self.comb += [
                master.aw.connect(aw_cdc.sink),
                aw_cdc.source.connect(slave.aw),
                master.w.connect(w_cdc.sink),
                w_cdc.source.connect(slave.w),
                slave.b.connect(b_cdc.sink),
                b_cdc.source.connect(master.b),
            ]
            # Read.
            ar_cdc = stream.ClockDomainCrossing(master.ar.description, cd_from,   cd_to)
            r_cdc  = stream.ClockDomainCrossing(master.r.description,    cd_to, cd_from)
            self.submodules += ar_cdc, r_cdc
            self.comb += [
                master.ar.connect(ar_cdc.sink),
                ar_cdc.source.connect(slave.ar),
                slave.r.connect(r_cdc.sink),
                r_cdc.source.connect(master.r),
            ]

# AXILite Timeout ----------------------------------------------------------------------------------

class AXILiteTimeout(Module):
    """Protect master against slave timeouts (master _has_ to respond correctly)"""
    def __init__(self, master, cycles):
        self.error = Signal()
        wr_error   = Signal()
        rd_error   = Signal()

        # # #

        self.comb += self.error.eq(wr_error | rd_error)

        wr_timer = WaitTimer(int(cycles))
        rd_timer = WaitTimer(int(cycles))
        self.submodules += wr_timer, rd_timer

        def channel_fsm(timer, wait_cond, error, response):
            fsm = FSM(reset_state="WAIT")
            fsm.act("WAIT",
                timer.wait.eq(wait_cond),
                # done is updated in `sync`, so we must make sure that `ready` has not been issued
                # by slave during that single cycle, by checking `timer.wait`.
                If(timer.done & timer.wait,
                    error.eq(1),
                    NextState("RESPOND")
                )
            )
            fsm.act("RESPOND", *response)
            return fsm

        self.submodules.wr_fsm = channel_fsm(
            timer     = wr_timer,
            wait_cond = (master.aw.valid & ~master.aw.ready) | (master.w.valid & ~master.w.ready),
            error     = wr_error,
            response  = [
                master.aw.ready.eq(master.aw.valid),
                master.w.ready.eq(master.w.valid),
                master.b.valid.eq(~master.aw.valid & ~master.w.valid),
                master.b.resp.eq(RESP_SLVERR),
                If(master.b.valid & master.b.ready,
                    NextState("WAIT")
                )
            ])

        self.submodules.rd_fsm = channel_fsm(
            timer     = rd_timer,
            wait_cond = master.ar.valid & ~master.ar.ready,
            error     = rd_error,
            response  = [
                master.ar.ready.eq(master.ar.valid),
                master.r.valid.eq(~master.ar.valid),
                master.r.resp.eq(RESP_SLVERR),
                master.r.data.eq(2**len(master.r.data) - 1),
                If(master.r.valid & master.r.ready,
                    NextState("WAIT")
                )
            ])

# AXILite Interconnect -----------------------------------------------------------------------------

class _AXILiteRequestCounter(Module):
    def __init__(self, request, response, max_requests=256):
        self.counter = counter = Signal(max=max_requests)
        self.full = full = Signal()
        self.empty = empty = Signal()
        self.stall = stall = Signal()
        self.ready = self.empty

        self.comb += [
            full.eq(counter == max_requests - 1),
            empty.eq(counter == 0),
            stall.eq(request & full),
        ]

        self.sync += [
            If(request & response,
                counter.eq(counter)
            ).Elif(request & ~full,
                counter.eq(counter + 1)
            ).Elif(response & ~empty,
                counter.eq(counter - 1)
            ),
        ]

class AXILiteInterconnectPointToPoint(Module):
    def __init__(self, master, slave):
        self.comb += master.connect(slave)

class AXILiteArbiter(Module):
    """AXI Lite arbiter

    Arbitrate between master interfaces and connect one to the target. New master will not be
    selected until all requests have been responded to. Arbitration for write and read channels is
    done separately.
    """
    def __init__(self, masters, target):
        self.submodules.rr_write = roundrobin.RoundRobin(len(masters), roundrobin.SP_CE)
        self.submodules.rr_read = roundrobin.RoundRobin(len(masters), roundrobin.SP_CE)

        def get_sig(interface, channel, name):
            return getattr(getattr(interface, channel), name)

        # Mux master->slave signals
        for channel, name, direction in target.layout_flat():
            rr = self.rr_write if channel in ["aw", "w", "b"] else self.rr_read
            if direction == DIR_M_TO_S:
                choices = Array(get_sig(m, channel, name) for m in masters)
                self.comb += get_sig(target, channel, name).eq(choices[rr.grant])

        # Connect slave->master signals
        for channel, name, direction in target.layout_flat():
            rr = self.rr_write if channel in ["aw", "w", "b"] else self.rr_read
            if direction == DIR_S_TO_M:
                source = get_sig(target, channel, name)
                for i, m in enumerate(masters):
                    dest = get_sig(m, channel, name)
                    if name == "ready":
                        self.comb += dest.eq(source & (rr.grant == i))
                    else:
                        self.comb += dest.eq(source)

        # Allow to change rr.grant only after all requests from a master have been responded to.
        self.submodules.wr_lock = wr_lock = _AXILiteRequestCounter(
            request=target.aw.valid & target.aw.ready, response=target.b.valid & target.b.ready)
        self.submodules.rd_lock = rd_lock = _AXILiteRequestCounter(
            request=target.ar.valid & target.ar.ready, response=target.r.valid & target.r.ready)

        # Switch to next request only if there are no responses pending.
        self.comb += [
            self.rr_write.ce.eq(~(target.aw.valid | target.w.valid | target.b.valid) & wr_lock.ready),
            self.rr_read.ce.eq(~(target.ar.valid | target.r.valid) & rd_lock.ready),
        ]

        # Connect bus requests to round-robin selectors.
        self.comb += [
            self.rr_write.request.eq(Cat(*[m.aw.valid | m.w.valid | m.b.valid for m in masters])),
            self.rr_read.request.eq(Cat(*[m.ar.valid | m.r.valid for m in masters])),
        ]

class AXILiteDecoder(Module):
    """AXI Lite decoder

    Decode master access to particular slave based on its decoder function.

    slaves: [(decoder, slave), ...]
        List of slaves with address decoders, where `decoder` is a function:
            decoder(Signal(address_width - log2(data_width//8))) -> Signal(1)
        that returns 1 when the slave is selected and 0 otherwise.
    """
    def __init__(self, master, slaves, register=False):
        # TODO: unused register argument
        addr_shift = log2_int(master.data_width//8)

        channels = {
            "write": {"aw", "w", "b"},
            "read":  {"ar", "r"},
        }
        # Reverse mapping: directions[channel] -> "write"/"read".
        directions = {ch: d for d, chs in channels.items() for ch in chs}

        def new_slave_sel():
            return {"write": Signal(len(slaves)), "read":  Signal(len(slaves))}

        slave_sel_dec = new_slave_sel()
        slave_sel_reg = new_slave_sel()
        slave_sel     = new_slave_sel()

        # We need to hold the slave selected until all responses come back.
        # TODO: we could reuse arbiter counters
        locks = {
            "write": _AXILiteRequestCounter(
                request=master.aw.valid & master.aw.ready,
                response=master.b.valid & master.b.ready),
            "read": _AXILiteRequestCounter(
                request=master.ar.valid & master.ar.ready,
                response=master.r.valid & master.r.ready),
        }
        self.submodules += locks.values()

        def get_sig(interface, channel, name):
            return getattr(getattr(interface, channel), name)

        # # #

        # Decode slave addresses.
        for i, (decoder, bus) in enumerate(slaves):
            self.comb += [
                slave_sel_dec["write"][i].eq(decoder(master.aw.addr[addr_shift:])),
                slave_sel_dec["read"][i].eq(decoder(master.ar.addr[addr_shift:])),
            ]

        # Dhange the current selection only when we've got all responses.
        for channel in locks.keys():
            self.sync += If(locks[channel].ready, slave_sel_reg[channel].eq(slave_sel_dec[channel]))
        # We have to cut the delaying select.
        for ch, final in slave_sel.items():
            self.comb += If(locks[ch].ready,
                             final.eq(slave_sel_dec[ch])
                         ).Else(
                             final.eq(slave_sel_reg[ch])
                         )

        # Connect master->slaves signals except valid/ready.
        for i, (_, slave) in enumerate(slaves):
            for channel, name, direction in master.layout_flat():
                if direction == DIR_M_TO_S:
                    src = get_sig(master, channel, name)
                    dst = get_sig(slave, channel, name)
                    # Mask master control signals depending on slave selection.
                    if name in ["valid", "ready"]:
                        src = src & slave_sel[directions[channel]][i]
                    self.comb += dst.eq(src)

        # Connect slave->master signals masking not selected slaves.
        for channel, name, direction in master.layout_flat():
            if direction == DIR_S_TO_M:
                dst = get_sig(master, channel, name)
                masked = []
                for i, (_, slave) in enumerate(slaves):
                    src = get_sig(slave, channel, name)
                    # Mask depending on channel.
                    mask = Replicate(slave_sel[directions[channel]][i], len(dst))
                    masked.append(src & mask)
                self.comb += dst.eq(reduce(or_, masked))

class AXILiteInterconnectShared(Module):
    """AXI Lite shared interconnect"""
    def __init__(self, masters, slaves, register=False, timeout_cycles=1e6):
        shared = AXILiteInterface(data_width=masters[0].data_width)
        self.submodules.arbiter = AXILiteArbiter(masters, shared)
        self.submodules.decoder = AXILiteDecoder(shared, slaves)
        if timeout_cycles is not None:
            self.submodules.timeout = AXILiteTimeout(shared, timeout_cycles)

class AXILiteCrossbar(Module):
    """AXI Lite crossbar

    MxN crossbar for M masters and N slaves.
    """
    def __init__(self, masters, slaves, register=False, timeout_cycles=1e6):
        matches, busses = zip(*slaves)
        access_m_s = [[AXILiteInterface() for j in slaves] for i in masters]  # a[master][slave]
        access_s_m = list(zip(*access_m_s))  # a[slave][master]
        # Decode each master into its access row.
        for slaves, master in zip(access_m_s, masters):
            slaves = list(zip(matches, slaves))
            self.submodules += AXILiteDecoder(master, slaves, register)
        # Arbitrate each access column onto its slave.
        for masters, bus in zip(access_s_m, busses):
            self.submodules += AXILiteArbiter(masters, bus)
