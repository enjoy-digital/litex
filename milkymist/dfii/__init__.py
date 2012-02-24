from migen.fhdl.structure import *
from migen.bus import dfi
from migen.bank.description import *
from migen.bank import csrgen

class PhaseInjector:
	def __init__(self, phase):
		self.phase = phase
		
		self._cs = Field("cs", 1, WRITE_ONLY, READ_ONLY)
		self._we = Field("we", 1, WRITE_ONLY, READ_ONLY)
		self._cas = Field("cas", 1, WRITE_ONLY, READ_ONLY)
		self._ras = Field("ras", 1, WRITE_ONLY, READ_ONLY)
		self._wren = Field("wren", 1, WRITE_ONLY, READ_ONLY)
		self._rden = Field("rden", 1, WRITE_ONLY, READ_ONLY)
		self._command = RegisterFields("command",
			[self._cs, self._we, self._cas, self._ras, self._wren, self._rden])
		
		self._address = RegisterField("address", self.phase.address.bv.width)
		self._baddress = RegisterField("baddress", self.phase.bank.bv.width)
		
		self._wrdata = RegisterField("wrdata", self.phase.wrdata.bv.width)
		self._rddata = RegisterField("rddata", self.phase.rddata.bv.width, READ_ONLY, WRITE_ONLY)
	
	def get_registers(self):
		return [self._command,
			self._address, self._baddress,
			self._wrdata, self._rddata]
		
	def get_fragment(self):
		comb = [
			If(self._command.re,
				self.phase.cs_n.eq(~self._cs.r),
				self.phase.we_n.eq(~self._we.r),
				self.phase.cas_n.eq(~self._cas.r),
				self.phase.ras_n.eq(~self._ras.r)
			).Else(
				self.phase.cs_n.eq(1),
				self.phase.we_n.eq(1),
				self.phase.cas_n.eq(1),
				self.phase.ras_n.eq(1)
			),
			self.phase.address.eq(self._address.field.r),
			self.phase.bank.eq(self._baddress.field.r),
			self.phase.wrdata_en.eq(self._command.re & self._wren.r),
			self.phase.rddata_en.eq(self._command.re & self._rden.r),
			self.phase.wrdata.eq(self._wrdata.field.r),
			self.phase.wrdata_mask.eq(0)
		]
		sync = [
			If(self.phase.rddata_valid, self._rddata.field.w.eq(self.phase.rddata))
		]
		return Fragment(comb, sync)

class DFIInjector:
	def __init__(self, csr_address, a, ba, d, nphases=1):
		self._int = dfi.Interface(a, ba, d, nphases)
		self.slave = dfi.Interface(a, ba, d, nphases)
		self.master = dfi.Interface(a, ba, d, nphases)
		
		self._sel = Field("sel")
		self._cke = Field("cke")
		self._control = RegisterFields("control", [self._sel, self._cke])
		
		self._phase_injectors = [PhaseInjector(phase) for phase in self._int.phases]
		
		registers = sum([pi.get_registers() for pi in self._phase_injectors], [self._control])
		self.bank = csrgen.Bank(registers, address=csr_address)
	
	def get_fragment(self):
		connect_int = dfi.interconnect_stmts(self._int, self.master)
		connect_slave = dfi.interconnect_stmts(self.slave, self.master)
		comb = [
			If(self._sel.r, *connect_slave).Else(*connect_int)
		]
		comb += [phase.cke.eq(self._cke.r) for phase in self._int.phases]
		
		return Fragment(comb) \
			+ sum([pi.get_fragment() for pi in self._phase_injectors], Fragment()) \
			+ self.bank.get_fragment()
