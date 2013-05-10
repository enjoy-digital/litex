from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.flow.actor import *
from migen.flow.network import *
from migen.bank.description import CSRStorage, AutoCSR
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

class Blender(PipelinedActor, AutoCSR):
	def __init__(self, nimages, latency):
		self.sink = Sink([("i"+str(i), pixel_layout) for i in range(nimages)])
		self.source = Source(pixel_layout)
		factors = []
		for i in range(nimages):
			name = "f"+str(i)
			csr = CSRStorage(8, name=name)
			setattr(self, name, csr)
			factors.append(csr.storage)
		PipelinedActor.__init__(self, latency)

		###

		imgs = [getattr(self.sink.payload, "i"+str(i)) for i in range(nimages)]
		outval = Record(pixel_layout)
		for e in pixel_layout:
			name = e[0]
			inpixs = [getattr(img, name) for img in imgs]
			outpix = getattr(outval, name)
			for component in ["r", "g", "b"]:
				incomps = [getattr(pix, component) for pix in inpixs]
				outcomp = getattr(outpix, component)
				self.comb += outcomp.eq(sum(incomp*factor for incomp, factor in zip(incomps, factors)) >> 8)

		pipe_stmts = []
		for i in range(latency):
			new_outval = Record(pixel_layout)
			pipe_stmts.append(new_outval.eq(outval))
			outval = new_outval
		self.sync += If(self.pipe_ce, pipe_stmts)
		self.comb += self.source.payload.eq(outval)

class MixFramebuffer(Module, AutoCSR):
	def __init__(self, pads, *asmiports, blender_latency=3):
		pack_factor = asmiports[0].hub.dw//(2*bpp)
		packed_pixels = structuring.pack_layout(pixel_layout, pack_factor)
		
		self._enable = CSRStorage()
		self.fi = FrameInitiator()
		self.blender = Blender(len(asmiports), blender_latency)
		self.comb += self.fi.trigger.eq(self._enable.storage)

		g = DataFlowGraph()
		for n, asmiport in enumerate(asmiports):
			dma = spi.DMAReadController(dma_asmi.Reader(asmiport), spi.MODE_EXTERNAL, length_reset=640*480*4)
			cast = structuring.Cast(asmiport.hub.dw, packed_pixels, reverse_to=True)
			unpack = structuring.Unpack(pack_factor, pixel_layout)

			g.add_connection(dma, cast)
			g.add_connection(cast, unpack)
			g.add_connection(unpack, self.blender, sink_subr=["i"+str(n)+"/p0", "i"+str(n)+"/p1"])

			self.comb += dma.generator.trigger.eq(self._enable.storage)
			setattr(self, "dma"+str(n), dma)

		vtg = VTG()
		fifo = FIFO()
		g.add_connection(self.fi, vtg, sink_ep="timing")
		g.add_connection(self.blender, vtg, sink_ep="pixels")
		g.add_connection(vtg, fifo)
		self.submodules += CompositeActor(g)
		
		self.comb += [
			pads.hsync_n.eq(fifo.vga_hsync_n),
			pads.vsync_n.eq(fifo.vga_vsync_n),
			pads.r.eq(fifo.vga_r),
			pads.g.eq(fifo.vga_g),
			pads.b.eq(fifo.vga_b),
			pads.psave_n.eq(1)
		]
	