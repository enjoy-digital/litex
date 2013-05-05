from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.genlib.cdc import MultiReg
from migen.bank.description import *

class ResolutionDetection(Module, AutoCSR):
	def __init__(self, nbits=11):
		self.vsync = Signal()
		self.de = Signal()

		self._hres = CSRStatus(nbits)
		self._vres = CSRStatus(nbits)

		###

		# Detect DE transitions
		de_r = Signal()
		pn_de = Signal()
		self.sync.pix += de_r.eq(self.de)
		self.comb += pn_de.eq(~self.de & de_r)

		# HRES
		hcounter = Signal(nbits)
		self.sync.pix += If(self.de,
				hcounter.eq(hcounter + 1)
			).Else(
				hcounter.eq(0)
			)

		hcounter_st = Signal(nbits)
		self.sync.pix += If(pn_de, hcounter_st.eq(hcounter))
		self.specials += MultiReg(hcounter_st, self._hres.status)

		# VRES
		vsync_r = Signal()
		p_vsync = Signal()
		self.sync.pix += vsync_r.eq(self.vsync),
		self.comb += p_vsync.eq(self.vsync & ~vsync_r)

		vcounter = Signal(nbits)
		self.sync.pix += If(p_vsync,
				vcounter.eq(0)
			).Elif(pn_de,
				vcounter.eq(vcounter + 1)
			)

		vcounter_st = Signal(nbits)
		self.sync.pix += If(p_vsync, vcounter_st.eq(vcounter))
		self.specials += MultiReg(vcounter_st, self._vres.status)
