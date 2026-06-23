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

def format_bytes(s, endianness, with_byteswap=None):
    if endianness not in ["big", "little"]:
        raise ValueError("endianness must be big or little.")
    if with_byteswap is None:
        with_byteswap = {"big": False, "little": True}[endianness]
    return reverse_bytes(s) if with_byteswap else s

def add_wishbone_burst_cti(module, bus, last, bursting):
    """Optionally add Wishbone CTI/BTE burst tagging.

    When enabled, the DMA emits incrementing-burst CTI values and uses linear BTE.
    Raw stream users must drive ``last`` on the final beat of a burst.
    """
    if bursting is None:
        bursting = getattr(bus, "bursting", False)
    if not bursting:
        return

    if not hasattr(bus, "cti"):
        raise ValueError("Wishbone burst support requires a bus with CTI.")
    if not hasattr(bus, "bte"):
        raise ValueError("Wishbone burst support requires a bus with BTE.")

    module.comb += [
        bus.cti.eq(wishbone.CTI_BURST_NONE),
        bus.bte.eq(0b00), # Linear burst.
        If(bus.cyc,
            If(last,
                bus.cti.eq(wishbone.CTI_BURST_END)
            ).Else(
                bus.cti.eq(wishbone.CTI_BURST_INCREMENTING)
            )
        )
    ]

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
    def __init__(self, bus, endianness="little", fifo_depth=16, with_csr=False, bursting=None,
        with_byteswap=None):
        """Create a Wishbone DMA reader.

        ``endianness`` preserves the legacy behavior: ``"little"`` byte-swaps the Wishbone word
        before presenting it on the stream, while ``"big"`` leaves it unchanged. Raw word users
        can set ``with_byteswap=False`` explicitly to keep the Wishbone word order independent of
        CPU endianness.
        """
        if not isinstance(bus, wishbone.Interface):
            raise TypeError("DMAReader requires a Wishbone bus.")
        if "r" not in bus.mode:
            raise ValueError("DMAReader requires a readable Wishbone bus.")
        self.bus    = bus
        self.sink   = sink   = stream.Endpoint([("address", bus.adr_width, ("last", 1))])
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
            fifo.sink.data.eq(format_bytes(bus.dat_r, endianness, with_byteswap)),
            If(bus.stb & bus.ack,
                sink.ready.eq(1),
                fifo.sink.valid.eq(1),
            ),
        ]

        # FIFO -> Output.
        self.comb += fifo.source.connect(source)

        # Optional Wishbone burst support.
        add_wishbone_burst_cti(
            module     = self,
            bus        = bus,
            last       = sink.last,
            bursting   = bursting,
        )

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
        self._base   = CSRStorage(64, reset=default_base,   description="DMA Reader base address.")
        self._length = CSRStorage(32, reset=default_length, description="DMA Reader transfer length in bytes.")
        self._enable = CSRStorage(reset=default_enable,     description="DMA Reader enable.")
        self._done   = CSRStatus(1,                         description="DMA Reader transfer done.")
        self._loop   = CSRStorage(reset=default_loop,       description="DMA Reader loop enable.")
        self._offset = CSRStatus(32,                        description="DMA Reader current transfer offset.")

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
    def __init__(self, bus, endianness="little", with_csr=False, bursting=None, with_byteswap=None):
        """Create a Wishbone DMA writer.

        ``endianness`` preserves the legacy behavior: ``"little"`` byte-swaps stream words before
        writing them to Wishbone, while ``"big"`` leaves them unchanged. Raw word users can set
        ``with_byteswap=False`` explicitly to keep the stream word order independent of CPU
        endianness.
        """
        if not isinstance(bus, wishbone.Interface):
            raise TypeError("DMAWriter requires a Wishbone bus.")
        if "w" not in bus.mode:
            raise ValueError("DMAWriter requires a writable Wishbone bus.")
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
            bus.dat_w.eq(format_bytes(sink.data, endianness, with_byteswap)),
            sink.ready.eq(bus.ack),
        ]

        # Optional Wishbone burst support.
        add_wishbone_burst_cti(
            module     = self,
            bus        = bus,
            last       = sink.last,
            bursting   = bursting,
        )

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
        self._base   = CSRStorage(64, reset=default_base,   description="DMA Writer base address.")
        self._length = CSRStorage(32, reset=default_length, description="DMA Writer transfer length in bytes.")
        self._enable = CSRStorage(reset=default_enable,     description="DMA Writer enable.")
        self._done   = CSRStatus(1,                         description="DMA Writer transfer done.")
        self._loop   = CSRStorage(reset=default_loop,       description="DMA Writer loop enable.")
        self._offset = CSRStatus(32,                        description="DMA Writer current transfer offset.")

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
