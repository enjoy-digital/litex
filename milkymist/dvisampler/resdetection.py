from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.genlib.cdc import MultiReg
from migen.bank.description import *

class ResolutionDetection(Module, AutoReg):
	def __init__(self, nbits=10):
		self.hsync = Signal()
		self.vsync = Signal()
		self.de = Signal()

		self._hres = RegisterField(nbits, READ_ONLY, WRITE_ONLY)
		self._vres = RegisterField(nbits, READ_ONLY, WRITE_ONLY)
		self._de_cycles = RegisterField(2*nbits, READ_ONLY, WRITE_ONLY)

		###

		# HRES/VRES
		hsync_r = Signal()
		vsync_r = Signal()
		p_hsync = Signal()
		p_vsync = Signal()
		self.sync.pix += [
			hsync_r.eq(self.hsync),
			vsync_r.eq(self.vsync),
		]
		self.comb += [
			p_hsync.eq(self.hsync & ~hsync_r),
			p_vsync.eq(self.vsync & ~vsync_r)
		]

		hcounter = Signal(nbits)
		vcounter = Signal(nbits)
		self.sync.pix += [
			If(p_hsync,
				hcounter.eq(0)
			).Elif(self.de,
				hcounter.eq(hcounter + 1)
			),
			If(p_vsync,
				vcounter.eq(0)
			).Elif(p_hsync,
				vcounter.eq(vcounter + 1)
			)
		]

		hcounter_st = Signal(nbits)
		vcounter_st = Signal(nbits)
		self.sync.pix += [
			If(p_hsync & (hcounter != 0), hcounter_st.eq(hcounter)),
			If(p_vsync & (vcounter != 0), vcounter_st.eq(vcounter))
		]
		self.specials += MultiReg(hcounter_st, self._hres.field.w)
		self.specials += MultiReg(vcounter_st, self._vres.field.w)

		# DE
		de_r = Signal()
		pn_de = Signal()
		self.sync.pix += de_r.eq(self.de)
		self.comb += pn_de.eq(~self.de & de_r)

		decounter = Signal(2*nbits)
		self.sync.pix += If(self.de,
				decounter.eq(decounter + 1)
			).Else(
				decounter.eq(0)
			)

		decounter_st = Signal(2*nbits)
		self.sync.pix += If(pn_de, decounter_st.eq(decounter))
		self.specials += MultiReg(decounter_st, self._de_cycles.field.w)
