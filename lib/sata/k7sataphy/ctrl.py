from migen.fhdl.std import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.fsm import FSM, NextState

# Todo:
# rx does not use the same clock, need to resynchronize signals.

def us(self, t, speed="SATA3", margin=True):
	clk_freq = {
		"SATA3" :	300*1000000,
		"SATA2" :	150*1000000,
		"SATA1" :	 75*1000000
	}
	clk_period_us = 1000000/clk_freq
	if margin:
		t += clk_period_us/2
	return ceil(t/clk_period_us)

class K7SATAPHYHostCtrl(Module):
	def __init__(self, gtx):
		self.link_up = Signal()
		self.speed = Signal(3)

		self.txdata = Signal(32)
		self.txcharisk = Signal(4)

		self.rxdata = Signal(32)

		align_timeout = Signal()
		align_detect = Signal()

		txcominit = Signal()
		txcomwake = Signa()

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("RESET",
			txcominit.eq(1),
			gtx.txelecidle.eq(1),
			If(gtx.txcomfinish & ~gtx.rxcominitdet),
				NextState("AWAIT_COMINIT")
			)
		)
		fsm.act("AWAIT_COMINIT",
			gtx.txelecidle.eq(1),
			If(gtx.rxcominitdet,
				NextState("AWAIT_NO_COMINIT")
			).Else(
				If(retry_cnt == 0,
					NextState("RESET")
				)
			)
		)
		fsm.act("AWAIT_NO_COMINIT",
			gtx.txelecidle.eq(1),
			If(~gtx.rxcominitdet,
				NextState("CALIBRATE")
			)
		)
		fsm.act("CALIBRATE",
			gtx.txelecidle.eq(1),
			NextState("COMWAKE")
		)
		fsm.act("COMWAKE",
			gtx.txelecidle.eq(1),
			txcomwake.eq(1),
			If(gtx.txcomfinish,
				NextState("AWAIT_COMWAKE")
			)
		)
		fsm.act("AWAIT_COMWAKE",
			gtx.txelecidle.eq(1),
			If(gtx.rxcomwakedet,
				NextState("AWAIT_NO_COMWAKE")
			).Else(
				If(retry_cnt == 0,
					NextState("RESET")
				)
			)
		)
		fsm.act("AWAIT_NO_COMWAKE",
			gtx.txelecidle.eq(1),
			If(~gtx.rxcomwakedet,
				NextState("AWAIT_ALIGN")
			)
		)
		fsm.act("AWAIT_ALIGN",
			gtx.txelecidle.eq(0),
			self.txdata.eq(0x4A4A4A4A), #D10.2
			self.txcharisk.eq(0b0000),
			If(align_detect & ~align_timeout,
				NextState("SEND_ALIGN")
			).Elif(~align_detect & align_timeout,
				NextState("RESET")
			)
		)
		fsm.act("SEND_ALIGN",
			gtx.txelecidle.eq(0),
			self.txdata.eq(ALIGN_VAL),
			self.txcharisk.eq(0b0001),
			If(non_align_cnt == 3,
				NextState("READY")
			)
		)
		fsm.act("READY",
			gtx.txelecidle.eq(0),
			self.txdata.eq(SYNC_VAL),
			self.txcharisk.eq(0b0001),
			If(gtx.rxelecidle,
				NextState("RESET")
			),
			self.link_up.eq(1)
		)

		txcominit_d = Signal()
		txcomwake_d = Signal()
		self.sync.sata += [
			gtx.txcominit.eq(txcominit & ~txcominit_d),
			gtx.txcomwake.eq(txcomwake & ~txcomwake),
		]
		self.comb +=  align_detect.eq(self.rxdata == ALIGN_VAL);

		align_timeout_cnt = Signal(16)
		self.sync.sata += \
			If(fsm.ongoing("RESET"),
				If(speed == 0b100,
					align_timeout_cnt.eq(us(873, "SATA3"))
				).Elif(speed == 0b010,
					align_timeout_cnt.eq(us(873, "SATA2"))
				).Else(
					align_timeout_cnt.eq(us(873, "SATA1"))
				)
			).Elif(fsm.ongoing("AWAIT_ALIGN"),
				align_timeout_cnt.eq(align_timeout_cnt-1)
			)
		self.comb += align_timeout.eq(align_timeout_cnt == 0)

		retry_cnt = Signal(16)
		self.sync.sata += \
			If(fsm.ongoing("RESET") | fsm.ongoing("AWAIT_NO_COMINIT"),
				If(speed == 0b100,
					retry_cnt.eq(us(10000, "SATA3"))
				).Elif(speed == 0b010,
					retry_cnt.eq(us(10000, "SATA2"))
				).Else(
					retry_cnt.eq(us(10000, "SATA1"))
				)
			).Elif(fsm.ongoing("AWAIT_COMINIT") | fsm.ongoing("AWAIT_COMWAKE")
				retry_cnt.eq(retry_cnt-1)
			)

		non_align_cnt = Signal(4)
		self.sync.sata += \
			If(fsm.ongoing("SEND_ALIGN"),
				If(self.rxdata[7:0] == K28_5,
					non_align_cnt.eq(non_align_cnt + 1)
				).Else(
					non_align_cnt.eq(0)
				)
			)

class K7SATAPHYDeviceCtrl(Module):
	def __init__(self, gtx):
		self.link_up = Signal()
		self.speed = Signal(3)

		self.txdata = Signal(32)
		self.txcharisk = Signal(4)

		self.rxdata = Signal(32)

		align_timeout = Signal()
		align_detect = Signal()

		txcominit = Signal()
		txcomwake = Signa()

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("RESET",
			gtx.txelecidle.eq(1),
			If(gtx.rxcominitdet,
				NextState("AWAIT_COMINIT")
			)
		)
		fsm.act("COMINIT",
			gtx.txelecidle.eq(1),
			If(gtx.txcomfinish,
				NextState("AWAIT_COMWAKE")
			)
		)
		fsm.act("AWAIT_COMWAKE",
			gtx.txelecidle.eq(1),
			If(gtx.rxcomwake,
				NextState("AWAIT_NO_COMWAKE")
			).Else(
				If(retry_cnt == 0,
					NextState("RESET")
				)
			)
		)
		fsm.act("AWAIT_NO_COMWAKE",
			gtx.txelecidle.eq(1),
			If(~gtx.rxcomwake,
				NextState("CALIBRATE")
			)
		)
		fsm.act("CALIBRATE",
			gtx.txelecidle.eq(1),
			NextState("COMWAKE")
		)
		fsm.act("COMWAKE",
			gtx.txelecidle.eq(1),
			If(gtx.txcomfinish,
				NextState("SEND_ALIGN")
			).Elif(align_timeout,
				NextState("ERROR")
			)
		)
		fsm.act("SEND_ALIGN",
			gtx.txelecidle.eq(0),
			self.txdata.eq(ALIGN_VAL),
			self.txcharisk.eq(0b0001),
			If(align_detect,
				NextState("READY")
			).Elsif(align_timeout,
				NextState("ERROR")
			)
		)
		fsm.act("READY",
			self.txdata.eq(SYNC_VAL),
			self.txcharisk.eq(0b0001),
			gtx.txelecidle.eq(0),
			NextState("READY"),
			If(gtx.rxelecidle,
				NextState("RESET")
			),
			self.link_up.eq(1)
		)
		fsm.act("ERROR",
			gtx.txelecidle.eq(1),
			NextState("RESET")
		)

		txcominit_d = Signal()
		txcomwake_d = Signal()
		self.sync.sata += [
			gtx.txcominit.eq(txcominit & ~txcominit_d),
			gtx.txcomwake.eq(txcomwake & ~txcomwake),
		]
		self.comb +=  align_detect.eq(self.rxdata == ALIGN_VAL);

		align_timeout_cnt = Signal(16)
		self.sync.sata += \
			If(fsm.ongoing("RESET"),
				If(speed == 0b100,
					align_timeout_cnt.eq(us(55, "SATA3"))
				).Elif(speed == 0b010,
					align_timeout_cnt.eq(us(55, "SATA2"))
				).Else(
					align_timeout_cnt.eq(us(55, "SATA1"))
				)
			).Elif(fsm.ongoing("AWAIT_ALIGN"),
				align_timeout_cnt.eq(align_timeout_cnt-1)
			)
		self.comb += align_timeout.eq(align_timeout_cnt == 0)