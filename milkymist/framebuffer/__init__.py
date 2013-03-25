from migen.fhdl.structure import *
from migen.fhdl.specials import Instance
from migen.fhdl.module import Module
from migen.flow.actor import *
from migen.flow.network import *
from migen.flow.transactions import *
from migen.flow import plumbing
from migen.actorlib import misc, dma_asmi, structuring, sim, spi

_hbits = 11
_vbits = 11

_bpp = 32
_bpc = 10
_pixel_layout = [
	("pad", _bpp-3*_bpc),
	("r", _bpc),
	("g", _bpc),
	("b", _bpc)
]

_bpc_dac = 8
_dac_layout = [
	("hsync", 1),
	("vsync", 1),
	("r", _bpc_dac),
	("g", _bpc_dac),
	("b", _bpc_dac)	
]

class _FrameInitiator(spi.SingleGenerator):
	def __init__(self, asmi_bits, length_bits, alignment_bits):
		layout = [
			("hres", _hbits, 640),
			("hsync_start", _hbits, 656),
			("hsync_end", _hbits, 752),
			("hscan", _hbits, 799),
			
			("vres", _vbits, 480),
			("vsync_start", _vbits, 492),
			("vsync_end", _vbits, 494),
			("vscan", _vbits, 524),
			
			("base", asmi_bits, 0, alignment_bits),
			("length", length_bits, 640*480*4, alignment_bits)
		]
		spi.SingleGenerator.__init__(self, layout, spi.MODE_CONTINUOUS)

class VTG(Module, Actor):
	def __init__(self):
		Actor.__init__(self,
			("timing", Sink, [
				("hres", _hbits),
				("hsync_start", _hbits),
				("hsync_end", _hbits),
				("hscan", _hbits),
				("vres", _vbits),
				("vsync_start", _vbits),
				("vsync_end", _vbits),
				("vscan", _vbits)]),
			("pixels", Sink, _pixel_layout),
			("dac", Source, _dac_layout)
		)

		hactive = Signal()
		vactive = Signal()
		active = Signal()
		
		generate_en = Signal()
		hcounter = Signal(_hbits)
		vcounter = Signal(_vbits)
		
		skip = _bpc - _bpc_dac
		self.comb += [
			active.eq(hactive & vactive),
			If(active,
				self.token("dac").r.eq(self.token("pixels").r[skip:]),
				self.token("dac").g.eq(self.token("pixels").g[skip:]),
				self.token("dac").b.eq(self.token("pixels").b[skip:])
			),
			
			generate_en.eq(self.endpoints["timing"].stb & (~active | self.endpoints["pixels"].stb)),
			self.endpoints["pixels"].ack.eq(self.endpoints["dac"].ack & active),
			self.endpoints["dac"].stb.eq(generate_en)
		]
		tp = self.token("timing")
		self.sync += [
			self.endpoints["timing"].ack.eq(0),
			If(generate_en & self.endpoints["dac"].ack,
				hcounter.eq(hcounter + 1),
			
				If(hcounter == 0, hactive.eq(1)),
				If(hcounter == tp.hres, hactive.eq(0)),
				If(hcounter == tp.hsync_start, self.token("dac").hsync.eq(1)),
				If(hcounter == tp.hsync_end, self.token("dac").hsync.eq(0)),
				If(hcounter == tp.hscan,
					hcounter.eq(0),
					If(vcounter == tp.vscan,
						vcounter.eq(0),
						self.endpoints["timing"].ack.eq(1)
					).Else(
						vcounter.eq(vcounter + 1)
					)
				),
				
				If(vcounter == 0, vactive.eq(1)),
				If(vcounter == tp.vres, vactive.eq(0)),
				If(vcounter == tp.vsync_start, self.token("dac").vsync.eq(1)),
				If(vcounter == tp.vsync_end, self.token("dac").vsync.eq(0))
			)
		]

class FIFO(Module, Actor):
	def __init__(self):
		Actor.__init__(self, ("dac", Sink, _dac_layout))
		
		self.vga_hsync_n = Signal()
		self.vga_vsync_n = Signal()
		self.vga_r = Signal(_bpc_dac)
		self.vga_g = Signal(_bpc_dac)
		self.vga_b = Signal(_bpc_dac)
	
		###

		data_width = 2+3*_bpc_dac
		fifo_full = Signal()
		fifo_write_en = Signal()
		fifo_data_out = Signal(data_width)
		fifo_data_in = Signal(data_width)
		self.specials += Instance("asfifo",
			Instance.Parameter("data_width", data_width),
			Instance.Parameter("address_width", 8),
	
			Instance.Output("data_out", fifo_data_out),
			Instance.Output("empty"),
			Instance.Input("read_en", 1),
			Instance.Input("clk_read", ClockSignal("vga")),

			Instance.Input("data_in", fifo_data_in),
			Instance.Output("full", fifo_full),
			Instance.Input("write_en", fifo_write_en),
			Instance.Input("clk_write", ClockSignal()),
			
			Instance.Input("rst", 0))
		t = self.token("dac")
		self.comb += [
			Cat(self.vga_hsync_n, self.vga_vsync_n, self.vga_r, self.vga_g, self.vga_b).eq(fifo_data_out),
			
			self.endpoints["dac"].ack.eq(~fifo_full),
			fifo_write_en.eq(self.endpoints["dac"].stb),
			fifo_data_in.eq(Cat(~t.hsync, ~t.vsync, t.r, t.g, t.b)),
			
			self.busy.eq(0)
		]

def sim_fifo_gen():
	while True:
		t = Token("dac")
		yield t
		print("H/V:" + str(t.value["hsync"]) + str(t.value["vsync"])
			+ " " + str(t.value["r"]) + " " + str(t.value["g"]) + " " + str(t.value["b"]))

class Framebuffer(Module):
	def __init__(self, asmiport, simulation=False):
		asmi_bits = asmiport.hub.aw
		alignment_bits = bits_for(asmiport.hub.dw//8) - 1
		length_bits = _hbits + _vbits + 2 - alignment_bits
		pack_factor = asmiport.hub.dw//_bpp
		packed_pixels = structuring.pack_layout(_pixel_layout, pack_factor)
		
		fi = _FrameInitiator(asmi_bits, length_bits, alignment_bits)
		adrloop = misc.IntSequence(length_bits, asmi_bits)
		adrbuffer = AbstractActor(plumbing.Buffer)
		dma = dma_asmi.Reader(asmiport)
		datbuffer = AbstractActor(plumbing.Buffer)
		cast = structuring.Cast(asmiport.hub.dw, packed_pixels, reverse_to=True)
		unpack = structuring.Unpack(pack_factor, _pixel_layout)
		vtg = VTG()
		if simulation:
			fifo = sim.SimActor(sim_fifo_gen(), ("dac", Sink, _dac_layout))
		else:
			fifo = FIFO()
		
		g = DataFlowGraph()
		g.add_connection(fi, adrloop, source_subr=["length", "base"])
		g.add_connection(adrloop, adrbuffer)
		g.add_connection(adrbuffer, dma)
		g.add_connection(dma, datbuffer)
		g.add_connection(datbuffer, cast)
		g.add_connection(cast, unpack)
		g.add_connection(unpack, vtg, sink_ep="pixels")
		g.add_connection(fi, vtg, sink_ep="timing", source_subr=[
			"hres", "hsync_start", "hsync_end", "hscan", 
			"vres", "vsync_start", "vsync_end", "vscan"])
		g.add_connection(vtg, fifo)
		self.submodules._comp_actor = CompositeActor(g, debugger=False)
		
		self._registers = fi.get_registers() + self._comp_actor.get_registers()
		
		# Pads
		self.vga_psave_n = Signal()
		if not simulation:
			self.vga_hsync_n = fifo.vga_hsync_n
			self.vga_vsync_n = fifo.vga_vsync_n
		self.vga_sync_n = Signal()
		self.vga_blank_n = Signal()
		if not simulation:
			self.vga_r = fifo.vga_r
			self.vga_g = fifo.vga_g
			self.vga_b = fifo.vga_b

		self.comb += [
			self.vga_sync_n.eq(0),
			self.vga_psave_n.eq(1),
			self.vga_blank_n.eq(1)
		]

	def get_registers(self):
		return self._registers
