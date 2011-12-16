from migen.fhdl.structure import *
from migen.bus.csr import *
from migen.bank.description import *

class Bank:
	def __init__(self, description, address=0):
		self.description = description
		self.address = address
		self.interface = Slave()
		declare_signal(self, "_sel")
	
	def get_fragment(self):
		comb = []
		sync = []
		
		comb.append(self._sel.eq(self.interface.a_i[10:] == Constant(self.address, BV(4))))
		
		nregs = len(self.description)
		nbits = bits_for(nregs-1)
		
		# Bus writes
		bwcases = []
		for i in range(nregs):
			reg = self.description[i]
			nfields = len(reg.fields)
			bwra = [Constant(i, BV(nbits))]
			for j in range(nfields):
				field = reg.fields[j]
				if field.access_bus == WRITE_ONLY or field.access_bus == READ_WRITE:
					bwra.append(field.storage.eq(self.interface.d_i[j]))
			if len(bwra) > 1:
				bwcases.append(bwra)
		if bwcases:
			sync.append(If(self._sel & self.interface.we_i, Case(self.interface.a_i[:nbits], *bwcases)))
		
		# Bus reads
		brcases = []
		for i in range(nregs):
			reg = self.description[i]
			nfields = len(reg.fields)
			brs = []
			reg_readable = False
			for j in range(nfields):
				field = reg.fields[j]
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
		if brcases:
			sync.append(self.interface.d_o.eq(Constant(0, BV(32))))
			sync.append(If(self._sel, Case(self.interface.a_i[:nbits], *brcases)))
		else:
			comb.append(self.interface.d_o.eq(Constant(0, BV(32))))
		
		# Device access
		for reg in self.description:
			for field in reg.fields:
				if field.access_dev == READ_ONLY or field.access_dev == READ_WRITE:
					comb.append(field.dev_r.eq(field.storage))
				if field.access_dev == WRITE_ONLY or field.access_dev == READ_WRITE:
					sync.append(If(field.dev_we, field.storage.eq(field.dev_w)))
		
		return Fragment(comb, sync)
