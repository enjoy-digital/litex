from migen.fhdl.structure import *
from migen.bus.csr import *
from migen.bank.description import *

class Bank:
	def __init__(self, description, address=0):
		self.description = description
		self.address = address
		self.interface = Slave()
	
	def get_fragment(self):
		comb = []
		sync = []
		
		sel = Signal()
		comb.append(sel.eq(self.interface.a_i[9:] == Constant(self.address, BV(5))))
		
		nbits = bits_for(len(self.description)-1)
		
		# Bus writes
		bwcases = []
		for i, reg in enumerate(self.description):
			if isinstance(reg, RegisterRaw):
				comb.append(reg.r.eq(self.interface.d_i[:reg.size]))
				comb.append(reg.re.eq(sel & \
					self.interface.we_i & \
					(self.interface.a_i[:nbits] == Constant(i, BV(nbits)))))
			elif isinstance(reg, RegisterFields):
				bwra = [Constant(i, BV(nbits))]
				for j, field in enumerate(reg.fields):
					if field.access_bus == WRITE_ONLY or field.access_bus == READ_WRITE:
						bwra.append(field.storage.eq(self.interface.d_i[j]))
				if len(bwra) > 1:
					bwcases.append(bwra)
			else:
				raise TypeError
		if bwcases:
			sync.append(If(sel & self.interface.we_i, Case(self.interface.a_i[:nbits], *bwcases)))
		
		# Bus reads
		brcases = []
		for i, reg in enumerate(self.description):
			if isinstance(reg, RegisterRaw):
				brcases.append([Constant(i, BV(nbits)), self.interface.d_o.eq(reg.w)])
			elif isinstance(reg, RegisterFields):
				brs = []
				reg_readable = False
				for j, field in enumerate(reg.fields):
					if field.access_bus == READ_ONLY or field.access_bus == READ_WRITE:
						brs.append(field.storage)
						reg_readable = True
					else:
						brs.append(Constant(0, BV(field.size)))
				if reg_readable:
					if len(brs) > 1:
						brcases.append([Constant(i, BV(nbits)), self.interface.d_o.eq(f.Cat(*brs))])
					else:
						brcases.append([Constant(i, BV(nbits)), self.interface.d_o.eq(brs[0])])
			else:
				raise TypeError
		if brcases:
			sync.append(self.interface.d_o.eq(Constant(0, BV(8))))
			sync.append(If(sel, Case(self.interface.a_i[:nbits], *brcases)))
		else:
			comb.append(self.interface.d_o.eq(Constant(0, BV(8))))
		
		# Device access
		for reg in self.description:
			if isinstance(reg, RegisterFields):
				for field in reg.fields:
					if field.access_dev == READ_ONLY or field.access_dev == READ_WRITE:
						comb.append(field.r.eq(field.storage))
					if field.access_dev == WRITE_ONLY or field.access_dev == READ_WRITE:
						sync.append(If(field.we, field.storage.eq(field.w)))
		
		return Fragment(comb, sync)
