#
# This file is part of LiteX.
#
# Copyright (c) 2020-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Direct Memory Access (DMA) reader and writer modules."""

from migen import *

from litex.gen.common import reverse_bytes

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream
from litex.soc.interconnect import wishbone

# Helpers ------------------------------------------------------------------------------------------

def format_bytes(s, endianness):
    return {"big": s, "little": reverse_bytes(s)}[endianness]

# WishboneDMAReader --------------------------------------------------------------------------------

class WishboneDMAReader(Module, AutoCSR):
    """Read data from Wishbone MMAP memory.

    For every address written to the sink, one word will be produced on the source.

    Parameters
    ----------
    bus : bus
        Wishbone bus of the SoC to read from.

    Attributes
    ----------
    sink : Record("address")
        Sink for MMAP addresses to be read.

    source : Record("data")
        Source for MMAP word results from reading.
    """
    def __init__(self, bus, endianness="little", with_csr=False):
        assert isinstance(bus, wishbone.Interface)
        self.bus    = bus
        self.sink   = sink   = stream.Endpoint([("address", bus.adr_width, ("last", 1))])
        self.source = source = stream.Endpoint([("data",    bus.data_width)])

        # # #

        data = Signal(bus.data_width)

        self.submodules.fsm = fsm = FSM(reset_state="BUS-READ")
        fsm.act("BUS-READ",
            bus.stb.eq(sink.valid),
            bus.cyc.eq(sink.valid),
            bus.we.eq(0),
            bus.sel.eq(2**(bus.data_width//8)-1),
            bus.adr.eq(sink.address),
            If(bus.stb & bus.ack,
                NextValue(data, format_bytes(bus.dat_r, endianness)),
                NextState("SOURCE-WRITE")
            )
        )
        fsm.act("SOURCE-WRITE",
            source.valid.eq(1),
            source.last.eq(sink.last),
            source.data.eq(data),
            If(source.ready,
                sink.ready.eq(1),
                NextState("BUS-READ")
            )
        )

        if with_csr:
            self.add_csr()

    def add_csr(self, default_base=0, default_length=0, default_enable=0, default_loop=0):
        self._base   = CSRStorage(64, reset=default_base)
        self._length = CSRStorage(32, reset=default_length)
        self._enable = CSRStorage(reset=default_enable)
        self._done   = CSRStatus()
        self._loop   = CSRStorage(reset=default_loop)
        self._offset = CSRStatus(32)

        # # #

        shift   = log2_int(self.bus.data_width//8)
        base    = Signal(self.bus.adr_width)
        offset  = Signal(self.bus.adr_width)
        length  = Signal(self.bus.adr_width)
        self.comb += base.eq(self._base.storage[shift:])
        self.comb += length.eq(self._length.storage[shift:])

        self.comb += self._offset.status.eq(offset)

        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.submodules += fsm
        self.comb += fsm.reset.eq(~self._enable.storage)
        fsm.act("IDLE",
            NextValue(offset, 0),
            NextState("RUN"),
        )
        fsm.act("RUN",
            self.sink.valid.eq(1),
            self.sink.last.eq(offset == (length - 1)),
            self.sink.address.eq(base + offset),
            If(self.sink.ready,
                NextValue(offset, offset + 1),
                If(self.sink.last,
                    If(self._loop.storage,
                        NextValue(offset, 0)
                    ).Else(
                        NextState("DONE")
                    )
                )
            )
        )
        fsm.act("DONE", self._done.status.eq(1))

# WishboneDMAWriter --------------------------------------------------------------------------------

class WishboneDMAWriter(Module, AutoCSR):
    """Write data to Wishbone MMAP memory.

    Parameters
    ----------
    bus : bus
        Wishbone bus of the SoC to read from.

    Attributes
    ----------
    sink : Record("address", "data")
        Sink for MMAP addresses/datas to be written.
    """
    def __init__(self, bus, endianness="little", with_csr=False):
        assert isinstance(bus, wishbone.Interface)
        self.bus  = bus
        self.sink = sink = stream.Endpoint([("address", bus.adr_width), ("data", bus.data_width)])

        # # #

        data = Signal(bus.data_width)

        self.comb += [
            bus.stb.eq(sink.valid),
            bus.cyc.eq(sink.valid),
            bus.we.eq(1),
            bus.sel.eq(2**(bus.data_width//8)-1),
            bus.adr.eq(sink.address),
            bus.dat_w.eq(format_bytes(sink.data, endianness)),
            sink.ready.eq(bus.ack),
        ]

        if with_csr:
            self.add_csr()

    def add_csr(self, default_base=0, default_length=0, default_enable=0, default_loop=0):
        self._sink = self.sink
        self.sink  = stream.Endpoint([("data", self.bus.data_width)])

        self._base   = CSRStorage(64, reset=default_base)
        self._length = CSRStorage(32, reset=default_length)
        self._enable = CSRStorage(reset=default_enable)
        self._done   = CSRStatus()
        self._loop   = CSRStorage(reset=default_loop)
        self._offset = CSRStatus(32)

        # # #

        shift   = log2_int(self.bus.data_width//8)
        base    = Signal(self.bus.adr_width)
        offset  = Signal(self.bus.adr_width)
        length  = Signal(self.bus.adr_width)
        self.comb += base.eq(self._base.storage[shift:])
        self.comb += length.eq(self._length.storage[shift:])

        self.comb += self._offset.status.eq(offset)

        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.submodules += fsm
        self.comb += fsm.reset.eq(~self._enable.storage)
        fsm.act("IDLE",
            self.sink.ready.eq(1),
            NextValue(offset, 0),
            NextState("RUN"),
        )
        fsm.act("RUN",
            self._sink.valid.eq(self.sink.valid),
            self._sink.last.eq(offset == (length - 1)),
            self._sink.address.eq(base + offset),
            self._sink.data.eq(self.sink.data),
            self.sink.ready.eq(self._sink.ready),
            If(self.sink.valid & self.sink.ready,
                NextValue(offset, offset + 1),
                If(self._sink.last,
                    If(self._loop.storage,
                        NextValue(offset, 0)
                    ).Else(
                        NextState("DONE")
                    )
                )
            )
        )
        fsm.act("DONE", self._done.status.eq(1))
