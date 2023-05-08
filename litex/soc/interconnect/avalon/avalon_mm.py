#
# This file is part of LiteX.
#
# Copyright (c) 2023 Hans Baier <hansfbaier@gmail.com>
# Copyright (c) 2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Avalon support for LiteX"""

from migen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect import wishbone

# Avalon MM Layout ---------------------------------------------------------------------------------

_layout = [
    ("address",          "adr_width", DIR_M_TO_S),
    ("writedata",       "data_width", DIR_M_TO_S),
    ("readdata",        "data_width", DIR_S_TO_M),
    ("readdatavalid",              1, DIR_S_TO_M),
    ("byteenable",       "sel_width", DIR_M_TO_S),
    ("read",                       1, DIR_M_TO_S),
    ("write",                      1, DIR_M_TO_S),
    ("waitrequest",                1, DIR_S_TO_M),
    ("burstbegin",                 1, DIR_M_TO_S), # Optional.
    ("burstcount",                 8, DIR_M_TO_S),
    ("chipselect",                 1, DIR_M_TO_S), # Optional.
]

# Avalon MM Interface ------------------------------------------------------------------------------

class AvalonMMInterface(Record):
    def __init__(self, data_width=32, adr_width=30, **kwargs):
        self.data_width = data_width
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

    def bus_read(self, address, byteenable=None, burstcount=1, chipselect=None):
        if byteenable is None:
            byteenable = 2**len(self.byteenable) - 1
        yield self.address.eq(address)
        yield self.write.eq(0)
        yield self.read.eq(1)
        yield self.byteenable.eq(byteenable)
        if burstcount != 1:
            yield self.burstcount.eq(burstcount)
        if chipselect is not None:
            yield self.chipselect.eq(chipselect)
        yield
        while (yield self.waitrequest):
            yield
        yield self.read.eq(0)
        # Actually don't care outside of a transaction this makes the traces look neater.
        yield self.byteenable.eq(0)
        if burstcount != 1:
            yield self.burstcount.eq(0)
        if chipselect is not None:
            yield self.chipselect.eq(0)

        while not (yield self.readdatavalid):
            yield
        return (yield self.readdata)

    def continue_read_burst(self):
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
