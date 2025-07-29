#
# This file is part of LiteX.
#
# Copyright (c) 2020-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Direct Memory Access (DMA) reader and writer modules."""

from migen import *

from litex.gen import *
from litex.gen.common import reverse_bytes

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream
from litex.soc.interconnect import wishbone

# Helpers ------------------------------------------------------------------------------------------

def format_bytes(s, endianness):
    return {"big": s, "little": reverse_bytes(s)}[endianness]

# WishboneDMAReader --------------------------------------------------------------------------------

class WishboneDMAReader(LiteXModule):
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
    def __init__(self, bus, endianness="little", fifo_depth=16, with_csr=False):
        assert isinstance(bus, wishbone.Interface)
        self.bus    = bus
        self.sink   = sink   = stream.Endpoint([("address", bus.adr_width)])
        self.source = source = stream.Endpoint([("data",    bus.data_width)])

        # # #

        # FIFO..
        self.fifo = fifo = stream.SyncFIFO([("data", bus.data_width)], depth=fifo_depth)

        # Reads -> FIFO.
        self.comb += [
            bus.stb.eq(sink.valid & fifo.sink.ready),
            bus.cyc.eq(sink.valid & fifo.sink.ready),
            bus.we.eq(0),
            bus.sel.eq(2**(bus.data_width//8)-1),
            bus.adr.eq(sink.address),
            fifo.sink.last.eq(sink.last),
            fifo.sink.data.eq(format_bytes(bus.dat_r, endianness)),
            If(bus.stb & bus.ack,
                sink.ready.eq(1),
                fifo.sink.valid.eq(1),
            ),
        ]

        # FIFO -> Output.
        self.comb += fifo.source.connect(source)

        # CSRs.
        if with_csr:
            self.add_csr()

    def add_ctrl(self, default_base=0, default_length=0, default_enable=0, default_loop=0):
        self.base   = Signal(64, reset=default_base)
        self.length = Signal(32, reset=default_length)
        self.enable = Signal(reset=default_enable)
        self.done   = Signal()
        self.loop   = Signal(reset=default_loop)
        self.offset = Signal(32)

        # # #

        shift   = log2_int(self.bus.data_width//8)
        base    = Signal(self.bus.adr_width)
        offset  = Signal(self.bus.adr_width)
        length  = Signal(self.bus.adr_width)
        self.comb += base.eq(self.base[shift:])
        self.comb += length.eq(self.length[shift:])

        self.comb += self.offset.eq(offset)

        self.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))
        self.comb += fsm.reset.eq(~self.enable)
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
                    If(self.loop,
                        NextValue(offset, 0)
                    ).Else(
                        NextState("DONE")
                    )
                )
            )
        )
        fsm.act("DONE", self.done.eq(1))

    def add_csr(self, default_base=0, default_length=0, default_enable=0, default_loop=0):
        if not hasattr(self, "base"):
            self.add_ctrl()
        self._base   = CSRStorage(64, reset=default_base)
        self._length = CSRStorage(32, reset=default_length)
        self._enable = CSRStorage(reset=default_enable)
        self._done   = CSRStatus()
        self._loop   = CSRStorage(reset=default_loop)
        self._offset = CSRStatus(32)

        # # #

        self.comb += [
            # Control.
            self.base.eq(self._base.storage),
            self.length.eq(self._length.storage),
            self.enable.eq(self._enable.storage),
            self.loop.eq(self._loop.storage),
            # Status.
            self._done.status.eq(self.done),
            self._offset.status.eq(self.offset),
        ]

# WishboneDMAWriter --------------------------------------------------------------------------------

class WishboneDMAWriter(LiteXModule):
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

        # Writes.
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

        # CSRs.
        if with_csr:
            self.add_csr()

    def add_ctrl(self, default_base=0, default_length=0, default_enable=0, default_loop=0, ready_on_idle=1):
        self._sink = self.sink
        self.sink  = stream.Endpoint([("data", self.bus.data_width)])

        self.base   = Signal(64, reset=default_base)
        self.length = Signal(32, reset=default_length)
        self.enable = Signal(reset=default_enable)
        self.done   = Signal()
        self.loop   = Signal(reset=default_loop)
        self.offset = Signal(32)

        # # #

        shift   = log2_int(self.bus.data_width//8)
        base    = Signal(self.bus.adr_width)
        offset  = Signal(self.bus.adr_width)
        length  = Signal(self.bus.adr_width)
        self.comb += base.eq(self.base[shift:])
        self.comb += length.eq(self.length[shift:])

        self.comb += self.offset.eq(offset)

        self.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))
        self.comb += fsm.reset.eq(~self.enable)
        fsm.act("IDLE",
            self.sink.ready.eq(ready_on_idle),
            NextValue(offset, 0),
            NextState("RUN"),
        )
        fsm.act("RUN",
            self._sink.valid.eq(self.sink.valid),
            self._sink.last.eq(self.sink.last | (offset + 1 == length)),
            self._sink.address.eq(base + offset),
            self._sink.data.eq(self.sink.data),
            self.sink.ready.eq(self._sink.ready),
            If(self.sink.valid & self.sink.ready,
                NextValue(offset, offset + 1),
                If(self._sink.last,
                    If(self.loop,
                        NextValue(offset, 0)
                    ).Else(
                        NextState("DONE")
                    )
                )
            )
        )
        fsm.act("DONE", self.done.eq(1))

    def add_csr(self, default_base=0, default_length=0, default_enable=0, default_loop=0):
        if not hasattr(self, "base"):
            self.add_ctrl()
        self._base   = CSRStorage(64, reset=default_base)
        self._length = CSRStorage(32, reset=default_length)
        self._enable = CSRStorage(reset=default_enable)
        self._done   = CSRStatus()
        self._loop   = CSRStorage(reset=default_loop)
        self._offset = CSRStatus(32)

        # # #

        self.comb += [
            # Control.
            self.base.eq(self._base.storage),
            self.length.eq(self._length.storage),
            self.enable.eq(self._enable.storage),
            self.loop.eq(self._loop.storage),
            # Status.
            self._done.status.eq(self.done),
            self._offset.status.eq(self.offset),
        ]

class WishboneDMAReaderWriter(LiteXModule):
    """Read and write data from Wishbone MMAP memory.

    Parameters
    ----------
    bus : bus
        Wishbone bus of the SoC to read and write from.

    Attributes
    ----------
    we : Signal()
        Write Enable. If set, it will write to the bus, otherwise it will read.

    w_sink : Record("address", "data")
        Sink for MMAP addresses/datas to be written.

    r_sink : Record("address")
        Sink for MMAP addresses to be read.

    source : Record("data")
        Source for MMAP word results from reading.
    
    sink : Record("data")
        Sink for MMAP datas to be written.
    """
    def __init__(self, bus, endianness="little", fifo_depth=16, with_csr=False):
        assert isinstance(bus, wishbone.Interface)
        self.bus    = bus
        self.r_sink = r_sink = stream.Endpoint([("address", bus.adr_width)])
        self.source = source = stream.Endpoint([("data",    bus.data_width)])
        self.w_sink = w_sink = stream.Endpoint([("address", bus.adr_width), ("data", bus.data_width)])

        self.we = we = Signal()

        # # #

        # FIFO..
        self.fifo = fifo = stream.SyncFIFO([("data", bus.data_width)], depth=fifo_depth)

        # Reads -> FIFO.
        self.comb += [
            If(we,
                bus.stb.eq(w_sink.valid),
                bus.adr.eq(w_sink.address),
                bus.dat_w.eq(format_bytes(w_sink.data, endianness)),
                w_sink.ready.eq(bus.ack),
            ).Else(
                bus.stb.eq(r_sink.valid & fifo.sink.ready),
                bus.adr.eq(r_sink.address),
                fifo.sink.last.eq(r_sink.last),
                fifo.sink.data.eq(format_bytes(bus.dat_r, endianness)),
                If(bus.stb & bus.ack,
                    r_sink.ready.eq(1),
                    fifo.sink.valid.eq(1),
                ),
            ),  
            bus.we.eq(we),
            bus.sel.eq(2**(bus.data_width//8)-1),
            bus.cyc.eq(bus.stb),
        ]

        # FIFO -> Output.
        self.comb += fifo.source.connect(source)

        # CSRs.
        if with_csr:
            self.add_csr()

    def add_ctrl(self, default_base=0, default_length=0, default_enable=0, default_loop=0, ready_on_idle=1):
        self.sink  = stream.Endpoint([("data", self.bus.data_width)])

        self.base   = Signal(64, reset=default_base)
        self.length = Signal(32, reset=default_length)
        self.enable = Signal(reset=default_enable)
        self.done   = Signal()
        self.loop   = Signal(reset=default_loop)
        self.offset = Signal(32)

        # # #

        shift   = log2_int(self.bus.data_width//8)
        base    = Signal(self.bus.adr_width)
        offset  = Signal(self.bus.adr_width)
        length  = Signal(self.bus.adr_width)
        self.comb += base.eq(self.base[shift:])
        self.comb += length.eq(self.length[shift:])

        self.comb += self.offset.eq(offset)

        self.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))
        self.comb += fsm.reset.eq(~self.enable)
        if ready_on_idle:
            self.comb += If(~self.we, self.sink.ready.eq(1))  # Read sink is always ready when not writing.
        fsm.act("IDLE",
            self.sink.ready.eq(ready_on_idle),
            NextValue(offset, 0),
            NextState("RUN"),
        )
        fsm.act("RUN",
            If(self.we,
                self.w_sink.valid.eq(self.sink.valid),
                self.w_sink.last.eq(self.sink.last | (offset + 1 == length)),
                self.w_sink.address.eq(base + offset),
                self.w_sink.data.eq(self.sink.data),
                self.sink.ready.eq(self.w_sink.ready),
                If(self.sink.valid & self.sink.ready,
                    NextValue(offset, offset + 1),
                    If(self.w_sink.last,
                        If(self.loop,
                            NextValue(offset, 0)
                        ).Else(
                            NextState("DONE")
                        )
                    )
                )
            ).Else(
                self.r_sink.valid.eq(1),
                self.r_sink.last.eq(offset == (length - 1)),
                self.r_sink.address.eq(base + offset),
                If(self.r_sink.ready,
                    NextValue(offset, offset + 1),
                    If(self.r_sink.last,
                        If(self.loop,
                            NextValue(offset, 0)
                        ).Else(
                            NextState("DONE")
                        )
                    )
                )
            )
        )
        fsm.act("DONE", self.done.eq(1))

    def add_csr(self, default_base=0, default_length=0, default_enable=0, default_loop=0):
        if not hasattr(self, "base"):
            self.add_ctrl()
        self._base   = CSRStorage(64, reset=default_base)
        self._length = CSRStorage(32, reset=default_length)
        self._enable = CSRStorage(reset=default_enable)
        self._done   = CSRStatus()
        self._loop   = CSRStorage(reset=default_loop)
        self._offset = CSRStatus(32)
        self._we     = CSRStorage()

        # # #

        self.comb += [
            # Control.
            self.base.eq(self._base.storage),
            self.length.eq(self._length.storage),
            self.enable.eq(self._enable.storage),
            self.we.eq(self._we.storage),  # Write Enable.
            self.loop.eq(self._loop.storage),
            # Status.
            self._done.status.eq(self.done),
            self._offset.status.eq(self.offset),
        ]
