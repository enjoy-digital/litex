from migen.fhdl.std import *
from migen.genlib.fsm import FSM, NextState

from lib.sata.std import *
from lib.sata.transport.std import *

regs = {
	"WRITE_DMA_EXT"			: 0x35,
	"READ_DMA_EXT"			: 0x25,
	"IDENTIFY_DEVICE_DMA"	: 0xEE
}

from_rx = [
	("dma_activate", 1)
]

class SATACommandTX(Module):
	def __init__(self, transport):
		self.sink = sink = Sink(command_tx_layout(32))
		self.from_rx = Sink(from_rx)

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
		fsm.act("WAIT_DMA_ACTIVATE",
			If(self.from_rx.dma_activate,
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

class SATACommandRX(Module):
	def __init__(self, transport):
		self.source = source = Source(command_tx_layout(32))
		self.to_tx = Source(from_rx)

		###

		self.comb += [
			transport.source.ack.eq(1),
			# XXX for test
			If(transport.source.stb & (transport.source.type == fis_types["DMA_ACTIVATE_D2H"]),
				self.to_tx.dma_activate.eq(1)
			),
			If(transport.source.stb & (transport.source.type == fis_types["DATA"]),
				source.stb.eq(1),
				source.sop.eq(transport.source.sop),
				source.eop.eq(transport.source.eop),
				source.data.eq(transport.source.data),
			)
		]

class SATACommand(Module):
	def __init__(self, transport):
		self.submodules.tx = SATACommandTX(transport)
		self.submodules.rx = SATACommandRX(transport)
		self.sink, self.source = self.tx.sink, self.rx.source
		self.comb += self.rx.to_tx.connect(self.tx.from_rx)
