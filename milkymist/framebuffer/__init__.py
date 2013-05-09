from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.flow.network import *
from migen.bank.description import CSRStorage
from migen.actorlib import dma_asmi, structuring, sim, spi

from milkymist.framebuffer.lib import bpp, pixel_layout, dac_layout, FrameInitiator, VTG, FIFO

class Framebuffer(Module):
	def __init__(self, pads, asmiport, simulation=False):
		pack_factor = asmiport.hub.dw//(2*bpp)
		packed_pixels = structuring.pack_layout(pixel_layout, pack_factor)
		
		fi = FrameInitiator()
		dma = spi.DMAReadController(dma_asmi.Reader(asmiport), spi.MODE_EXTERNAL, length_reset=640*480*4)
		cast = structuring.Cast(asmiport.hub.dw, packed_pixels, reverse_to=True)
		unpack = structuring.Unpack(pack_factor, pixel_layout)
		vtg = VTG()
		if simulation:
			fifo = sim.SimActor(sim_fifo_gen(), ("dac", Sink, dac_layout))
		else:
			fifo = FIFO()
		
		g = DataFlowGraph()
		g.add_connection(fi, vtg, sink_ep="timing")
		g.add_connection(dma, cast)
		g.add_connection(cast, unpack)
		g.add_connection(unpack, vtg, sink_ep="pixels")
		g.add_connection(vtg, fifo)
		self.submodules += CompositeActor(g)

		self._enable = CSRStorage()
		self.comb += [
			fi.trigger.eq(self._enable.storage),
			dma.generator.trigger.eq(self._enable.storage),
		]
		self._fi = fi
		self._dma = dma
		
		# Drive pads
		if not simulation:
			self.comb += [
				pads.hsync_n.eq(fifo.vga_hsync_n),
				pads.vsync_n.eq(fifo.vga_vsync_n),
				pads.r.eq(fifo.vga_r),
				pads.g.eq(fifo.vga_g),
				pads.b.eq(fifo.vga_b)
			]
		self.comb += pads.psave_n.eq(1)

	def get_csrs(self):
		return [self._enable] + self._fi.get_csrs() + self._dma.get_csrs()
