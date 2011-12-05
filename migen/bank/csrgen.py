from ..fhdl import structure as f
from ..bus.csr import *
from .description import *
from functools import partial

class Bank:
	def __init__(self, description, address=0):
		self.description = description
		self.address = address
		self.interface = Slave()
		d = partial(f.Declare, self)
		d("_sel")
	
	def GetFragment(self):
		a = f.Assign
		comb = []
		sync = []
		
		comb.append(a(self._sel, self.interface.a_i[12:] == f.Constant(self.address, f.BV(4))))
		
		nregs = len(self.description)
		nbits = f.BitsFor(nregs-1)
		
		# Bus writes
		bwcases = []
		for i in range(nregs):
			reg = self.description[i]
			nfields = len(reg.fields)
			bwra = []
			for j in range(nfields):
				field = reg.fields[j]
				if field.access_bus == WRITE_ONLY or field.access_bus == READ_WRITE:
					bwra.append(a(field.storage, self.interface.d_i[j]))
			if bwra:
				bwcases.append((f.Constant(i, f.BV(nbits)), bwra))
		if bwcases:
			sync.append(f.If(self._sel & self.interface.we_i, [f.Case(self.interface.a_i[:nbits], bwcases)]))
		
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
					brs.append(f.Constant(0, f.bv(field.size)))
			if reg_readable:
				if len(brs) > 1:
					brcases.append((f.Constant(i, f.BV(nbits)), [a(self.interface.d_o, f.Cat(*brs))]))
				else:
					brcases.append((f.Constant(i, f.BV(nbits)), [a(self.interface.d_o, brs[0])]))
		if brcases:
			sync.append(a(self.interface.d_o, f.Constant(0, f.BV(32))))
			sync.append(f.If(self._sel, [f.Case(self.interface.a_i[:nbits], brcases)]))
		else:
			comb.append(a(self.interface.d_o, f.Constant(0, f.BV(32))))
		
		# Device access
		for reg in self.description:
			for field in reg.fields:
				if field.access_dev == READ_ONLY or field.access_dev == READ_WRITE:
					comb.append(a(field.dev_r, field.storage))
				if field.access_dev == WRITE_ONLY or field.access_dev == READ_WRITE:
					sync.append(f.If(field.dev_we, [a(field.storage, field.dev_w)]))
		
		return f.Fragment(comb, sync)