from migen.fhdl.std import *
from migen.flow.actor import *
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

bpc_phy = 8
phy_layout_s = [
	("r", bpc_phy),
	("g", bpc_phy),
	("b", bpc_phy)
]
phy_layout = [
	("hsync", 1),
	("vsync", 1),
	("de", 1),
	("p0", phy_layout_s),
	("p1", phy_layout_s)
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
		self.enable = Signal()
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
		self.phy = Source(phy_layout)
		self.busy = Signal()

		###

		hactive = Signal()
		vactive = Signal()
		active = Signal()
		
		generate_en = Signal()
		hcounter = Signal(_hbits)
		vcounter = Signal(_vbits)
		
		skip = bpc - bpc_phy
		self.comb += [
			active.eq(hactive & vactive),
			If(active,
				[getattr(getattr(self.phy.payload, p), c).eq(getattr(getattr(self.pixels.payload, p), c)[skip:])
					for p in ["p0", "p1"] for c in ["r", "g", "b"]],
				self.phy.payload.de.eq(1)
			),
			
			generate_en.eq(self.timing.stb & (~active | self.pixels.stb)),
			self.pixels.ack.eq(~self.enable | (self.phy.ack & active)),
			self.phy.stb.eq(generate_en),
			self.busy.eq(generate_en)
		]
		tp = self.timing.payload
		self.sync += [
			If(self.enable,
				self.timing.ack.eq(0),
				If(generate_en & self.phy.ack,
					hcounter.eq(hcounter + 1),
				
					If(hcounter == 0, hactive.eq(1)),
					If(hcounter == tp.hres, hactive.eq(0)),
					If(hcounter == tp.hsync_start, self.phy.payload.hsync.eq(1)),
					If(hcounter == tp.hsync_end, self.phy.payload.hsync.eq(0)),
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
					If(vcounter == tp.vsync_start, self.phy.payload.vsync.eq(1)),
					If(vcounter == tp.vsync_end, self.phy.payload.vsync.eq(0))
				)
			).Else(
				self.timing.ack.eq(1),
				hcounter.eq(0),
				vcounter.eq(0)
			)
		]
