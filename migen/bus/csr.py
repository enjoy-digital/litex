from migen.fhdl.structure import *
from migen.bus.simple import *

_desc = Description(
	(M_TO_S,	"adr",		14),
	(M_TO_S,	"we",		1),
	(M_TO_S,	"dat_w",	8),
	(S_TO_M,	"dat_r",	8)
)

class Interface(SimpleInterface):
	def __init__(self):
		SimpleInterface.__init__(self, _desc)

class Interconnect(SimpleInterconnect):
	pass
