from migen.fhdl.std import *
from migen.flow.actor import *
from migen.flow.network import *
from migen.flow import plumbing
from migen.bank.description import CSRStorage, AutoCSR
from migen.actorlib import dma_lasmi, structuring, sim, misc

from misoclib.framebuffer.format import bpp, pixel_layout, FrameInitiator, VTG
from misoclib.framebuffer.phy import Driver

class Framebuffer(Module, AutoCSR):
	def __init__(self, pads_vga, pads_dvi, lasmim, simulation=False):
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

class Blender(PipelinedActor, AutoCSR):
	def __init__(self, nimages, pack_factor, latency):
		epixel_layout = pixel_layout(pack_factor)
		sink_layout = [("i"+str(i), epixel_layout) for i in range(nimages)]
		self.sink = Sink(sink_layout)
		self.source = Source(epixel_layout)
		factors = []
		for i in range(nimages):
			name = "f"+str(i)
			csr = CSRStorage(8, name=name)
			setattr(self, name, csr)
			factors.append(csr.storage)
		PipelinedActor.__init__(self, latency)

		###

		sink_registered = Record(sink_layout)
		self.sync += If(self.pipe_ce, sink_registered.eq(self.sink.payload))

		imgs = [getattr(sink_registered, "i"+str(i)) for i in range(nimages)]
		outval = Record(epixel_layout)
		for e in epixel_layout:
			name = e[0]
			inpixs = [getattr(img, name) for img in imgs]
			outpix = getattr(outval, name)
			for component in ["r", "g", "b"]:
				incomps = [getattr(pix, component) for pix in inpixs]
				outcomp = getattr(outpix, component)
				outcomp_full = Signal(19)
				self.comb += [
					outcomp_full.eq(sum(incomp*factor for incomp, factor in zip(incomps, factors))),
					If(outcomp_full[18],
						outcomp.eq(2**10 - 1) # saturate on overflow
					).Else(
						outcomp.eq(outcomp_full[8:18])
					)
				]

		pipe_stmts = []
		for i in range(latency-1):
			new_outval = Record(epixel_layout)
			pipe_stmts.append(new_outval.eq(outval))
			outval = new_outval
		self.sync += If(self.pipe_ce, pipe_stmts)
		self.comb += self.source.payload.eq(outval)

class MixFramebuffer(Module, AutoCSR):
	def __init__(self, pads_vga, pads_dvi, *lasmims, blender_latency=5):
		assert(all(lasmim.aw == lasmims[0].aw and lasmim.dw == lasmims[0].dw
			for lasmim in lasmims))
		pack_factor = lasmims[0].dw//bpp
		
		self.fi = FrameInitiator(lasmims[0].aw, pack_factor, len(lasmims))
		self.blender = Blender(len(lasmims), pack_factor, blender_latency)
		self.driver = Driver(pack_factor, pads_vga, pads_dvi)

		g = DataFlowGraph()
		epixel_layout = pixel_layout(pack_factor)
		for n, lasmim in enumerate(lasmims):
			intseq = misc.IntSequence(lasmim.aw, lasmim.aw)
			dma_out = AbstractActor(plumbing.Buffer)
			g.add_connection(self.fi, intseq, source_subr=self.fi.dma_subr(n))
			g.add_pipeline(intseq, AbstractActor(plumbing.Buffer), dma_lasmi.Reader(lasmim), dma_out)

			cast = structuring.Cast(lasmim.dw, epixel_layout, reverse_to=True)
			g.add_connection(dma_out, cast)
			g.add_connection(cast, self.blender, sink_subr=["i"+str(n)])

		vtg = VTG(pack_factor)
		g.add_connection(self.fi, vtg, source_subr=self.fi.timing_subr, sink_ep="timing")
		g.add_connection(self.blender, vtg, sink_ep="pixels")
		g.add_connection(vtg, self.driver)
		self.submodules += CompositeActor(g)
