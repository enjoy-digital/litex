from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.fhdl.specials import Instance
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.bank.description import *

class DataCapture(Module, AutoReg):
	def __init__(self, ntbits, invert):
		self.pad = Signal()
		self.serdesstrobe = Signal()
		self.d = Signal(10)

		self._r_dly_ctl = RegisterRaw(4)
		self._r_dly_busy = RegisterField(1, READ_ONLY, WRITE_ONLY)
		self._r_phase = RegisterField(2, READ_ONLY, WRITE_ONLY)
		self._r_phase_reset = RegisterRaw()

		###

		# IO
		pad_delayed = Signal()
		delay_inc = Signal()
		delay_ce = Signal()
		delay_cal = Signal()
		delay_rst = Signal()
		delay_busy = Signal()
		self.specials += Instance("IODELAY2",
			Instance.Parameter("DELAY_SRC", "IDATAIN"),
			Instance.Parameter("IDELAY_TYPE", "VARIABLE_FROM_HALF_MAX"),
			Instance.Parameter("COUNTER_WRAPAROUND", "STAY_AT_LIMIT"),
			Instance.Parameter("DATA_RATE", "SDR"),
			Instance.Input("IDATAIN", self.pad),
			Instance.Output("DATAOUT", pad_delayed),
			Instance.Input("CLK", ClockSignal("pix5x")),
			Instance.Input("IOCLK0", ClockSignal("pix10x")),
			Instance.Input("INC", delay_inc),
			Instance.Input("CE", delay_ce),
			Instance.Input("CAL", delay_cal),
			Instance.Input("RST", delay_rst),
			Instance.Output("BUSY", delay_busy),
			Instance.Input("T", 1)
		)

		d0 = Signal()
		d0p = Signal()
		d1 = Signal()
		d1p = Signal()
		self.specials += Instance("ISERDES2",
			Instance.Parameter("BITSLIP_ENABLE", "FALSE"),
			Instance.Parameter("DATA_RATE", "SDR"),
			Instance.Parameter("DATA_WIDTH", 4),
			Instance.Parameter("INTERFACE_TYPE", "RETIMED"),
			Instance.Parameter("SERDES_MODE", "NONE"),
			Instance.Output("Q4", d0),
			Instance.Output("Q3", d0p),
			Instance.Output("Q2", d1),
			Instance.Output("Q1", d1p),
			Instance.Input("BITSLIP", 0),
			Instance.Input("CE0", 1),
			Instance.Input("CLK0", ClockSignal("pix20x")),
			Instance.Input("CLKDIV", ClockSignal("pix5x")),
			Instance.Input("D", pad_delayed),
			Instance.Input("IOCE", self.serdesstrobe),
			Instance.Input("RST", 0)
		)

		# Phase detector
		lateness = Signal(ntbits, reset=2**(ntbits - 1))
		too_late = Signal()
		too_early = Signal()
		reset_lateness = Signal()
		self.comb += [
			too_late.eq(lateness == (2**ntbits - 1)),
			too_early.eq(lateness == 0)
		]
		self.sync.pix5x += [
			If(reset_lateness,
				lateness.eq(2**(ntbits - 1))
			).Elif(~delay_busy & ~too_late & ~too_early & (d0 != d1),
				If(d0,
					# 1 -----> 0
					#    d0p
					If(d0p,
						lateness.eq(lateness - 1)
					).Else(
						lateness.eq(lateness + 1)
					)
				).Else(
					# 0 -----> 1
					#    d0p
					If(d0p,
						lateness.eq(lateness + 1)
					).Else(
						lateness.eq(lateness - 1)
					)
				)
			)
		]

		# Delay control
		self.submodules.delay_done = PulseSynchronizer("pix5x", "sys")
		delay_pending = Signal()
		self.sync.pix5x += [
			self.delay_done.i.eq(0),
			If(~delay_pending,
				If(delay_cal | delay_ce, delay_pending.eq(1))
			).Else(
				If(~delay_busy,
					self.delay_done.i.eq(1),
					delay_pending.eq(0)
				)
			)
		]

		self.submodules.do_delay_cal = PulseSynchronizer("sys", "pix5x")
		self.submodules.do_delay_rst = PulseSynchronizer("sys", "pix5x")
		self.submodules.do_delay_inc = PulseSynchronizer("sys", "pix5x")
		self.submodules.do_delay_dec = PulseSynchronizer("sys", "pix5x")
		self.comb += [
			delay_cal.eq(self.do_delay_cal.o),
			delay_rst.eq(self.do_delay_rst.o),
			delay_inc.eq(self.do_delay_inc.o),
			delay_ce.eq(self.do_delay_inc.o | self.do_delay_dec.o),
		]

		sys_delay_pending = Signal()
		self.sync += [
			If(self.do_delay_cal.i | self.do_delay_inc.i | self.do_delay_dec.i,
				sys_delay_pending.eq(1)
			).Elif(self.delay_done.o,
				sys_delay_pending.eq(0)
			)
		]

		self.comb += [
			self.do_delay_cal.i.eq(self._r_dly_ctl.re & self._r_dly_ctl.r[0]),
			self.do_delay_rst.i.eq(self._r_dly_ctl.re & self._r_dly_ctl.r[1]),
			self.do_delay_inc.i.eq(self._r_dly_ctl.re & self._r_dly_ctl.r[2]),
			self.do_delay_dec.i.eq(self._r_dly_ctl.re & self._r_dly_ctl.r[3]),
			self._r_dly_busy.field.w.eq(sys_delay_pending)
		]

		# Phase detector control
		self.specials += MultiReg(Cat(too_late, too_early), self._r_phase.field.w)
		self.submodules.do_reset_lateness = PulseSynchronizer("sys", "pix5x")
		self.comb += [
			reset_lateness.eq(self.do_reset_lateness.o),
			self.do_reset_lateness.i.eq(self._r_phase_reset.re)
		]

		# 2:10 deserialization
		d0i = Signal()
		d1i = Signal()
		self.comb += [
			d0i.eq(d0 ^ invert),
			d1i.eq(d1 ^ invert)
		]
		dsr = Signal(10)
		self.sync.pix5x += dsr.eq(Cat(dsr[2:], d0i, d1i))
		self.sync.pix += self.d.eq(dsr)
