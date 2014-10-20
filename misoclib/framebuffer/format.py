from migen.fhdl.std import *
from migen.flow.actor import *
from migen.bank.description import CSRStorage
from migen.genlib.record import Record
from migen.genlib.fsm import FSM, NextState
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
	def __init__(self, bus_aw, pack_factor, ndmas=1):
		h_alignment_bits = log2_int(pack_factor)
		hbits_dyn = _hbits - h_alignment_bits
		bus_alignment_bits = h_alignment_bits + log2_int(bpp//8)
		layout = [
			("hres", hbits_dyn, 640, h_alignment_bits),
			("hsync_start", hbits_dyn, 656, h_alignment_bits),
			("hsync_end", hbits_dyn, 752, h_alignment_bits),
			("hscan", hbits_dyn, 800, h_alignment_bits),

			("vres", _vbits, 480),
			("vsync_start", _vbits, 492),
			("vsync_end", _vbits, 494),
			("vscan", _vbits, 525),

			("length", bus_aw + bus_alignment_bits, 640*480*bpp//8, bus_alignment_bits)
		]
		layout += [("base"+str(i), bus_aw + bus_alignment_bits, 0, bus_alignment_bits)
			for i in range(ndmas)]
		spi.SingleGenerator.__init__(self, layout, spi.MODE_CONTINUOUS)

	timing_subr = ["hres", "hsync_start", "hsync_end", "hscan",
		"vres", "vsync_start", "vsync_end", "vscan"]

	def dma_subr(self, i=0):
		return ["length", "base"+str(i)]

class VTG(Module):
	def __init__(self, pack_factor):
		hbits_dyn = _hbits - log2_int(pack_factor)
		timing_layout = [
			("hres", hbits_dyn),
			("hsync_start", hbits_dyn),
			("hsync_end", hbits_dyn),
			("hscan", hbits_dyn),
			("vres", _vbits),
			("vsync_start", _vbits),
			("vsync_end", _vbits),
			("vscan", _vbits)]
		self.timing = Sink(timing_layout)
		self.pixels = Sink(pixel_layout(pack_factor))
		self.phy = Source(phy_layout(pack_factor))
		self.busy = Signal()

		###

		hactive = Signal()
		vactive = Signal()
		active = Signal()

		hcounter = Signal(hbits_dyn)
		vcounter = Signal(_vbits)

		skip = bpc - bpc_phy
		self.comb += [
			active.eq(hactive & vactive),
			If(active,
				[getattr(getattr(self.phy.payload, p), c).eq(getattr(getattr(self.pixels.payload, p), c)[skip:])
					for p in ["p"+str(i) for i in range(pack_factor)] for c in ["r", "g", "b"]],
				self.phy.de.eq(1)
			),
			self.pixels.ack.eq(self.phy.ack & active)
		]

		load_timing = Signal()
		tr = Record(timing_layout)
		self.sync += If(load_timing, tr.eq(self.timing.payload))

		generate_en = Signal()
		generate_frame_done = Signal()
		self.sync += [
			generate_frame_done.eq(0),
			If(generate_en,
				hcounter.eq(hcounter + 1),

				If(hcounter == 0, hactive.eq(1)),
				If(hcounter == tr.hres, hactive.eq(0)),
				If(hcounter == tr.hsync_start, self.phy.hsync.eq(1)),
				If(hcounter == tr.hsync_end, self.phy.hsync.eq(0)),
				If(hcounter == tr.hscan,
					hcounter.eq(0),
					If(vcounter == tr.vscan,
						vcounter.eq(0),
						generate_frame_done.eq(1)
					).Else(
						vcounter.eq(vcounter + 1)
					)
				),

				If(vcounter == 0, vactive.eq(1)),
				If(vcounter == tr.vres, vactive.eq(0)),
				If(vcounter == tr.vsync_start, self.phy.vsync.eq(1)),
				If(vcounter == tr.vsync_end, self.phy.vsync.eq(0))
			)
		]

		self.submodules.fsm = FSM()
		self.fsm.act("GET_TIMING",
			self.timing.ack.eq(1),
			load_timing.eq(1),
			If(self.timing.stb, NextState("GENERATE"))
		)
		self.fsm.act("GENERATE",
			self.busy.eq(1),
			If(~active | self.pixels.stb,
				self.phy.stb.eq(1),
				If(self.phy.ack, generate_en.eq(1))
			),
			If(generate_frame_done,	NextState("GET_TIMING"))
		)
