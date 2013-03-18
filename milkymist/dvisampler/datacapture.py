from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.fhdl.specials import Instance
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.bank.description import *

class DataCapture(Module, AutoReg):
	def __init__(self, ntbits, debug=False):
		self.pad = Signal()
		self.serdesstrobe = Signal()
		self.d0 = Signal() # pix5x clock domain
		self.d1 = Signal() # pix5x clock domain

		if debug:
			self._r_current_tap = RegisterField(8, READ_ONLY, WRITE_ONLY)

		###

		# IO
		pad_delayed = Signal()
		delay_inc = Signal()
		delay_ce = Signal()
		self.specials += Instance("IODELAY2",
			Instance.Parameter("DELAY_SRC", "IDATAIN"),
			Instance.Parameter("IDELAY_TYPE", "VARIABLE_FROM_ZERO"),
			Instance.Parameter("COUNTER_WRAPAROUND", "STAY_AT_LIMIT"),
			Instance.Parameter("DATA_RATE", "SDR"),
			Instance.Input("IDATAIN", self.pad),
			Instance.Output("DATAOUT", pad_delayed),
			Instance.Input("INC", delay_inc),
			Instance.Input("CE", delay_ce),
			Instance.Input("RST", ResetSignal("pix5x")),
			Instance.Input("CLK", ClockSignal("pix5x")),
			Instance.Input("IOCLK0", ClockSignal("pix20x")),
			Instance.Input("CAL", 0),
			Instance.Input("T", 1)
		)

		d0p = Signal()
		d1p = Signal()
		self.specials += Instance("ISERDES2",
			Instance.Parameter("BITSLIP_ENABLE", "FALSE"),
			Instance.Parameter("DATA_RATE", "SDR"),
			Instance.Parameter("DATA_WIDTH", 4),
			Instance.Parameter("INTERFACE_TYPE", "RETIMED"),
			Instance.Parameter("SERDES_MODE", "NONE"),
			Instance.Output("Q4", self.d0),
			Instance.Output("Q3", d0p),
			Instance.Output("Q2", self.d1),
			Instance.Output("Q1", d1p),
			Instance.Input("BITSLIP", 0),
			Instance.Input("CE0", 1),
			Instance.Input("CLK0", ClockSignal("pix20x")),
			Instance.Input("CLKDIV", ClockSignal("pix5x")),
			Instance.Input("D", pad_delayed),
			Instance.Input("IOCE", self.serdesstrobe),
			Instance.Input("RST", 0)
		)

		# Transition counter
		transitions = Signal(ntbits)
		lateness = Signal((ntbits + 1, True))
		pulse_inc = Signal()
		pulse_dec = Signal()
		self.sync.pix5x += [
			pulse_inc.eq(0),
			pulse_dec.eq(0),
			If(transitions ==  2**ntbits - 1,
				If(lateness[ntbits],
					pulse_inc.eq(1)
				).Else(
					pulse_dec.eq(1)
				),
				lateness.eq(0),
				transitions.eq(0)
			).Elif(self.d0 != self.d1,
				If(self.d0,
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
				),
				transitions.eq(transitions + 1)
			)
		]

		# Drive IODELAY controls
		delay_init = Signal()
		delay_init_count = Signal(7, reset=127)
		self.comb += delay_init.eq(delay_init_count != 0)
		self.sync.pix5x += If(delay_init, delay_init_count.eq(delay_init_count - 1))
		self.comb += [
			delay_ce.eq(delay_init | pulse_inc | pulse_dec),
			delay_inc.eq(delay_init | pulse_inc)
		]

		# Debug
		if debug:
			# Transfer delay update commands to system clock domain
			pix5x_reset_sys = Signal()
			self.specials += MultiReg(ResetSignal("pix5x"), pix5x_reset_sys, "sys")
			self.submodules.xf_inc = PulseSynchronizer("pix5x", "sys")
			self.submodules.xf_dec = PulseSynchronizer("pix5x", "sys")
			self.comb += [
				self.xf_inc.i.eq(pulse_inc),
				self.xf_dec.i.eq(pulse_dec)
			]
			# Update tap count in system clock domain
			current_tap = Signal(8, reset=127)
			self.comb += self._r_current_tap.field.w.eq(current_tap)
			self.sync += If(pix5x_reset_sys,
					current_tap.eq(127)
				).Elif(self.xf_inc.o & (current_tap != 0xff),
					current_tap.eq(current_tap + 1)
				).Elif(self.xf_dec.o & (current_tap != 0),
					current_tap.eq(current_tap - 1)
				)
