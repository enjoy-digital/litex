from lib.sata.common import *

tx_to_rx = [
	("write", 1),
	("read", 1),
	("count", 16)
]

rx_to_tx = [
	("dma_activate", 1)
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
			transport.sink.lba.eq(sink.sector),
			transport.sink.device.eq(0xe0),
			transport.sink.count.eq(sink.count),
			transport.sink.icc.eq(0),
			transport.sink.control.eq(0),
		]

		self.dwords_counter = dwords_counter = Counter(max=fis_max_dwords)

		self.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			sink.ack.eq(0),
			If(sink.stb & sink.sop,
				If(sink.write,
					NextState("SEND_WRITE_DMA_CMD")
				).Elif(sink.read,
					NextState("SEND_READ_DMA_CMD")
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
			dwords_counter.reset.eq(1),
			If(from_rx.dma_activate,
				NextState("SEND_DATA")
			)
		)
		fsm.act("SEND_DATA",
			dwords_counter.ce.eq(sink.stb & sink.ack),

			transport.sink.stb.eq(sink.stb),
			transport.sink.sop.eq(dwords_counter.value == 0),
			transport.sink.eop.eq((dwords_counter.value == (fis_max_dwords-1)) | sink.eop),

			transport.sink.type.eq(fis_types["DATA"]),
			transport.sink.data.eq(sink.data),
			sink.ack.eq(transport.sink.ack),
			If(sink.stb & sink.ack,
				If(sink.eop,
					NextState("IDLE")
				).Elif(dwords_counter.value == (fis_max_dwords-1),
					NextState("WAIT_DMA_ACTIVATE")
				)
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

		self.comb += [
			If(sink.stb,
				to_rx.write.eq(sink.write),
				to_rx.read.eq(sink.read),
				to_rx.count.eq(sink.count)
			)
		]

class SATACommandRX(Module):
	def __init__(self, transport):
		self.source = source = Source(command_rx_description(32))
		self.to_tx = to_tx = Source(rx_to_tx)
		self.from_tx = from_tx = Sink(tx_to_rx)

		###

		cmd_fifo = SyncFIFO(command_rx_cmd_description(32), 2) # Note: ideally depth of 1
		# XXX Simulate a fifo with depth of 1, FIXME
		cmd_fifo_sink_stb = Signal()
		cmd_fifo_sink_ack = Signal()
		self.comb += [
			cmd_fifo.sink.stb.eq(cmd_fifo_sink_stb & ~cmd_fifo.fifo.readable),
			cmd_fifo_sink_ack.eq(~cmd_fifo.fifo.readable)
		]
		data_fifo = InsertReset(SyncFIFO(command_rx_data_description(32), fis_max_dwords, buffered=True))
		self.submodules += cmd_fifo, data_fifo

		def test_type(name):
			return transport.source.type == fis_types[name]

		dma_activate = Signal()
		read_ndwords = Signal(max=sectors2dwords(2**16))
		self.dwords_counter = dwords_counter = Counter(max=sectors2dwords(2**16))
		read_done = Signal()

		self.sync += \
			If(from_tx.read,
				read_ndwords.eq(from_tx.count*sectors2dwords(1)-1)
			)
		self.comb += read_done.eq(self.dwords_counter.value == read_ndwords)

		self.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			self.dwords_counter.reset.eq(1),
			transport.source.ack.eq(1),
			If(from_tx.write,
				NextState("WAIT_WRITE_ACTIVATE_OR_REG_D2H")
			).Elif(from_tx.read,
				NextState("WAIT_READ_DATA")
			)
		)
		fsm.act("WAIT_WRITE_ACTIVATE_OR_REG_D2H",
			# XXX: use status and error fields of REG_D2H
			transport.source.ack.eq(1),
			If(transport.source.stb,
				If(test_type("DMA_ACTIVATE_D2H"),
					dma_activate.eq(1),
				).Elif(test_type("REG_D2H"),
					NextState("PRESENT_WRITE_RESPONSE")
				)
			)
		)
		fsm.act("PRESENT_WRITE_RESPONSE",
			cmd_fifo_sink_stb.eq(1),
			cmd_fifo.sink.write.eq(1),
			cmd_fifo.sink.last.eq(1),
			cmd_fifo.sink.success.eq(~transport.source.error),
			cmd_fifo.sink.failed.eq(transport.source.error),
			If(cmd_fifo_sink_stb & cmd_fifo_sink_ack,
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
			If(data_fifo.sink.stb & data_fifo.sink.ack,
				self.dwords_counter.ce.eq(~read_done),
				If(data_fifo.sink.eop,
					If(read_done,
						NextState("WAIT_READ_REG_D2H")
					).Else(
						NextState("PRESENT_READ_RESPONSE")
					)
				)
			)
		)
		read_error = Signal()
		self.sync += \
			If(fsm.ongoing("WAIT_READ_DATA"),
				read_error.eq(1)
			).Elif(transport.source.stb & transport.source.ack & transport.source.eop,
				read_error.eq(transport.source.error)
			)
		fsm.act("WAIT_READ_REG_D2H",
			# XXX: use status and error fields of REG_D2H
			transport.source.ack.eq(1),
			If(transport.source.stb,
				If(test_type("REG_D2H"),
					NextState("PRESENT_READ_RESPONSE")
				)
			)
		)
		fsm.act("PRESENT_READ_RESPONSE",
			cmd_fifo_sink_stb.eq(1),
			cmd_fifo.sink.read.eq(1),
			cmd_fifo.sink.last.eq(read_done),
			cmd_fifo.sink.success.eq(~read_error),
			cmd_fifo.sink.failed.eq(read_error),
			If(cmd_fifo_sink_stb & cmd_fifo_sink_ack,
				If(cmd_fifo.sink.failed,
					data_fifo.reset.eq(1)
				),
				If(read_done,
					NextState("IDLE")
				).Else(
					NextState("WAIT_READ_DATA")
				)
			)
		)

		self.out_fsm = out_fsm = FSM(reset_state="IDLE")
		out_fsm.act("IDLE",
			If(cmd_fifo.source.stb & cmd_fifo.source.write,
				NextState("PRESENT_WRITE_RESPONSE"),
			).Elif(cmd_fifo.source.stb & (cmd_fifo.source.read),
				If(cmd_fifo.source.success,
					NextState("PRESENT_READ_RESPONSE_SUCCESS"),
				).Else(
					NextState("PRESENT_READ_RESPONSE_FAILED"),
				)
			)
		)
		# XXX try to merge PRESENT_XXX states
		out_fsm.act("PRESENT_WRITE_RESPONSE",
			source.stb.eq(1),
			source.sop.eq(1),
			source.eop.eq(1),
			source.write.eq(1),
			source.last.eq(cmd_fifo.source.last),
			source.success.eq(cmd_fifo.source.success),
			If(source.stb & source.ack,
				cmd_fifo.source.ack.eq(1),
				NextState("IDLE")
			)
		)
		out_fsm.act("PRESENT_READ_RESPONSE_SUCCESS",
			source.stb.eq(data_fifo.source.stb),
			source.read.eq(cmd_fifo.source.read),
			source.success.eq(1),
			source.last.eq(cmd_fifo.source.last),
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
			source.last.eq(cmd_fifo.source.last),
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
	def __init__(self, transport):
		self.tx = SATACommandTX(transport)
		self.rx = SATACommandRX(transport)
		self.comb += [
			self.rx.to_tx.connect(self.tx.from_rx),
			self.tx.to_rx.connect(self.rx.from_tx)
		]
		self.sink, self.source = self.tx.sink, self.rx.source
