from migen.fhdl.structure import *
from migen.bus import dfi
from migen.bank.description import *
from migen.bank import csrgen

def _data_en(trigger, output, delay, duration):
	dcounter = Signal(BV(4))
	dce = Signal()
	return [
		If(trigger,
			dcounter.eq(delay),
			dce.eq(1)
		).Elif(dce,
			dcounter.eq(dcounter - 1),
			If(dcounter == 0,
				If(~output,
					output.eq(1),
					dcounter.eq(duration)
				).Else(
					output.eq(0),
					dce.eq(0)
				)
			)
		)
	]

class DFIInjector:
	def __init__(self, csr_address, a, ba, d, nphases=1):
		self._int = dfi.Interface(a, ba, d, nphases)
		self.slave = dfi.Interface(a, ba, d, nphases)
		self.master = dfi.Interface(a, ba, d, nphases)
		
		self._sel = Field("sel")
		self._cke = Field("cke")
		self._control = RegisterFields("control", [self._sel, self._cke])
		
		self._cs = Field("cs", 1, WRITE_ONLY, READ_ONLY)
		self._we = Field("we", 1, WRITE_ONLY, READ_ONLY)
		self._cas = Field("cas", 1, WRITE_ONLY, READ_ONLY)
		self._ras = Field("ras", 1, WRITE_ONLY, READ_ONLY)
		self._rddata = Field("rddata", 1, WRITE_ONLY, READ_ONLY)
		self._wrdata = Field("wrdata", 1, WRITE_ONLY, READ_ONLY)
		self._command = RegisterFields("command",
			[self._cs, self._we, self._cas, self._ras, self._rddata, self._wrdata])
		
		self._address = RegisterField("address", a)
		self._baddress = RegisterField("baddress", ba)
		
		self._rddelay = RegisterField("rddelay", 4, reset=5)
		self._rdduration = RegisterField("rdduration", 3, reset=0)
		self._wrdelay = RegisterField("wrdelay", 4, reset=3)
		self._wrduration = RegisterField("wrduration", 3, reset=0)
		
		self.bank = csrgen.Bank([
				self._control, self._command,
				self._address, self._baddress,
				self._rddelay, self._rdduration,
				self._wrdelay, self._wrduration
			], address=csr_address)
	
	def get_fragment(self):
		comb = []
		sync = []
		
		# mux
		connect_int = dfi.interconnect_stmts(self._int, self.master)
		connect_slave = dfi.interconnect_stmts(self.slave, self.master)
		comb.append(If(self._sel.r, *connect_slave).Else(*connect_int))
		
		# phases
		rddata_en = Signal()
		wrdata_en = Signal()
		for phase in self._int.phases:
			comb += [
				phase.cke.eq(self._cke.r),
				phase.rddata_en.eq(rddata_en),
				phase.wrdata_en.eq(wrdata_en)
			]
		cmdphase = self._int.phases[0]
		for phase in self._int.phases[1:]:
			comb += [
				phase.cs_n.eq(1),
				phase.we_n.eq(1),
				phase.cas_n.eq(1),
				phase.ras_n.eq(1)
			]
		
		# commands
		comb += [
			If(self._command.re,
				cmdphase.cs_n.eq(~self._cs.r),
				cmdphase.we_n.eq(~self._we.r),
				cmdphase.cas_n.eq(~self._cas.r),
				cmdphase.ras_n.eq(~self._ras.r)
			).Else(
				cmdphase.cs_n.eq(1),
				cmdphase.we_n.eq(1),
				cmdphase.cas_n.eq(1),
				cmdphase.ras_n.eq(1)
			)
		]
		
		# addresses
		comb += [
			cmdphase.address.eq(self._address.field.r),
			cmdphase.bank.eq(self._baddress.field.r)
		]
		
		# data enables
		sync += _data_en(self._command.re & self._rddata.r,
			rddata_en,
			self._rddelay.field.r, self._rdduration.field.r)
		sync += _data_en(self._command.re & self._wrdata.r,
			wrdata_en,
			self._wrdelay.field.r, self._wrduration.field.r)
		
		return Fragment(comb, sync) + self.bank.get_fragment()
