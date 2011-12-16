import inspect

from migen.fhdl.structure import *

def from_local():
	f = Fragment()
	frame = inspect.currentframe().f_back
	ns = frame.f_locals
	for x in ns:
		obj = ns[x]
		if hasattr(obj, "get_fragment"):
			f += obj.get_fragment()
	return f
