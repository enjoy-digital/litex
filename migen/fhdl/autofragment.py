from .structure import *
import inspect

def FromLocal():
	f = Fragment()
	frame = inspect.currentframe().f_back
	ns = frame.f_locals
	for x in ns:
		obj = ns[x]
		if hasattr(obj, "GetFragment"):
			f += obj.GetFragment()
	return f
