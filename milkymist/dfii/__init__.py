from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bus import dfi
from migen.bank.description import *

class PhaseInjector(Module, AutoReg):
	def __init__(self, phase):
		self._cs = Field("cs", 1, WRITE_ONLY, READ_ONLY)
		self._we = Field("we", 1, WRITE_ONLY, READ_ONLY)
		self._cas = Field("cas", 1, WRITE_ONLY, READ_ONLY)
		self._ras = Field("ras", 1, WRITE_ONLY, READ_ONLY)
		self._wren = Field("wren", 1, WRITE_ONLY, READ_ONLY)
		self._rden = Field("rden", 1, WRITE_ONLY, READ_ONLY)
		self._command = RegisterFields("command",
			[self._cs, self._we, self._cas, self._ras, self._wren, self._rden])
		self._command_issue = RegisterRaw("command_issue")
		
		self._address = RegisterField("address", len(phase.address))
		self._baddress = RegisterField("baddress", len(phase.bank))
		
		self._wrdata = RegisterField("wrdata", len(phase.wrdata))
		self._rddata = RegisterField("rddata", len(phase.rddata), READ_ONLY, WRITE_ONLY)
	
		###

		self.comb += [
			If(self._command_issue.re,
				phase.cs_n.eq(~self._cs.r),
				phase.we_n.eq(~self._we.r),
				phase.cas_n.eq(~self._cas.r),
				phase.ras_n.eq(~self._ras.r)
			).Else(
				phase.cs_n.eq(1),
				phase.we_n.eq(1),
				phase.cas_n.eq(1),
				phase.ras_n.eq(1)
			),
			phase.address.eq(self._address.field.r),
			phase.bank.eq(self._baddress.field.r),
			phase.wrdata_en.eq(self._command_issue.re & self._wren.r),
			phase.rddata_en.eq(self._command_issue.re & self._rden.r),
			phase.wrdata.eq(self._wrdata.field.r),
			phase.wrdata_mask.eq(0)
		]
		self.sync += If(phase.rddata_valid, self._rddata.field.w.eq(phase.rddata))

class DFIInjector(Module, AutoReg):
	def __init__(self, a, ba, d, nphases=1):
		inti = dfi.Interface(a, ba, d, nphases)
		self.slave = dfi.Interface(a, ba, d, nphases)
		self.master = dfi.Interface(a, ba, d, nphases)
		
		self._sel = Field("sel")
		self._cke = Field("cke")
		self._control = RegisterFields("control", [self._sel, self._cke])
		
		for n, phase in enumerate(inti.phases):
			setattr(self.submodules, "pi" + str(n), PhaseInjector(phase))
	
		###
	
		connect_inti = dfi.interconnect_stmts(inti, self.master)
		connect_slave = dfi.interconnect_stmts(self.slave, self.master)
		self.comb += If(self._sel.r, *connect_slave).Else(*connect_inti)
		self.comb += [phase.cke.eq(self._cke.r) for phase in inti.phases]
