import inspect

from migen.fhdl.structure import *
from migen.fhdl.specials import Special

def from_local():
	f = Fragment()
	frame = inspect.currentframe().f_back
	ns = frame.f_locals
	for x in ns:
		obj = ns[x]
		if hasattr(obj, "get_fragment"):
			f += obj.get_fragment()
	return f

def from_attributes(obj):
	f = Fragment()
	for x in obj.__dict__.values():
		if hasattr(x, "get_fragment"):
			f += x.get_fragment()
	return f

class _FModuleProxy:
	def __init__(self, fm):
		object.__setattr__(self, "_fm", fm)

class _FModuleComb(_FModuleProxy):
	def __iadd__(self, other):
		if isinstance(other, (list, tuple)):
			self._fm._fragment.comb += other
		else:
			self._fm._fragment.comb.append(other)
		return self

def _cd_append(d, key, statements):
	try:
		l = d[key]
	except KeyError:
		l = []
		d[key] = l
	if isinstance(statements, (list, tuple)):
		l += statements
	else:
		l.append(statements)

class _FModuleSyncCD:
	def __init__(self, fm, cd):
		self._fm = fm
		self._cd = cd

	def __iadd__(self, other):
		_cd_append(self._fm._fragment.sync, self._cd, other)
		return self

class _FModuleSync(_FModuleProxy):
	def __iadd__(self, other):
		_cd_append(self._fm._fragment.sync, "sys", other)
		return self

	def __getattr__(self, name):
		return _FModuleSyncCD(self._fm, name)

	def __setattr__(self, name, value):
		if not isinstance(value, _FModuleSyncCD):
			raise AttributeError("Attempted to assign sync property - use += instead")

class _FModuleSpecials(_FModuleProxy):
	def __iadd__(self, other):
		if isinstance(other, (set, list, tuple)):
			self._fm._fragment.specials |= set(other)
		else:
			self._fm._fragment.specials.add(other)
		return self

class _FModuleSubmodules(_FModuleProxy):
	def __iadd__(self, other):
		if isinstance(other, (list, tuple)):
			self._fm._submodules += other
		else:
			self._fm._submodules.append(other)
		return self

class FModule:
	auto_attr = True

	def get_fragment(self):
		assert(not hasattr(self, "_fragment"))
		self._fragment = Fragment()
		self._submodules = []
		self.build_fragment()
		if hasattr(self, "do_simulation"):
			self._fragment.sim.append(self.do_simulation)
		for submodule in self._submodules:
			self._fragment += submodule.get_fragment()
		if self.auto_attr:
			for x in self.__dict__.values():
				if isinstance(x, Special):
					self._fragment.specials.add(x)
				elif hasattr(x, "get_fragment"):
					self._fragment += x.get_fragment()
		return self._fragment

	def __getattr__(self, name):
		if name == "comb":
			return _FModuleComb(self)
		elif name == "sync":
			return _FModuleSync(self)
		elif name == "specials":
			return _FModuleSpecials(self)
		elif name == "submodules":
			return _FModuleSubmodules(self)
		else:
			raise AttributeError("'"+self.__class__.__name__+"' object has no attribute '"+name+"'")

	def __setattr__(self, name, value):
		if name in ["comb", "sync", "specials", "submodules"]:
			if not isinstance(value, _FModuleProxy):
				raise AttributeError("Attempted to assign special FModule property - use += instead")
		else:
			object.__setattr__(self, name, value)

	def build_fragment(self):
		pass # do nothing (e.g. module has only submodules)
