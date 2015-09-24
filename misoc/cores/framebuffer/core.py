from migen import *
from migen.flow.network import *
from migen.flow import plumbing
from migen.bank.description import AutoCSR
from migen.actorlib import structuring, misc

from misoc.mem.sdram.frontend import dma_lasmi
from misoc.framebuffer.format import bpp, pixel_layout, FrameInitiator, VTG
from misoc.framebuffer.phy import Driver


class Framebuffer(Module, AutoCSR):
    def __init__(self, pads_vga, pads_dvi, lasmim):
        pack_factor = lasmim.dw//bpp

        g = DataFlowGraph()

        self.fi = FrameInitiator(lasmim.aw, pack_factor)

        intseq = misc.IntSequence(lasmim.aw, lasmim.aw)
        dma_out = AbstractActor(plumbing.Buffer)
        g.add_connection(self.fi, intseq, source_subr=self.fi.dma_subr())
        g.add_pipeline(intseq, AbstractActor(plumbing.Buffer), dma_lasmi.Reader(lasmim), dma_out)

        cast = structuring.Cast(lasmim.dw, pixel_layout(pack_factor), reverse_to=True)
        vtg = VTG(pack_factor)
        self.driver = Driver(pack_factor, pads_vga, pads_dvi)

        g.add_connection(self.fi, vtg, source_subr=self.fi.timing_subr, sink_ep="timing")
        g.add_connection(dma_out, cast)
        g.add_connection(cast, vtg, sink_ep="pixels")
        g.add_connection(vtg, self.driver)
        self.submodules += CompositeActor(g)
