from migen.fhdl.structure import *
from migen.fhdl.specials import Instance
from migen.fhdl.module import Module
from migen.genlib.record import Record
from migen.flow.actor import *
from migen.flow.network import *
from migen.flow.transactions import *
from migen.flow import plumbing
from migen.actorlib import misc, dma_asmi, structuring, sim, spi

_hbits = 11
_vbits = 12

_bpp = 32
_bpc = 10
_pixel_layout_s = [
	("pad", _bpp-3*_bpc),
	("r", _bpc),
	("g", _bpc),
	("b", _bpc)
]
_pixel_layout = [
	("p0", _pixel_layout_s),
	("p1", _pixel_layout_s)
]

_bpc_dac = 8
_dac_layout_s = [
	("r", _bpc_dac),
	("g", _bpc_dac),
	("b", _bpc_dac)
]
_dac_layout = [
	("hsync", 1),
	("vsync", 1),
	("p0", _dac_layout_s),
	("p1", _dac_layout_s)
]

class _FrameInitiator(spi.SingleGenerator):
	def __init__(self, asmi_bits, length_bits, alignment_bits):
		layout = [
			("hres", _hbits, 640, 1),
			("hsync_start", _hbits, 656, 1),
			("hsync_end", _hbits, 752, 1),
			("hscan", _hbits, 800, 1),
			
			("vres", _vbits, 480),
			("vsync_start", _vbits, 492),
			("vsync_end", _vbits, 494),
			("vscan", _vbits, 525),
			
			("base", asmi_bits, 0, alignment_bits),
			("length", length_bits, 640*480*4, alignment_bits)
		]
		spi.SingleGenerator.__init__(self, layout, spi.MODE_CONTINUOUS)

class VTG(Module):
	def __init__(self):
		self.timing = Sink([
				("hres", _hbits),
				("hsync_start", _hbits),
				("hsync_end", _hbits),
				("hscan", _hbits),
				("vres", _vbits),
				("vsync_start", _vbits),
				("vsync_end", _vbits),
				("vscan", _vbits)])
		self.pixels = Sink(_pixel_layout)
		self.dac = Source(_dac_layout)
		self.busy = Signal()

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
				[getattr(getattr(self.dac.payload, p), c).eq(getattr(getattr(self.pixels.payload, p), c)[skip:])
					for p in ["p0", "p1"] for c in ["r", "g", "b"]]
			),
			
			generate_en.eq(self.timing.stb & (~active | self.pixels.stb)),
			self.pixels.ack.eq(self.dac.ack & active),
			self.dac.stb.eq(generate_en),
			self.busy.eq(generate_en)
		]
		tp = self.timing.payload
		self.sync += [
			self.timing.ack.eq(0),
			If(generate_en & self.dac.ack,
				hcounter.eq(hcounter + 1),
			
				If(hcounter == 0, hactive.eq(1)),
				If(hcounter == tp.hres, hactive.eq(0)),
				If(hcounter == tp.hsync_start, self.dac.payload.hsync.eq(1)),
				If(hcounter == tp.hsync_end, self.dac.payload.hsync.eq(0)),
				If(hcounter == tp.hscan,
					hcounter.eq(0),
					If(vcounter == tp.vscan,
						vcounter.eq(0),
						self.timing.ack.eq(1)
					).Else(
						vcounter.eq(vcounter + 1)
					)
				),
				
				If(vcounter == 0, vactive.eq(1)),
				If(vcounter == tp.vres, vactive.eq(0)),
				If(vcounter == tp.vsync_start, self.dac.payload.vsync.eq(1)),
				If(vcounter == tp.vsync_end, self.dac.payload.vsync.eq(0))
			)
		]

class FIFO(Module):
	def __init__(self):
		self.dac = Sink(_dac_layout)
		self.busy = Signal()
		
		self.vga_hsync_n = Signal()
		self.vga_vsync_n = Signal()
		self.vga_r = Signal(_bpc_dac)
		self.vga_g = Signal(_bpc_dac)
		self.vga_b = Signal(_bpc_dac)
	
		###

		data_width = 2+2*3*_bpc_dac
		fifo_full = Signal()
		fifo_write_en = Signal()
		fifo_read_en = Signal()
		fifo_data_out = Signal(data_width)
		fifo_data_in = Signal(data_width)
		self.specials += Instance("asfifo",
			Instance.Parameter("data_width", data_width),
			Instance.Parameter("address_width", 8),
	
			Instance.Output("data_out", fifo_data_out),
			Instance.Output("empty"),
			Instance.Input("read_en", fifo_read_en),
			Instance.Input("clk_read", ClockSignal("vga")),

			Instance.Input("data_in", fifo_data_in),
			Instance.Output("full", fifo_full),
			Instance.Input("write_en", fifo_write_en),
			Instance.Input("clk_write", ClockSignal()),
			
			Instance.Input("rst", 0))
		fifo_in = self.dac.payload
		fifo_out = Record(_dac_layout)
		self.comb += [
			self.dac.ack.eq(~fifo_full),
			fifo_write_en.eq(self.dac.stb),
			fifo_data_in.eq(fifo_in.raw_bits()),
			fifo_out.raw_bits().eq(fifo_data_out),
			self.busy.eq(0)
		]

		pix_parity = Signal()
		self.sync.vga += [
			pix_parity.eq(~pix_parity),
			self.vga_hsync_n.eq(~fifo_out.hsync),
			self.vga_vsync_n.eq(~fifo_out.vsync),
			If(pix_parity,
				self.vga_r.eq(fifo_out.p1.r),
				self.vga_g.eq(fifo_out.p1.g),
				self.vga_b.eq(fifo_out.p1.b)
			).Else(
				self.vga_r.eq(fifo_out.p0.r),
				self.vga_g.eq(fifo_out.p0.g),
				self.vga_b.eq(fifo_out.p0.b)
			)
		]
		self.comb += fifo_read_en.eq(pix_parity)

def sim_fifo_gen():
	while True:
		t = Token("dac")
		yield t
		print("H/V:" + str(t.value["hsync"]) + str(t.value["vsync"])
			+ " " + str(t.value["r"]) + " " + str(t.value["g"]) + " " + str(t.value["b"]))

class Framebuffer(Module):
	def __init__(self, pads, asmiport, simulation=False):
		asmi_bits = asmiport.hub.aw
		alignment_bits = bits_for(asmiport.hub.dw//8) - 1
		length_bits = _hbits + _vbits + 2 - alignment_bits
		pack_factor = asmiport.hub.dw//(2*_bpp)
		packed_pixels = structuring.pack_layout(_pixel_layout, pack_factor)
		
		self._fi = fi = _FrameInitiator(asmi_bits, length_bits, alignment_bits)
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
		self.submodules._comp_actor = CompositeActor(g)
		
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
		return self._fi.get_csrs()
