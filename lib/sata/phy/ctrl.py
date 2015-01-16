from math import ceil

from lib.sata.common import *

def us(t, clk_freq):
	clk_period_us = 1000000/clk_freq
	return ceil(t/clk_period_us)

class SATAPHYHostCtrlTimeout(Module):
	def __init__(self, load):
		self.load = Signal()
		self.dec = Signal()
		self.reached = Signal()

		cnt = Signal(max=load+1)
		self.sync += \
			If(self.load,
				cnt.eq(load)
			).Elif(self.dec & ~self.reached,
				cnt.eq(cnt-1)
			)
		self.comb += self.reached.eq(cnt == 0)

class SATAPHYHostCtrl(Module):
	def __init__(self, trx, crg, clk_freq):
		self.ready = Signal()
		self.need_reset = Signal()
		self.sink = sink = Sink(phy_description(32))
		self.source = source = Source(phy_description(32))

		###
		self.comb += [
			source.stb.eq(1),
			sink.ack.eq(1)
		]

		retry_timeout = SATAPHYHostCtrlTimeout(us(10000, clk_freq))
		align_timeout = SATAPHYHostCtrlTimeout(us(873, clk_freq))
		self.submodules += align_timeout, retry_timeout

		align_detect = Signal()
		non_align_cnt = Signal(4)

		self.fsm = fsm = FSM(reset_state="RESET")
		fsm.act("RESET",
			trx.tx_idle.eq(1),
			retry_timeout.load.eq(1),
			align_timeout.load.eq(1),
			If(crg.ready,
				NextState("COMINIT")
			),
		)
		fsm.act("COMINIT",
			trx.tx_idle.eq(1),
			trx.tx_cominit_stb.eq(1),
			If(trx.tx_cominit_ack & ~trx.rx_cominit_stb,
				NextState("AWAIT_COMINIT")
			),
		)
		fsm.act("AWAIT_COMINIT",
			trx.tx_idle.eq(1),
			retry_timeout.dec.eq(1),
			If(trx.rx_cominit_stb,
				NextState("AWAIT_NO_COMINIT")
			).Else(
				If(retry_timeout.reached,
					NextState("RESET")
				)
			),
		)
		fsm.act("AWAIT_NO_COMINIT",
			trx.tx_idle.eq(1),
			retry_timeout.load.eq(1),
			If(~trx.rx_cominit_stb,
				NextState("CALIBRATE")
			),
		)
		fsm.act("CALIBRATE",
			trx.tx_idle.eq(1),
			NextState("COMWAKE"),
		)
		fsm.act("COMWAKE",
			trx.tx_idle.eq(1),
			trx.tx_comwake_stb.eq(1),
			If(trx.tx_comwake_ack,
				NextState("AWAIT_COMWAKE")
			),
		)
		fsm.act("AWAIT_COMWAKE",
			trx.tx_idle.eq(1),
			retry_timeout.dec.eq(1),
			If(trx.rx_comwake_stb,
				NextState("AWAIT_NO_COMWAKE")
			).Else(
				If(retry_timeout.reached,
					NextState("RESET")
				)
			),
		)
		fsm.act("AWAIT_NO_COMWAKE",
			trx.tx_idle.eq(1),
			If(~trx.rx_comwake_stb,
				NextState("AWAIT_NO_RX_IDLE")
			),
		)
		fsm.act("AWAIT_NO_RX_IDLE",
			trx.tx_idle.eq(0),
			source.data.eq(0x4A4A4A4A), #D10.2
			source.charisk.eq(0b0000),
			If(~trx.rx_idle,
				NextState("AWAIT_ALIGN"),
				crg.reset.eq(1),
				trx.pmarxreset.eq(1)
			),
		)
		fsm.act("AWAIT_ALIGN",
			trx.tx_idle.eq(0),
			source.data.eq(0x4A4A4A4A), #D10.2
			source.charisk.eq(0b0000),
			trx.rx_align.eq(1),
			align_timeout.dec.eq(1),
			If(align_detect & ~trx.rx_idle,
				NextState("SEND_ALIGN")
			).Elif(align_timeout.reached,
				NextState("RESET")
			),
		)
		fsm.act("SEND_ALIGN",
			trx.tx_idle.eq(0),
			trx.rx_align.eq(1),
			source.data.eq(primitives["ALIGN"]),
			source.charisk.eq(0b0001),
			If(non_align_cnt == 3,
				NextState("READY")
			),
		)
		fsm.act("READY",
			trx.tx_idle.eq(0),
			trx.rx_align.eq(1),
			source.data.eq(primitives["SYNC"]),
			source.charisk.eq(0b0001),
			If(trx.rx_idle,
				NextState("RESET")
			),
			self.ready.eq(1),
		)

		self.reset_timeout = Timeout(clk_freq//16)
		self.comb += [
			self.reset_timeout.ce.eq(~self.ready),
			self.need_reset.eq(self.reset_timeout.reached)
		]

		self.comb +=  \
			align_detect.eq(self.sink.stb & (self.sink.data == primitives["ALIGN"]))
		self.sync += \
			If(fsm.ongoing("SEND_ALIGN"),
				If(sink.stb,
					If(sink.data[0:8] == 0x7C,
						non_align_cnt.eq(non_align_cnt + 1)
					).Else(
						non_align_cnt.eq(0)
					)
				)
			)
