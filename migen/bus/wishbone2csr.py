from migen.fhdl import structure as f
from migen.corelogic import timeline
from . import wishbone
from . import csr

class Inst():
	def __init__(self):
		self.wishbone = wishbone.Slave("to_csr")
		self.csr = csr.Master("from_wishbone")
		self.timeline = timeline.Inst(self.wishbone.cyc_i & self.wishbone.stb_i,
			[(2, [f.Assign(self.wishbone.ack_o, 1)])])
	
	def GetFragment(self):
		sync = [
			f.Assign(self.csr.we_o, self.wishbone.we_i),
			f.Assign(self.csr.d_o, self.wishbone.dat_i),
			f.Assign(self.csr.a_o, self.wishbone.adr_i[2:16]),
			f.Assign(self.wishbone.ack_o, 0),
			f.Assign(self.wishbone.dat_o, self.csr.d_i)
		]
		return f.Fragment(sync=sync) + self.timeline.GetFragment()
