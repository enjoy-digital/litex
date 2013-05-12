from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.genlib.record import Record
from migen.genlib.fifo import AsyncFIFO
from migen.flow.actor import *
from migen.flow.network import *
from migen.flow.transactions import *
from migen.bank.description import CSRStorage
from migen.actorlib import spi

_hbits = 11
_vbits = 12

bpp = 32
bpc = 10
pixel_layout_s = [
	("pad", bpp-3*bpc),
	("r", bpc),
	("g", bpc),
	("b", bpc)
]
pixel_layout = [
	("p0", pixel_layout_s),
	("p1", pixel_layout_s)
]

bpc_dac = 8
dac_layout_s = [
	("r", bpc_dac),
	("g", bpc_dac),
	("b", bpc_dac)
]
dac_layout = [
	("hsync", 1),
	("vsync", 1),
	("p0", dac_layout_s),
	("p1", dac_layout_s)
]

class FrameInitiator(spi.SingleGenerator):
	def __init__(self):
		layout = [
			("hres", _hbits, 640, 1),
			("hsync_start", _hbits, 656, 1),
			("hsync_end", _hbits, 752, 1),
			("hscan", _hbits, 800, 1),
			
			("vres", _vbits, 480),
			("vsync_start", _vbits, 492),
			("vsync_end", _vbits, 494),
			("vscan", _vbits, 525)
		]
		spi.SingleGenerator.__init__(self, layout, spi.MODE_EXTERNAL)

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
		self.pixels = Sink(pixel_layout)
		self.dac = Source(dac_layout)
		self.busy = Signal()

		hactive = Signal()
		vactive = Signal()
		active = Signal()
		
		generate_en = Signal()
		hcounter = Signal(_hbits)
		vcounter = Signal(_vbits)
		
		skip = bpc - bpc_dac
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
		self.dac = Sink(dac_layout)
		self.busy = Signal()
		
		self.vga_hsync_n = Signal()
		self.vga_vsync_n = Signal()
		self.vga_r = Signal(bpc_dac)
		self.vga_g = Signal(bpc_dac)
		self.vga_b = Signal(bpc_dac)
	
		###

		data_width = 2+2*3*bpc_dac
		fifo = AsyncFIFO(data_width, 512)
		self.add_submodule(fifo, {"write": "sys", "read": "vga"})
		fifo_in = self.dac.payload
		fifo_out = Record(dac_layout)
		self.comb += [
			self.dac.ack.eq(fifo.writable),
			fifo.we.eq(self.dac.stb),
			fifo.din.eq(fifo_in.raw_bits()),
			fifo_out.raw_bits().eq(fifo.dout),
			self.busy.eq(0)
		]

		pix_parity = Signal()
		self.sync.vga += [
			pix_parity.eq(~pix_parity),
			self.vga_hsync_n.eq(~fifo_out.hsync),
			self.vga_vsync_n.eq(~fifo_out.vsync),
			If(pix_parity,
				# FIXME: p0/p1 should be the other way around. Clarify this.
				self.vga_r.eq(fifo_out.p0.r),
				self.vga_g.eq(fifo_out.p0.g),
				self.vga_b.eq(fifo_out.p0.b)
			).Else(
				self.vga_r.eq(fifo_out.p1.r),
				self.vga_g.eq(fifo_out.p1.g),
				self.vga_b.eq(fifo_out.p1.b)
			)
		]
		self.comb += fifo.re.eq(pix_parity)

def sim_fifo_gen():
	while True:
		t = Token("dac")
		yield t
		print("H/V:" + str(t.value["hsync"]) + str(t.value["vsync"])
			+ " " + str(t.value["r"]) + " " + str(t.value["g"]) + " " + str(t.value["b"]))
