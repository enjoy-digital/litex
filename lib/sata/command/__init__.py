from migen.fhdl.std import *
from migen.genlib.fsm import FSM, NextState

from lib.sata.common import *

tx_to_rx = [
	("write", 1),
	("read", 1),
	("identify", 1)
]

rx_to_tx = [
	("dma_activate", 1),
	("data", 1),
	("reg_d2h", 1)
]

class SATACommandTX(Module):
	def __init__(self, transport):
		self.sink = sink = Sink(command_tx_description(32))
		self.to_rx = to_rx = Source(tx_to_rx)
		self.from_rx = from_rx = Sink(rx_to_tx)

		###

		self.comb += [
			transport.sink.pm_port.eq(0),
			transport.sink.features.eq(0),
			transport.sink.lba.eq(sink.address),  # XXX need adaptation?
			transport.sink.device.eq(0xe0),
			transport.sink.count.eq(sink.length), # XXX need adaptation?
			transport.sink.icc.eq(0),
			transport.sink.control.eq(0),
		]

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("IDLE",
			If(sink.stb & sink.sop,
				If(sink.write,
					NextState("SEND_WRITE_DMA_CMD")
				).Elif(sink.read,
					NextState("SEND_READ_DMA_CMD")
				).Elif(sink.identify,
					NextState("SEND_IDENTIFY_CMD")
				).Else(
					sink.ack.eq(1)
				)
			).Else(
				sink.ack.eq(1)
			)
		)
		fsm.act("SEND_WRITE_DMA_CMD",
			transport.sink.stb.eq(1),
			transport.sink.sop.eq(1),
			transport.sink.eop.eq(1),
			transport.sink.type.eq(fis_types["REG_H2D"]),
			transport.sink.c.eq(1),
			transport.sink.command.eq(regs["WRITE_DMA_EXT"]),
			If(transport.sink.ack,
				NextState("WAIT_DMA_ACTIVATE")
			)
		)
		# XXX: split when length > 2048 dwords
		fsm.act("WAIT_DMA_ACTIVATE",
			If(from_rx.dma_activate,
				NextState("SEND_DATA")
			)
		)
		fsm.act("SEND_DATA",
			transport.sink.stb.eq(sink.stb),
			transport.sink.sop.eq(sink.sop),
			transport.sink.eop.eq(sink.eop),
			transport.sink.type.eq(fis_types["DATA"]),
			transport.sink.data.eq(sink.data),
			sink.ack.eq(transport.sink.ack),
			If(sink.stb & sink.ack & sink.eop,
				NextState("IDLE")
			)
		)
		fsm.act("SEND_READ_DMA_CMD",
			transport.sink.stb.eq(sink.stb),
			transport.sink.sop.eq(1),
			transport.sink.eop.eq(1),
			transport.sink.type.eq(fis_types["REG_H2D"]),
			transport.sink.c.eq(1),
			transport.sink.command.eq(regs["READ_DMA_EXT"]),
			sink.ack.eq(transport.sink.ack),
			If(sink.stb & sink.ack,
				NextState("IDLE")
			)
		)
		fsm.act("SEND_IDENTIFY_CMD",
			transport.sink.stb.eq(sink.stb),
			transport.sink.sop.eq(1),
			transport.sink.eop.eq(1),
			transport.sink.type.eq(fis_types["REG_H2D"]),
			transport.sink.c.eq(1),
			transport.sink.command.eq(regs["IDENTIFY_DEVICE_DMA"]),
			sink.ack.eq(transport.sink.ack),
			If(sink.stb & sink.ack,
				NextState("IDLE")
			)
		)

		self.comb += [
			If(sink.stb,
				to_rx.write.eq(sink.write),
				to_rx.read.eq(sink.read),
				to_rx.identify.eq(sink.identify),
			)
		]

class SATACommandRX(Module):
	def __init__(self, transport):
		self.source = source = Source(command_rx_description(32))
		self.to_tx = to_tx = Source(rx_to_tx)
		self.from_tx = from_tx = Sink(tx_to_rx)

		###

		def test_type(name):
			return transport.source.type == fis_types[name]

		dma_activate = Signal()

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("IDLE",
			transport.source.ack.eq(1),
			If(from_tx.write,
				NextState("WAIT_WRITE_ACTIVATE")
			).Elif(from_tx.read | from_tx.identify,
				NextState("WAIT_READ_DATA")
			)
		)
		identify = Signal()
		self.sync += \
			If(fsm.ongoing("IDLE"),
				identify.eq(from_tx.identify)
			)
		fsm.act("WAIT_WRITE_ACTIVATE",
			transport.source.ack.eq(1),
			If(transport.source.stb,
				If(test_type("DMA_ACTIVATE_D2H"),
					dma_activate.eq(1),
					NextState("WAIT_WRITE_REG_D2H")
				)
			)
		)
		fsm.act("WAIT_WRITE_REG_D2H",
			transport.source.ack.eq(1),
			If(transport.source.stb,
				If(test_type("REG_D2H"),
					NextState("PRESENT_WRITE_RESPONSE")
				)
			)
		)
		fsm.act("PRESENT_WRITE_RESPONSE",
			source.stb.eq(1),
			source.sop.eq(1),
			source.eop.eq(1),
			source.write.eq(1),
			source.success.eq(1),
			If(source.ack,
				NextState("IDLE")
			)
		)
		fsm.act("WAIT_READ_DATA",
			transport.source.ack.eq(1),
			If(transport.source.stb,
				transport.source.ack.eq(0),
				If(test_type("DATA"),
					NextState("PRESENT_READ_DATA")
				)
			)
		)
		fsm.act("PRESENT_READ_DATA",
			source.stb.eq(transport.source.stb),
			source.read.eq(~identify),
			source.identify.eq(identify),
			source.sop.eq(transport.source.sop),
			source.eop.eq(transport.source.eop),
			source.data.eq(transport.source.data),
			transport.source.ack.eq(source.ack),
			If(source.stb & source.eop & source.ack,
				NextState("WAIT_READ_REG_D2H")
			)
		)
		fsm.act("WAIT_READ_REG_D2H",
			transport.source.ack.eq(1),
			If(transport.source.stb,
				If(test_type("REG_D2H"),
					NextState("PRESENT_READ_RESPONSE")
				)
			)
		)
		fsm.act("PRESENT_READ_RESPONSE",
			source.stb.eq(1),
			source.sop.eq(1),
			source.eop.eq(1),
			source.read.eq(~identify),
			source.identify.eq(identify),
			source.success.eq(1),
			If(source.ack,
				NextState("IDLE")
			)
		)

		self.comb += [
			to_tx.dma_activate.eq(dma_activate),
		]

class SATACommand(Module):
	def __init__(self, transport):
		self.submodules.tx = SATACommandTX(transport)
		self.submodules.rx = SATACommandRX(transport)
		self.comb += [
			self.rx.to_tx.connect(self.tx.from_rx),
			self.tx.to_rx.connect(self.rx.from_tx)
		]
		self.sink, self.source = self.tx.sink, self.rx.source
