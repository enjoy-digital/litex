from migen.fhdl.std import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.fsm import FSM, NextState

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

		tx_com_done = Signal()
		align_timeout = Signal()
		align_detect = Signal()

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("RESET",
			gtx.txcominit.eq(1),
			gtx.txelecidle.eq(1),
			If(tx_com_done & ~gtx.rxcominitdet),
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
			gtx.txcomwake.eq(1),
			If(tx_com_done,
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
			gtx.txdata.eq(0x4A4A), #D10.2
			gtx.txcharisk.eq(0b0000),
			If(align_detect & ~align_timeout,
				NextState("SEND_ALIGN")
			).Elif(~align_detect & align_timeout,
				NextState("RESET")
			)
		)
		fsm.act("SEND_ALIGN",
			gtx.txelecidle.eq(0),
			gtx.txdata.eq(ALIGN_VAL),
			gtx.txcharisk.eq(0b0001),
			If(non_align_cnt == 3,
				NextState("READY")
			)
		)
		fsm.act("READY",
			gtx.txelecidle.eq(0),
			gtx.txdata.eq(SYNC_VAL),
			gtx.txcharisk.eq(0b0001),
			If(gtx.rxelecidle,
				NextState("RESET")
			),
			self.link_up.eq(1)
		)

class K7SATAPHYDeviceCtrl(Module):
	def __init__(self, gtx):
