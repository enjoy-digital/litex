import collections

from migen.fhdl.structure import *
from migen.fhdl.specials import Special
from migen.fhdl.tools import flat_iteration

class FinalizeError(Exception):
	pass

def _flat_list(e):
	if isinstance(e, collections.Iterable):
		return flat_iteration(e)
	else:
		return [e]

class _ModuleProxy:
	def __init__(self, fm):
		object.__setattr__(self, "_fm", fm)

class _ModuleComb(_ModuleProxy):
	def __iadd__(self, other):
		self._fm._fragment.comb += _flat_list(other)
		return self

def _cd_append(d, key, statements):
	try:
		l = d[key]
	except KeyError:
		l = []
		d[key] = l
	l += _flat_list(statements)

class _ModuleSyncCD:
	def __init__(self, fm, cd):
		self._fm = fm
		self._cd = cd

	def __iadd__(self, other):
		_cd_append(self._fm._fragment.sync, self._cd, other)
		return self

class _ModuleSync(_ModuleProxy):
	def __iadd__(self, other):
		_cd_append(self._fm._fragment.sync, "sys", other)
		return self

	def __getattr__(self, name):
		return _ModuleSyncCD(self._fm, name)

	def __setattr__(self, name, value):
		if not isinstance(value, _ModuleSyncCD):
			raise AttributeError("Attempted to assign sync property - use += instead")

# _ModuleForwardAttr enables user classes to do e.g.:
# self.subm.foobar = SomeModule()
# and then access the submodule with self.foobar.
class _ModuleForwardAttr:
	def __setattr__(self, name, value):
		self.__iadd__(value)
		setattr(self._fm, name, value)

class _ModuleSpecials(_ModuleProxy, _ModuleForwardAttr):
	def __iadd__(self, other):
		self._fm._fragment.specials |= set(_flat_list(other))
		return self

class _ModuleSubmodules(_ModuleProxy, _ModuleForwardAttr):
	def __iadd__(self, other):
		self._fm._submodules += _flat_list(other)
		return self

class Module:
	def get_fragment(self):
		assert(not self._get_fragment_called)
		self._get_fragment_called = True
		self.finalize()
		return self._fragment

	def __getattr__(self, name):
		if name == "comb":
			return _ModuleComb(self)
		elif name == "sync":
			return _ModuleSync(self)
		elif name == "specials":
			return _ModuleSpecials(self)
		elif name == "submodules":
			return _ModuleSubmodules(self)

		# hack to have initialized regular attributes without using __init__
		# (which would require derived classes to call it)
		elif name == "finalized":
			self.finalized = False
			return self.finalized
		elif name == "_fragment":
			try:
				sim = [self.do_simulation]
			except AttributeError:
				sim = []
			self._fragment = Fragment(sim=sim)
			return self._fragment
		elif name == "_submodules":
			self._submodules = []
			return self._submodules
		elif name == "_get_fragment_called":
			self._get_fragment_called = False
			return self._get_fragment_called

		else:
			raise AttributeError("'"+self.__class__.__name__+"' object has no attribute '"+name+"'")

	def __setattr__(self, name, value):
		if name in ["comb", "sync", "specials", "submodules"]:
			if not isinstance(value, _ModuleProxy):
				raise AttributeError("Attempted to assign special Module property - use += instead")
		else:
			object.__setattr__(self, name, value)

	def finalize(self):
		if not self.finalized:
			self.finalized = True
			for submodule in self._submodules:
				self._fragment += submodule.get_fragment()
			self._submodules = []
			self.do_finalize()
			for submodule in self._submodules:
				self._fragment += submodule.get_fragment()

	def do_finalize(self):
		pass
