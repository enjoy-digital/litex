from migen.fhdl.structure import *
from migen.fhdl.structure import _make_signal_name

class Record:
	def __init__(self, template, name=None):
		self.name = name or _make_signal_name()
		for f in template:
			if isinstance(f, tuple):
				if isinstance(f[1], BV):
					setattr(self, f[0], Signal(f[1], self.name + "_" + f[0]))
				elif isinstance(f[1], Signal) or isinstance(f[1], Record):
					setattr(self, f[0], f[1])
				elif isinstance(f[1], list):
					setattr(self, f[0], Record(f[1], self.name + "_" + f[0]))
				else:
					raise TypeError
			else:
				setattr(self, f, Signal(BV(1), self.name + "_" + f))

	def template(self):
		l = []
		for key in sorted(self.__dict__):
			e = self.__dict__[key]
			if isinstance(e, Signal):
				l.append((key, e.bv))
			elif isinstance(e, Record):
				l.append((key, e.template()))
		return l
	
	def copy(self, name=None):
		return Record(self.template(), name or _make_signal_name())
	
	def subrecord(self, *descr):
		fields = {}
		for item in descr:
			path = item.split('/')
			last = path.pop()
			pos_self = self
			pos_fields = fields
			for hop in path:
				pos_self = getattr(pos_self, hop)
				try:
					pos_fields = fields[hop]
				except KeyError:
					pos_fields = fields[hop] = {}
				if not isinstance(pos_fields, dict):
					raise ValueError
			if last in pos_fields:
				raise ValueError
			pos_fields[last] = getattr(pos_self, last)
		def dict_to_list(d):
			l = []
			for key in d:
				e = d[key]
				if isinstance(e, dict):
					l.append((key, dict_to_list(e)))
				else:
					l.append((key, e))
			return l
		return Record(dict_to_list(fields), "subrecord")
	
	def compatible(self, other):
		tpl1 = self.flatten()
		tpl2 = other.flatten()
		return len(tpl1) == len(tpl2)
	
	def flatten(self):
		l = []
		for key in sorted(self.__dict__):
			e = self.__dict__[key]
			if isinstance(e, Signal):
				l.append(e)
			elif isinstance(e, Record):
				l += e.flatten()
		return l
	
	def __repr__(self):
		return repr(self.template())
