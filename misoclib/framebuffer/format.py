from migen.fhdl.std import *
from migen.flow.actor import *
from migen.bank.description import CSRStorage
from migen.actorlib import spi

_hbits = 12
_vbits = 12

bpp = 32
bpc = 10
pixel_layout_s = [
	("pad", bpp-3*bpc),
	("r", bpc),
	("g", bpc),
	("b", bpc)
]
def pixel_layout(pack_factor):
	return [("p"+str(i), pixel_layout_s) for i in range(pack_factor)]

bpc_phy = 8
phy_layout_s = [
	("r", bpc_phy),
	("g", bpc_phy),
	("b", bpc_phy)
]
def phy_layout(pack_factor):
	r = [("hsync", 1), ("vsync", 1), ("de", 1)]
	for i in range(pack_factor):
		r.append(("p"+str(i), phy_layout_s))
	return r

class FrameInitiator(spi.SingleGenerator):
	def __init__(self, pack_factor):
		h_alignment_bits = log2_int(pack_factor)
		hbits_dyn = _hbits - h_alignment_bits
		layout = [
			("hres", hbits_dyn, 640, h_alignment_bits),
			("hsync_start", hbits_dyn, 656, h_alignment_bits),
			("hsync_end", hbits_dyn, 752, h_alignment_bits),
			("hscan", hbits_dyn, 800, h_alignment_bits),
			
			("vres", _vbits, 480),
			("vsync_start", _vbits, 492),
			("vsync_end", _vbits, 494),
			("vscan", _vbits, 525)
		]
		spi.SingleGenerator.__init__(self, layout, spi.MODE_EXTERNAL)

class VTG(Module):
	def __init__(self, pack_factor):
		hbits_dyn = _hbits - log2_int(pack_factor)
		self.enable = Signal()
		self.timing = Sink([
				("hres", hbits_dyn),
				("hsync_start", hbits_dyn),
				("hsync_end", hbits_dyn),
				("hscan", hbits_dyn),
				("vres", _vbits),
				("vsync_start", _vbits),
				("vsync_end", _vbits),
				("vscan", _vbits)])
		self.pixels = Sink(pixel_layout(pack_factor))
		self.phy = Source(phy_layout(pack_factor))
		self.busy = Signal()

		###

		hactive = Signal()
		vactive = Signal()
		active = Signal()
		
		generate_en = Signal()
		hcounter = Signal(hbits_dyn)
		vcounter = Signal(_vbits)
		
		skip = bpc - bpc_phy
		self.comb += [
			active.eq(hactive & vactive),
			If(active,
				[getattr(getattr(self.phy.payload, p), c).eq(getattr(getattr(self.pixels.payload, p), c)[skip:])
					for p in ["p"+str(i) for i in range(pack_factor)] for c in ["r", "g", "b"]],
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
