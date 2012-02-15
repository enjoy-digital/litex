from migen.fhdl.structure import *
from migen.bus.simple import *

def phase_description(a, ba, d):
	return Description(
		(M_TO_S,	"address",	a),
		(M_TO_S,	"bank",		ba),
		(M_TO_S,	"cas_n",	1),
		(M_TO_S,	"cke",		1),
		(M_TO_S,	"cs_n",		1),
		(M_TO_S,	"ras_n",	1),
		(M_TO_S,	"we_n",		1),
		
		(M_TO_S,	"wrdata",	d),
		(M_TO_S,	"wrdata_en",	1),
		(M_TO_S,	"wrdata_mask",	d//8),
		
		(M_TO_S,	"rddata_en",	1),
		(S_TO_M,	"rddata",	d),
		(S_TO_M,	"rddata_valid",	1)
	)

class Interface:
	def __init__(self, a, ba, d, nphases=1):
		self.pdesc = phase_description(a, ba, d)
		self.phases = [SimpleInterface(self.pdesc) for i in range(nphases)]
	
	# Returns pairs (DFI-mandated signal name, Migen signal object)
	def get_standard_names(self, m2s=True, s2m=True):
		r = []
		add_suffix = len(self.phases) > 1
		for n, phase in enumerate(self.phases):
			for signal in self.pdesc.desc:
				if (m2s and signal[0] == M_TO_S) or (s2m and signal[0] == S_TO_M):
					if add_suffix:
						if signal[0] == M_TO_S:
							suffix = "_p" + int(n)
						else:
							suffix = "_w" + int(n)
					else:
						suffix = ""
					r.append(("dfi_" + signal[1] + suffix, getattr(phase, signal[1])))
		return r

class Interconnect:
	def __init__(self, master, slave):
		self.master = master
		self.slave = slave
	
	def get_fragment(self):
		f = Fragment()
		for pm, ps in zip(self.master.phases, self.slave.phases):
			ic = SimpleInterconnect(pm, [ps])
			f += ic.get_fragment()
		return f
