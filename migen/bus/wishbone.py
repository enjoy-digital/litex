from migen.fhdl import structure as f
from .simple import Simple

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
