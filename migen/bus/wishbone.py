from migen.fhdl import structure as f
from migen.corelogic import roundrobin, multimux
from .simple import Simple, GetSigName
from functools import partial

_desc = [
	(True,	"adr",	32),
	(True,	"dat",	32),
	(False,	"dat",	32),
	(True,	"sel",	4),
	(True,	"cyc",	1),
	(True,	"stb",	1),
	(False,	"ack",	1),
	(True,	"we",	1),
	(True,	"cti",	3),
	(True,	"bte",	2),
	(False,	"err",	1)
]

class Master(Simple):
	def __init__(self, name=""):
		Simple.__init__(self, _desc, False, name)

class Slave(Simple):
	def __init__(self, name=""):
		Simple.__init__(self, _desc, True, name)

class Arbiter:
	def __init__(self, masters, target):
		self.masters = masters
		self.target = target
		self.rr = roundrobin.Inst(len(self.masters))

	def GetFragment(self):
		comb = []
		
		# mux master->slave signals
		m2s_names = [GetSigName(x, False) for x in _desc if x[0]]
		m2s_masters = [[getattr(m, name) for name in m2s_names] for m in self.masters]
		m2s_target = [getattr(self.target, name) for name in m2s_names]
		comb += multimux.MultiMux(self.rr.grant, m2s_masters, m2s_target)
		
		# connect slave->master signals
		s2m_names = [GetSigName(x, False) for x in _desc if not x[0]]
		for name in s2m_names:
			source = getattr(self.target, name)
			for m in self.masters:
				dest = getattr(m, name)
				comb.append(f.Assign(dest, source))
		
		# connect bus requests to round-robin selector
		reqs = [m.cyc_o for m in self.masters]
		comb.append(f.Assign(self.rr.request, f.Cat(*reqs)))
		
		return f.Fragment(comb) + self.rr.GetFragment()

