from lib.sata.common import *

tx_to_rx = [
	("write", 1),
	("read", 1),
	("identify", 1),
	("count", 4)
]

rx_to_tx = [
	("dma_activate", 1),
	("data", 1),
	("reg_d2h", 1)
]

class SATACommandTX(Module):
	def __init__(self, transport, sector_size):
		self.sink = sink = Sink(command_tx_description(32))
		self.to_rx = to_rx = Source(tx_to_rx)
		self.from_rx = from_rx = Sink(rx_to_tx)

		###

		self.comb += [
			transport.sink.pm_port.eq(0),
			transport.sink.features.eq(0),
			transport.sink.lba.eq(sink.sector),
			transport.sink.device.eq(0xe0),
			transport.sink.count.eq(sink.count),
			transport.sink.icc.eq(0),
			transport.sink.control.eq(0),
		]

		self.fsm = fsm = FSM(reset_state="IDLE")
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
			transport.sink.stb.eq(sink.stb),
			transport.sink.sop.eq(1),
			transport.sink.eop.eq(1),
			transport.sink.type.eq(fis_types["REG_H2D"]),
			transport.sink.c.eq(1),
			transport.sink.command.eq(regs["WRITE_DMA_EXT"]),
			If(sink.stb & transport.sink.ack,
				NextState("WAIT_DMA_ACTIVATE")
			)
		)
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
				to_rx.count.eq(sink.count)
			)
		]

class SATACommandRX(Module):
	def __init__(self, transport, sector_size, max_count):
		self.source = source = Source(command_rx_description(32))
		self.to_tx = to_tx = Source(rx_to_tx)
		self.from_tx = from_tx = Sink(tx_to_rx)

		###

		cmd_fifo = SyncFIFO(command_rx_cmd_description(32), 2) # Note: ideally depth=1
		data_fifo = InsertReset(SyncFIFO(command_rx_data_description(32), sector_size*max_count//4, buffered=True))
		self.submodules += cmd_fifo, data_fifo

		def test_type(name):
			return transport.source.type == fis_types[name]

		dma_activate = Signal()

		self.fsm = fsm = FSM(reset_state="IDLE")
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
			cmd_fifo.sink.stb.eq(1),
			cmd_fifo.sink.write.eq(1),
			cmd_fifo.sink.success.eq(1),
			If(cmd_fifo.sink.stb & cmd_fifo.sink.ack,
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
			data_fifo.sink.stb.eq(transport.source.stb),
			data_fifo.sink.sop.eq(transport.source.sop),
			data_fifo.sink.eop.eq(transport.source.eop),
			data_fifo.sink.data.eq(transport.source.data),
			transport.source.ack.eq(data_fifo.sink.ack),
			If(data_fifo.sink.stb & data_fifo.sink.eop & data_fifo.sink.ack,
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
			cmd_fifo.sink.stb.eq(1),
			cmd_fifo.sink.read.eq(~identify),
			cmd_fifo.sink.identify.eq(identify),
			cmd_fifo.sink.success.eq(1),
			cmd_fifo.sink.failed.eq(0),
			If(~cmd_fifo.fifo.readable, # Note: simulate a depth=1 fifo
				If(cmd_fifo.sink.stb & cmd_fifo.sink.ack,
					If(cmd_fifo.sink.failed,
						data_fifo.reset.eq(1)
					),
					NextState("IDLE")
				)
			)
		)

		self.out_fsm = out_fsm = FSM(reset_state="IDLE")
		out_fsm.act("IDLE",
			If(cmd_fifo.source.stb & cmd_fifo.source.write,
				NextState("PRESENT_WRITE_RESPONSE"),
			).Elif(cmd_fifo.source.stb & (cmd_fifo.source.read | cmd_fifo.source.identify),
				If(cmd_fifo.source.success,
					NextState("PRESENT_READ_RESPONSE_SUCCESS"),
				).Else(
					NextState("PRESENT_READ_RESPONSE_FAILED"),
				)
			)
		)
		out_fsm.act("PRESENT_WRITE_RESPONSE",
			source.stb.eq(1),
			source.sop.eq(1),
			source.eop.eq(1),
			source.write.eq(1),
			source.success.eq(cmd_fifo.source.success),
			If(source.stb & source.ack,
				cmd_fifo.source.ack.eq(1),
				NextState("IDLE")
			)
		)
		out_fsm.act("PRESENT_READ_RESPONSE_SUCCESS",
			source.stb.eq(data_fifo.source.stb),
			source.read.eq(cmd_fifo.source.read),
			source.identify.eq(cmd_fifo.source.identify),
			source.success.eq(1),
			source.sop.eq(data_fifo.source.sop),
			source.eop.eq(data_fifo.source.eop),
			source.data.eq(data_fifo.source.data),
			data_fifo.source.ack.eq(source.ack),
			If(source.stb & source.eop & source.ack,
				cmd_fifo.source.ack.eq(1),
				NextState("IDLE")
			)
		)
		out_fsm.act("PRESENT_READ_RESPONSE_FAILED",
			source.stb.eq(1),
			source.sop.eq(1),
			source.eop.eq(1),
			source.read.eq(cmd_fifo.source.read),
			source.identify.eq(cmd_fifo.source.identify),
			source.failed.eq(1),
			If(source.stb & source.ack,
				cmd_fifo.source.ack.eq(1),
				NextState("IDLE")
			)
		)

		self.comb += [
			to_tx.dma_activate.eq(dma_activate),
		]

class SATACommand(Module):
	def __init__(self, transport, sector_size=512, max_count=4):
		if max_count*sector_size > 8192:
			raise ValueError("sector_size * max_count must be <= 8192")
		self.tx = SATACommandTX(transport, sector_size)
		self.rx = SATACommandRX(transport, sector_size, max_count)
		self.comb += [
			self.rx.to_tx.connect(self.tx.from_rx),
			self.tx.to_rx.connect(self.rx.from_tx)
		]
		self.sink, self.source = self.tx.sink, self.rx.source
