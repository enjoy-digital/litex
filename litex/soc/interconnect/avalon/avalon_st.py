#
# This file is part of LiteX.
#
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Avalon ST support for LiteX"""

from migen import *

from litex.soc.interconnect import stream

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
