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
        """Add a byte-addressed transfer controller.

        Base and length must be aligned to bus words and remain stable while enabled. Empty
        transfers complete without bus activity, including in loop mode. Misaligned transfers
        complete with ``error`` asserted; disable the controller before starting a new transfer.
        """
        self.base   = Signal(64, reset=default_base)
        self.length = Signal(32, reset=default_length)
        self.enable = Signal(reset=default_enable)
        self.done   = Signal()
        self.error  = Signal()
        self.loop   = Signal(reset=default_loop)
        self.offset = Signal(32)

        # # #

        shift   = log2_int(self.bus.data_width//8)
        base    = Signal(self.bus.adr_width)
        offset  = Signal(self.bus.adr_width)
        length  = Signal(self.bus.adr_width)
        self.comb += base.eq(self.base[shift:])
        self.comb += length.eq(self.length[shift:])
        unaligned = (self.base[:shift] != 0) | (self.length[:shift] != 0) if shift else 0

        self.comb += self.offset.eq(offset)

        self.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))
        self.comb += fsm.reset.eq(~self.enable)
        fsm.act("IDLE",
            NextValue(offset, 0),
            If(self.length == 0,
                NextState("DONE"),
            ).Elif(unaligned,
                NextState("ERROR"),
            ).Else(
                NextState("RUN"),
            ),
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
        fsm.act("ERROR", self.done.eq(1), self.error.eq(1))

    def add_csr(self, default_base=0, default_length=0, default_enable=0, default_loop=0):
        if not hasattr(self, "base"):
            self.add_ctrl()
        self._base   = CSRStorage(64, reset=default_base,   description="DMA Reader base address.")
        self._length = CSRStorage(32, reset=default_length, description="DMA Reader transfer length in bytes.")
        self._enable = CSRStorage(reset=default_enable,     description="DMA Reader enable.")
        self._done   = CSRStatus(1,                         description="DMA Reader transfer done.")
        self._loop   = CSRStorage(reset=default_loop,       description="DMA Reader loop enable.")
        self._offset = CSRStatus(32,                        description="DMA Reader current transfer offset.")
        self._error  = CSRStatus(1, description="DMA Reader rejected a non-word-aligned base or length. Cleared when disabled.")

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
            self._error.status.eq(self.error),
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
    def __init__(self, bus, endianness="little", with_csr=False, bursting=None, with_byteswap=None, with_be=False):
        """Create a Wishbone DMA writer.

        ``endianness`` preserves the legacy behavior: ``"little"`` byte-swaps stream words before
        writing them to Wishbone, while ``"big"`` leaves them unchanged. Raw word users can set
        ``with_byteswap=False`` explicitly to keep the stream word order independent of CPU
        endianness.

        With ``with_be=True``, ``sink.be`` selects each written byte on every beat, including
        sparse and zero masks. The mask is reversed with the data when byte swapping is enabled.
        A zero-mask beat still completes a bus transaction. The optional controller retains its
        word-aligned base and length contract; masks select bytes within those addressed words.
        """
        if not isinstance(bus, wishbone.Interface):
            raise TypeError("DMAWriter requires a Wishbone bus.")
        if "w" not in bus.mode:
            raise ValueError("DMAWriter requires a writable Wishbone bus.")
        self.bus     = bus
        self.with_be = with_be
        payload_layout = [("address", bus.adr_width), ("data", bus.data_width)]
        if with_be:
            payload_layout += [("be", bus.data_width//8)]
        self.sink = sink = stream.Endpoint(payload_layout)

        # # #

        # Byte enables follow the same lane ordering as data, including optional byte swapping.
        if with_byteswap is None:
            with_byteswap = {"big": False, "little": True}.get(endianness, False)
        be = (sink.be[::-1] if with_byteswap else sink.be) if with_be else (1 << (bus.data_width//8)) - 1

        # Writes.
        self.comb += [
            bus.stb.eq(sink.valid),
            bus.cyc.eq(sink.valid),
            bus.we.eq(1),
            bus.sel.eq(be),
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
        """Add a controller with the same alignment/completion rules as the DMA reader.

        ``ready_on_idle`` retains the optional discard behavior while the controller is idle.
        """
        self._sink = self.sink
        payload_layout = [("data", self.bus.data_width)]
        if self.with_be:
            payload_layout += [("be", self.bus.data_width//8)]
        self.sink = stream.Endpoint(payload_layout)

        self.base   = Signal(64, reset=default_base)
        self.length = Signal(32, reset=default_length)
        self.enable = Signal(reset=default_enable)
        self.done   = Signal()
        self.error  = Signal()
        self.loop   = Signal(reset=default_loop)
        self.offset = Signal(32)

        # # #

        shift   = log2_int(self.bus.data_width//8)
        base    = Signal(self.bus.adr_width)
        offset  = Signal(self.bus.adr_width)
        length  = Signal(self.bus.adr_width)
        self.comb += base.eq(self.base[shift:])
        self.comb += length.eq(self.length[shift:])
        unaligned = (self.base[:shift] != 0) | (self.length[:shift] != 0) if shift else 0

        self.comb += self.offset.eq(offset)

        if self.with_be:
            self.comb += self._sink.be.eq(self.sink.be)

        self.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))
        self.comb += fsm.reset.eq(~self.enable)
        fsm.act("IDLE",
            self.sink.ready.eq(ready_on_idle),
            NextValue(offset, 0),
            If(self.length == 0,
                NextState("DONE"),
            ).Elif(unaligned,
                NextState("ERROR"),
            ).Else(
                NextState("RUN"),
            ),
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
        fsm.act("ERROR", self.done.eq(1), self.error.eq(1))

    def add_csr(self, default_base=0, default_length=0, default_enable=0, default_loop=0):
        if not hasattr(self, "base"):
            self.add_ctrl()
        self._base   = CSRStorage(64, reset=default_base,   description="DMA Writer base address.")
        self._length = CSRStorage(32, reset=default_length, description="DMA Writer transfer length in bytes.")
        self._enable = CSRStorage(reset=default_enable,     description="DMA Writer enable.")
        self._done   = CSRStatus(1,                         description="DMA Writer transfer done.")
        self._loop   = CSRStorage(reset=default_loop,       description="DMA Writer loop enable.")
        self._offset = CSRStatus(32,                        description="DMA Writer current transfer offset.")
        self._error  = CSRStatus(1, description="DMA Writer rejected a non-word-aligned base or length. Cleared when disabled.")

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
            self._error.status.eq(self.error),
        ]
