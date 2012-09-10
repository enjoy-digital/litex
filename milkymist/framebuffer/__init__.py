from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.flow.network import *
from migen.flow import plumbing
from migen.actorlib import misc, dma_asmi, structuring, sim
from migen.bank.description import *
from migen.bank import csrgen

_hbits = 11
_vbits = 11

_bpp = 32
_bpc = 10
_pixel_layout = [
	("b", BV(_bpc)),
	("g", BV(_bpc)),
	("r", BV(_bpc)),
	("pad", BV(_bpp-3*_bpc))
]

_bpc_dac = 8
_dac_layout = [
	("hsync", BV(1)),
	("vsync", BV(1)),
	("b", BV(_bpc_dac)),
	("g", BV(_bpc_dac)),
	("r", BV(_bpc_dac))
]

class _FrameInitiator(Actor):
	def __init__(self, asmi_bits, length_bits, alignment_bits):
		self._alignment_bits = alignment_bits
		
		self._enable = RegisterField("enable")
		
		self._hres = RegisterField("hres", _hbits, reset=640)
		self._hsync_start = RegisterField("hsync_start", _hbits, reset=656)
		self._hsync_end = RegisterField("hsync_end", _hbits, reset=752)
		self._hscan = RegisterField("hscan", _hbits, reset=799)
		
		self._vres = RegisterField("vres", _vbits, reset=480)
		self._vsync_start = RegisterField("vsync_start", _vbits, reset=492)
		self._vsync_end = RegisterField("vsync_end", _vbits, reset=494)
		self._vscan = RegisterField("vscan", _vbits, reset=524)
		
		self._base = RegisterField("base", asmi_bits + self._alignment_bits)
		self._length = RegisterField("length", length_bits + self._alignment_bits, reset=640*480*4)
		
		layout = [
			("hres", BV(_hbits)),
			("hsync_start", BV(_hbits)),
			("hsync_end", BV(_hbits)),
			("hscan", BV(_hbits)),
			("vres", BV(_vbits)),
			("vsync_start", BV(_vbits)),
			("vsync_end", BV(_vbits)),
			("vscan", BV(_vbits)),
			("base", BV(asmi_bits)),
			("length", BV(length_bits))
		]
		super().__init__(("frame", Source, layout))
		
	def get_registers(self):
		return [self._enable,
			self._hres, self._hsync_start, self._hsync_end, self._hscan,
			self._vres, self._vsync_start, self._vsync_end, self._vscan,
			self._base, self._length]
		
	def get_fragment(self):
		# TODO: make address updates atomic
		token = self.token("frame")
		stb = self.endpoints["frame"].stb
		ack = self.endpoints["frame"].ack
		comb = [
			self.busy.eq(stb),
			token.hres.eq(self._hres.field.r),
			token.hsync_start.eq(self._hsync_start.field.r),
			token.hsync_end.eq(self._hsync_end.field.r),
			token.hscan.eq(self._hscan.field.r),
			token.vres.eq(self._vres.field.r),
			token.vsync_start.eq(self._vsync_start.field.r),
			token.vsync_end.eq(self._vsync_end.field.r),
			token.vscan.eq(self._vscan.field.r),
			token.length.eq(self._length.field.r[self._alignment_bits:])
		]
		sync = [
			If(ack | ~stb,
				stb.eq(self._enable.field.r),
				token.base.eq(self._base.field.r[self._alignment_bits:])
			)
		]
		return Fragment(comb, sync)

class VTG(Actor):
	def __init__(self):
		super().__init__(
			("timing", Sink, [
				("hres", BV(_hbits)),
				("hsync_start", BV(_hbits)),
				("hsync_end", BV(_hbits)),
				("hscan", BV(_hbits)),
				("vres", BV(_vbits)),
				("vsync_start", BV(_vbits)),
				("vsync_end", BV(_vbits)),
				("vscan", BV(_vbits))]),
			("pixels", Sink, _pixel_layout),
			("dac", Source, _dac_layout)
		)
	
	def get_fragment(self):
		hactive = Signal()
		vactive = Signal()
		active = Signal()
		
		generate_en = Signal()
		hcounter = Signal(BV(_hbits))
		vcounter = Signal(BV(_vbits))
		
		skip = _bpc - _bpc_dac
		comb = [
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
		sync = [
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
		
		return Fragment(comb, sync)

class FIFO(Actor):
	def __init__(self):
		super().__init__(("dac", Sink, _dac_layout))
		
		self.vga_clk = Signal()
		self.vga_hsync_n = Signal()
		self.vga_vsync_n = Signal()
		self.vga_r = Signal(BV(_bpc_dac))
		self.vga_g = Signal(BV(_bpc_dac))
		self.vga_b = Signal(BV(_bpc_dac))
	
	def get_fragment(self):
		data_width = 2+3*_bpc_dac
		asfifo = Instance("asfifo",
			Instance.Parameter("data_width", data_width),
			Instance.Parameter("address_width", 8),
	
			Instance.Output("data_out", BV(data_width)),
			Instance.Output("empty", BV(1)),
			Instance.Input("read_en", BV(1)),
			Instance.Input("clk_read", self.vga_clk),

			Instance.Input("data_in", BV(data_width)),
			Instance.Output("full", BV(1)),
			Instance.Input("write_en", BV(1)),
			Instance.ClockPort("clk_write"),
			
			Instance.Input("rst", BV(1)))
		t = self.token("dac")
		return Fragment(
			[
				asfifo.get_io("read_en").eq(1),
				Cat(self.vga_hsync_n, self.vga_vsync_n, self.vga_r, self.vga_g, self.vga_b).eq(asfifo.get_io("data_out")),
				
				self.endpoints["dac"].ack.eq(~asfifo.get_io("full")),
				asfifo.get_io("write_en").eq(self.endpoints["dac"].stb),
				asfifo.get_io("data_in").eq(Cat(~t.hsync, ~t.vsync, t.r, t.g, t.b)),
				
				self.busy.eq(0),
				asfifo.get_io("rst").eq(0)
			],
			instances=[asfifo])

def sim_fifo_gen():
	while True:
		t = sim.Token("dac")
		yield t
		print("H/V:" + str(t.value["hsync"]) + str(t.value["vsync"])
			+ " " + str(t.value["r"]) + " " + str(t.value["g"]) + " " + str(t.value["b"]))


class Framebuffer:
	def __init__(self, address, asmiport, simulation=False):
		asmi_bits = asmiport.hub.aw
		alignment_bits = bits_for(asmiport.hub.dw//8) - 1
		length_bits = _hbits + _vbits + 2 - alignment_bits
		pack_factor = asmiport.hub.dw//_bpp
		packed_pixels = structuring.pack_layout(_pixel_layout, pack_factor)
		
		fi = ActorNode(_FrameInitiator(asmi_bits, length_bits, alignment_bits))
		adrloop = ActorNode(misc.IntSequence(length_bits, asmi_bits))
		adrbuffer = ActorNode(plumbing.Buffer)
		dma = ActorNode(dma_asmi.Reader(asmiport))
		datbuffer = ActorNode(plumbing.Buffer)
		cast = ActorNode(structuring.Cast(asmiport.hub.dw, packed_pixels))
		unpack = ActorNode(structuring.Unpack(pack_factor, _pixel_layout))
		vtg = ActorNode(VTG())
		if simulation:
			fifo = ActorNode(sim.SimActor(sim_fifo_gen(), ("dac", Sink, _dac_layout)))
		else:
			fifo = ActorNode(FIFO())
		
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
		self._comp_actor = CompositeActor(g, debugger=False)
		
		self.bank = csrgen.Bank(fi.actor.get_registers() + self._comp_actor.get_registers(),
			address=address)
		
		# VGA clock input
		if not simulation:
			self.vga_clk = fifo.actor.vga_clk
		
		# Pads
		self.vga_psave_n = Signal()
		if not simulation:
			self.vga_hsync_n = fifo.actor.vga_hsync_n
			self.vga_vsync_n = fifo.actor.vga_vsync_n
		self.vga_sync_n = Signal()
		self.vga_blank_n = Signal()
		if not simulation:
			self.vga_r = fifo.actor.vga_r
			self.vga_g = fifo.actor.vga_g
			self.vga_b = fifo.actor.vga_b

	def get_fragment(self):
		comb = [
			self.vga_sync_n.eq(0),
			self.vga_psave_n.eq(1),
			self.vga_blank_n.eq(1)
		]
		return self.bank.get_fragment() \
			+ self._comp_actor.get_fragment() \
			+ Fragment(comb)
