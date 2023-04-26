#
# This file is part of LiteX.
#
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2023 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

"""Avalon support for LiteX"""

from migen import *

from litex.soc.interconnect import stream
from . import wishbone

_layout = [
    ("address",          "adr_width", DIR_M_TO_S),
    ("writedata",       "data_width", DIR_M_TO_S),
    ("readdata",        "data_width", DIR_S_TO_M),
    ("readdatavalid",              1, DIR_S_TO_M),
    ("byteenable",       "sel_width", DIR_M_TO_S),
    ("read",                       1, DIR_M_TO_S),
    ("write",                      1, DIR_M_TO_S),
    ("waitrequest",                1, DIR_S_TO_M),
    ("burstbegin",                 1, DIR_M_TO_S), # this is optional
    ("burstcount",                 8, DIR_M_TO_S),
    ("chipselect",                 1, DIR_M_TO_S), # this is optional
]

class AvalonMMInterface(Record):
    def __init__(self, data_width=32, adr_width=30, bursting=False, **kwargs):
        self.data_width = data_width
        self.bursting   = bursting
        if kwargs.get("adr_width", False):
            adr_width = kwargs["adr_width"] - int(log2(data_width//8))
        self.adr_width = adr_width
        Record.__init__(self, set_layout_parameters(_layout,
            adr_width  = adr_width,
            data_width = data_width,
            sel_width  = data_width//8))
        self.address.reset_less    = True
        self.writedata.reset_less  = True
        self.readdata.reset_less   = True
        self.byteenable.reset_less = True

    @staticmethod
    def like(other):
        return AvalonMMInterface(len(other.writedata))

    def get_ios(self, bus_name="avl"):
        subsignals = []
        for name, width, direction in self.layout:
            subsignals.append(Subsignal(name, Pins(width)))
        ios = [(bus_name , 0) + tuple(subsignals)]
        return ios

    def connect_to_pads(self, pads, mode="master"):
        assert mode in ["slave", "master"]
        r = []
        for name, width, direction in self.layout:
            sig  = getattr(self, name)
            pad  = getattr(pads, name)
            if mode == "master":
                if direction == DIR_M_TO_S:
                    r.append(pad.eq(sig))
                else:
                    r.append(sig.eq(pad))
            else:
                if direction == DIR_S_TO_M:
                    r.append(pad.eq(sig))
                else:
                    r.append(sig.eq(pad))
        return r

    def bus_read(self, address, byteenable=None, burstcount=None, chipselect=None):
        if byteenable is None:
            byteenable = 2**len(self.byteenable) - 1
        yield self.address.eq(address)
        yield self.write.eq(0)
        yield self.read.eq(1)
        yield self.byteenable.eq(byteenable)
        if burstcount is not None:
            yield self.burstcount.eq(burstcount)
        if chipselect is not None:
            yield self.chipselect.eq(chipselect)
        yield
        while (yield self.waitrequest):
            yield
        yield self.read.eq(0)
        # actually don't care outside of a transaction
        # this makes the traces look neater
        yield self.byteenable.eq(0)
        if burstcount is not None:
            yield self.burstcount.eq(0)
        if chipselect is not None:
            yield self.chipselect.eq(0)
        while not (yield self.readdatavalid):
            yield
        return (yield self.readdata)

    def bus_write(self, address, writedata, byteenable=None, chipselect=None):
        if not isinstance(writedata, list):
            writedata = [ writedata ]
        burstcount = len(writedata)
        if byteenable is None:
            byteenable = 2**len(self.byteenable) - 1
        yield self.address.eq(address)
        yield self.write.eq(1)
        yield self.read.eq(0)
        yield self.byteenable.eq(byteenable)
        if burstcount is not None:
            yield self.burstcount.eq(burstcount)
        if chipselect is not None:
            yield self.chipselect.eq(chipselect)
        for data in writedata:
            yield self.writedata.eq(data)
            yield
            while (yield self.waitrequest):
                yield
            yield self.burstcount.eq(0)
        yield self.writedata.eq(0)
        yield self.write.eq(0)
        # actually don't care outside of a transaction
        # this makes the traces look neater
        yield self.byteenable.eq(0)
        if chipselect is not None:
            yield self.chipselect.eq(0)

class AvalonMM2Wishbone(Module):
    def __init__(self, data_width=32, address_width=32):
        self.wishbone = wb  = wishbone.Interface(data_width=data_width, adr_width=address_width)
        self.avalon   = avl = AvalonMMInterface(data_width=data_width, adr_width=address_width)

        read_access   = Signal()
        readdatavalid = Signal()
        readdata      = Signal(data_width)

        self.sync += [
             If  (wb.ack | wb.err, read_access.eq(0)) \
            .Elif(avl.read,        read_access.eq(1)),
        ]

        # Wishbone -> Avalon
        self.comb += [
            avl.waitrequest.eq(~(wb.ack | wb.err)),
            readdatavalid.eq((wb.ack | wb.err) & read_access),
            readdata.eq(wb.dat_r),
            avl.readdatavalid.eq(readdatavalid),
            avl.readdata.eq(readdata),
        ]

        # Avalon -> Wishbone
        self.comb += [
            wb.adr.eq(avl.address),
            wb.dat_w.eq(avl.writedata),
            wb.sel.eq(avl.byteenable),
            wb.we.eq(avl.write),
            wb.cyc.eq(read_access | avl.write),
            wb.stb.eq(read_access | avl.write),
            wb.cti.eq(wishbone.CTI_BURST_END),
            wb.bte.eq(Constant(0, 2)),
        ]


# Avalon-ST to/from native LiteX's stream ----------------------------------------------------------

# In native LiteX's streams, ready signal has no latency (similar to AXI). In Avalon-ST streams the
# ready signal has a latency: If ready is asserted on cycle n, then cycle n + latency is a "ready"
# in the LiteX/AXI's sense) cycle. This means that:
# - when converting to Avalon-ST, we need to add this latency on datas.
# - when converting from Avalon-ST, we need to make sure we are able to store datas for "latency"
# cycles after ready deassertion on the native interface.

class Native2AvalonST(Module):
    """Native LiteX's stream to Avalon-ST stream"""
    def __init__(self, layout, latency=2):
        self.sink   = sink   = stream.Endpoint(layout)
        self.source = source = stream.Endpoint(layout)

        # # #

        _from = sink
        for n in range(latency):
            _to = stream.Endpoint(layout)
            self.sync += _from.connect(_to, omit={"ready"})
            if n == 0:
                self.sync += _to.valid.eq(sink.valid & source.ready)
            _from = _to
        self.comb += _to.connect(source, omit={"ready"})
        self.comb += sink.ready.eq(source.ready)


class AvalonST2Native(Module):
    """Avalon-ST Stream to native LiteX's stream"""
    def __init__(self, layout, latency=2):
        self.sink   = sink   = stream.Endpoint(layout)
        self.source = source = stream.Endpoint(layout)

        # # #

        buf = stream.SyncFIFO(layout, latency)
        self.submodules += buf
        self.comb += sink.connect(buf.sink, omit={"ready"})
        self.comb += sink.ready.eq(source.ready)
        self.comb += buf.source.connect(source)
