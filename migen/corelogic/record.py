from migen.fhdl.structure import *

class Record:
	def __init__(self, layout, name=""):
		self.name = name
		self.field_order = []
		if self.name:
			prefix = self.name + "_"
		else:
			prefix = ""
		for f in layout:
			if isinstance(f, tuple):
				if isinstance(f[1], BV):
					setattr(self, f[0], Signal(f[1], prefix + f[0]))
				elif isinstance(f[1], Signal) or isinstance(f[1], Record):
					setattr(self, f[0], f[1])
				elif isinstance(f[1], list):
					setattr(self, f[0], Record(f[1], prefix + f[0]))
				else:
					raise TypeError
				if len(f) == 3:
					self.field_order.append((f[0], f[2]))
				else:
					self.field_order.append((f[0], 1))
			else:
				setattr(self, f, Signal(BV(1), prefix + f))
				self.field_order.append((f, 1))

	def layout(self):
		l = []
		for key, alignment in self.field_order:
			e = self.__dict__[key]
			if isinstance(e, Signal):
				l.append((key, e.bv, alignment))
			elif isinstance(e, Record):
				l.append((key, e.layout(), alignment))
		return l
	
	def copy(self, name=None):
		return Record(self.layout(), name)
	
	def get_alignment(self, name):
		return list(filter(lambda x: x[0] == name, self.field_order))[0][1]
	
	def subrecord(self, *descr):
		fields = []
		for item in descr:
			path = item.split('/')
			last = path.pop()
			pos_self = self
			pos_fields = fields
			for hop in path:
				pos_self = getattr(pos_self, hop)
				lu = list(filter(lambda x: x[0] == hop, pos_fields))
				try:
					pos_fields = lu[0][1]
				except IndexError:
					n = []
					pos_fields.append((hop, n))
					pos_fields = n
				if not isinstance(pos_fields, list):
					raise ValueError
			if len(list(filter(lambda x: x[0] == last, pos_fields))) > 0:
				raise ValueError
			pos_fields.append((last, getattr(pos_self, last), pos_self.get_alignment(last)))
		return Record(fields, "subrecord")
	
	def compatible(self, other):
		tpl1 = self.flatten()
		tpl2 = other.flatten()
		return len(tpl1) == len(tpl2)
	
	def flatten(self, align=False, offset=0, return_offset=False):
		l = []
		for key, alignment in self.field_order:
			if align:
				pad_size = alignment - (offset % alignment)
				if pad_size < alignment:
					l.append(Constant(0, BV(pad_size)))
					offset += pad_size
			
			e = self.__dict__[key]
			if isinstance(e, Signal):
				added = [e]
			elif isinstance(e, Record):
				added = e.flatten(align, offset)
			else:
				raise TypeError
			for x in added:
				offset += x.bv.width
			l += added
		if return_offset:
			return (l, offset)
		else:
			return l
	
	def to_signal(self, assignment_list, sig_out, align=False):
		flattened, length = self.flatten(align, return_offset=True)
		raw = Signal(BV(length))
		if sig_out:
			assignment_list.append(raw.eq(Cat(*flattened)))
		else:
			assignment_list.append(Cat(*flattened).eq(raw))
		return raw
	
	def __repr__(self):
		return repr(self.layout())
