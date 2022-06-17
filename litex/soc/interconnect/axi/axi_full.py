#
# This file is part of LiteX.
#
# Copyright (c) 2018-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""AXI4-Full/Lite support for LiteX"""

from migen import *
from migen.genlib import roundrobin
from migen.genlib.misc import WaitTimer

from litex.soc.interconnect import stream
from litex.build.generic_platform import *

from litex.soc.interconnect.axi.axi_common import *

# AXI Definition -----------------------------------------------------------------------------------

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

class AXIInterface:
    def __init__(self, data_width=32, address_width=32, id_width=1, clock_domain="sys", name=None, bursting=False):
        self.data_width    = data_width
        self.address_width = address_width
        self.id_width      = id_width
        self.clock_domain  = clock_domain
        self.bursting      = bursting # FIXME: Use or add check.

        self.aw = stream.Endpoint(ax_description(address_width, id_width), name=name)
        self.w  = stream.Endpoint(w_description(data_width, id_width),     name=name)
        self.b  = stream.Endpoint(b_description(id_width),                 name=name)
        self.ar = stream.Endpoint(ax_description(address_width, id_width), name=name)
        self.r  = stream.Endpoint(r_description(data_width, id_width),     name=name)

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
        return connect_axi(self, slave, **kwargs)

    def layout_flat(self):
        return list(axi_layout_flat(self))

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

# AXI Data-Width Converter -------------------------------------------------------------------------

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


class AXIDownConverter(Module):
    def __init__(self, axi_from, axi_to):
        dw_from  = len(axi_from.r.data)
        dw_to    = len(axi_to.r.data)
        ratio    = int(dw_from//dw_to)
        assert dw_from == dw_to*ratio

        # # #

        # Write path -------------------------------------------------------------------------------

        # AW Channel.
        self.comb += [
            axi_from.aw.connect(axi_to.aw, omit={"len", "size"}),
            axi_to.aw.len.eq( axi_from.aw.len << log2_int(ratio)),
            axi_to.aw.size.eq(axi_from.aw.size - log2_int(ratio)),
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
            axi_to.ar.len.eq( axi_from.ar.len << log2_int(ratio)),
            axi_to.ar.size.eq(axi_from.ar.size - log2_int(ratio)),
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


class AXIConverter(Module):
    """AXI data width converter"""
    def __init__(self, master, slave):
        self.master = master
        self.slave  = slave

        # # #

        dw_from = len(master.r.data)
        dw_to   = len(slave.r.data)
        ratio   = dw_from/dw_to

        if ratio > 1:
            self.submodules += AXIDownConverter(master, slave)
        elif ratio < 1:
            self.submodules += AXIUpConverter(master, slave)
        else:
            self.comb += master.connect(slave)
