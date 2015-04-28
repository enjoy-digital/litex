from migen.fhdl.std import *
from migen.flow.actor import *
from migen.flow.network import *
from migen.actorlib import structuring, spi
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.genlib.record import Record

from misoclib.mem.sdram.frontend import dma_lasmi
from misoclib.com.liteusb.common import *


class LiteUSBDMAWriter(Module, AutoCSR):
    def __init__(self, lasmim):
        self.sink = sink = Sink(user_description(8))

        # Pack data
        pack_factor = lasmim.dw//8
        pack = structuring.Pack(phy_layout, pack_factor, reverse=True)
        cast = structuring.Cast(pack.source.payload.layout, lasmim.dw)

        # DMA
        writer = dma_lasmi.Writer(lasmim)
        self._reset = CSR()
        self.dma = InsertReset(spi.DMAWriteController(writer, mode=spi.MODE_SINGLE_SHOT))
        self.comb += self.dma.reset.eq(self._reset.r & self._reset.re)

        # Remove sop/eop/length/dst fields from payload
        self.comb += [
            pack.sink.stb.eq(sink.stb),
            pack.sink.payload.eq(sink.payload),
            sink.ack.eq(pack.sink.ack)
        ]

        # Graph
        g = DataFlowGraph()
        g.add_pipeline(pack, cast, self.dma)
        self.submodules += CompositeActor(g)

        # IRQ
        self.submodules.ev = EventManager()
        self.ev.done = EventSourcePulse()
        self.ev.finalize()
        self.comb += self.ev.done.trigger.eq(sink.stb & sink.eop)

        # CRC
        self._crc_failed = CSRStatus()
        self.sync += \
            If(sink.stb & sink.eop,
                self._crc_failed.status.eq(sink.error)
            )


class LiteUSBDMAReader(Module, AutoCSR):
    def __init__(self, lasmim, tag):
        self.source = source = Source(user_description(8))

        reader = dma_lasmi.Reader(lasmim)
        self.dma = spi.DMAReadController(reader, mode=spi.MODE_SINGLE_SHOT)

        pack_factor = lasmim.dw//8
        packed_dat = structuring.pack_layout(8, pack_factor)
        cast = structuring.Cast(lasmim.dw, packed_dat)
        unpack = structuring.Unpack(pack_factor, phy_layout, reverse=True)

        # Graph
        cnt = Signal(32)
        self.sync += \
            If(self.dma.generator._r_shoot.re,
                cnt.eq(0)
            ).Elif(source.stb & source.ack,
                cnt.eq(cnt + 1)
            )
        g = DataFlowGraph()
        g.add_pipeline(self.dma, cast, unpack)
        self.submodules += CompositeActor(g)
        self.comb += [
            source.stb.eq(unpack.source.stb),
            source.sop.eq(cnt == 0),
            source.eop.eq(cnt == (self.dma.length*pack_factor-1)),
            source.length.eq(self.dma.length*pack_factor+4),
            source.data.eq(unpack.source.data),
            source.dst.eq(tag),
            unpack.source.ack.eq(source.ack)
        ]

        # IRQ
        self.submodules.ev = EventManager()
        self.ev.done = EventSourcePulse()
        self.ev.finalize()
        self.comb += self.ev.done.trigger.eq(source.stb & source.eop)


class LiteUSBDMA(Module, AutoCSR):
    def __init__(self, lasmim_dma_wr, lasmim_dma_rd, tag):
        self.tag = tag

        self.submodules.writer = LiteUSBDMAWriter(lasmim_dma_wr)
        self.submodules.reader = LiteUSBDMAReader(lasmim_dma_rd, self.tag)
        self.submodules.ev = SharedIRQ(self.writer.ev, self.reader.ev)

        self.sink = self.writer.sink
        self.source = self.reader.source
