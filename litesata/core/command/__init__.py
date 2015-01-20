from litesata.common import *

tx_to_rx = [
	("write", 1),
	("read", 1),
	("identify", 1),
	("count", 16)
]

rx_to_tx = [
	("dma_activate", 1),
	("d2h_error", 1)
]

class LiteSATACommandTX(Module):
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
			transport.sink.data.eq(sink.data)
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
			dwords_counter.reset.eq(1),
			If(from_rx.dma_activate,
				NextState("SEND_DATA")
			).Elif(from_rx.d2h_error,
				sink.ack.eq(1),
				NextState("IDLE")
			)
		)
		fsm.act("SEND_DATA",
			dwords_counter.ce.eq(sink.stb & sink.ack),

			transport.sink.stb.eq(sink.stb),
			transport.sink.sop.eq(dwords_counter.value == 0),
			transport.sink.eop.eq((dwords_counter.value == (fis_max_dwords-1)) | sink.eop),

			transport.sink.type.eq(fis_types["DATA"]),
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
		fsm.act("SEND_IDENTIFY_CMD",
			transport.sink.stb.eq(sink.stb),
			transport.sink.sop.eq(1),
			transport.sink.eop.eq(1),
			transport.sink.type.eq(fis_types["REG_H2D"]),
			transport.sink.c.eq(1),
			transport.sink.command.eq(regs["IDENTIFY_DEVICE"]),
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

class LiteSATACommandRX(Module):
	def __init__(self, transport):
		self.source = source = Source(command_rx_description(32))
		self.to_tx = to_tx = Source(rx_to_tx)
		self.from_tx = from_tx = Sink(tx_to_rx)

		###

		cmd_buffer = Buffer(command_rx_cmd_description(32))
		cmd_buffer.sink, cmd_buffer.source = cmd_buffer.d, cmd_buffer.q
		data_buffer = InsertReset(SyncFIFO(command_rx_data_description(32), fis_max_dwords, buffered=True))
		self.submodules += cmd_buffer, data_buffer

		def test_type(name):
			return transport.source.type == fis_types[name]

		identify = Signal()
		dma_activate = Signal()
		read_ndwords = Signal(max=sectors2dwords(2**16))
		self.dwords_counter = dwords_counter = Counter(max=sectors2dwords(2**16))
		read_done = Signal()

		self.sync += \
			If(from_tx.read,
				read_ndwords.eq(from_tx.count*sectors2dwords(1)-1)
			)
		self.comb += read_done.eq(self.dwords_counter.value == read_ndwords)

		d2h_error = Signal()
		clr_d2h_error = Signal()
		set_d2h_error = Signal()
		self.sync += \
			If(clr_d2h_error,
				d2h_error.eq(0)
			).Elif(set_d2h_error,
				d2h_error.eq(1)
			)

		self.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			self.dwords_counter.reset.eq(1),
			transport.source.ack.eq(1),
			clr_d2h_error.eq(1),
			If(from_tx.write,
				NextState("WAIT_WRITE_ACTIVATE_OR_REG_D2H")
			).Elif(from_tx.read,
				NextState("WAIT_READ_DATA_OR_REG_D2H"),
			).Elif(from_tx.identify,
				NextState("WAIT_PIO_SETUP_D2H"),
			)
		)
		self.sync += \
			If(fsm.ongoing("IDLE"),
				identify.eq(from_tx.identify)
			)
		fsm.act("WAIT_WRITE_ACTIVATE_OR_REG_D2H",
			transport.source.ack.eq(1),
			If(transport.source.stb,
				If(test_type("DMA_ACTIVATE_D2H"),
					dma_activate.eq(1),
				).Elif(test_type("REG_D2H"),
					set_d2h_error.eq(transport.source.status[reg_d2h_status["err"]]),
					NextState("PRESENT_WRITE_RESPONSE")
				)
			)
		)
		fsm.act("PRESENT_WRITE_RESPONSE",
			cmd_buffer.sink.stb.eq(1),
			cmd_buffer.sink.write.eq(1),
			cmd_buffer.sink.last.eq(1),
			cmd_buffer.sink.success.eq(~transport.source.error & ~d2h_error),
			cmd_buffer.sink.failed.eq(transport.source.error | d2h_error),
			If(cmd_buffer.sink.stb & cmd_buffer.sink.ack,
				NextState("IDLE")
			)
		)
		fsm.act("WAIT_READ_DATA_OR_REG_D2H",
			transport.source.ack.eq(1),
			If(transport.source.stb,
				transport.source.ack.eq(0),
				If(test_type("DATA"),
					NextState("PRESENT_READ_DATA")
				).Elif(test_type("REG_D2H"),
					set_d2h_error.eq(transport.source.status[reg_d2h_status["err"]]),
					NextState("PRESENT_READ_RESPONSE")
				)
			)
		)
		fsm.act("WAIT_PIO_SETUP_D2H",
			transport.source.ack.eq(1),
			If(transport.source.stb,
				transport.source.ack.eq(0),
				If(test_type("PIO_SETUP_D2H"),
					NextState("PRESENT_PIO_SETUP_D2H")
				)
			)
		)
		fsm.act("PRESENT_PIO_SETUP_D2H",
			transport.source.ack.eq(1),
			If(transport.source.stb & transport.source.eop,
				NextState("WAIT_READ_DATA_OR_REG_D2H")
			)
		)

		self.comb += [
			data_buffer.sink.sop.eq(transport.source.sop),
			data_buffer.sink.eop.eq(transport.source.eop),
			data_buffer.sink.data.eq(transport.source.data)
		]
		fsm.act("PRESENT_READ_DATA",
			data_buffer.sink.stb.eq(transport.source.stb),
			transport.source.ack.eq(data_buffer.sink.ack),
			If(data_buffer.sink.stb & data_buffer.sink.ack,
				self.dwords_counter.ce.eq(~read_done),
				If(data_buffer.sink.eop,
					If(read_done & ~identify,
						NextState("WAIT_READ_DATA_OR_REG_D2H")
					).Else(
						NextState("PRESENT_READ_RESPONSE")
					)
				)
			)
		)
		read_error = Signal()
		self.sync += \
			If(fsm.before_entering("PRESENT_READ_DATA"),
				read_error.eq(1)
			).Elif(transport.source.stb & transport.source.ack & transport.source.eop,
				read_error.eq(transport.source.error)
			)
		fsm.act("PRESENT_READ_RESPONSE",
			cmd_buffer.sink.stb.eq(1),
			cmd_buffer.sink.read.eq(~identify),
			cmd_buffer.sink.identify.eq(identify),
			cmd_buffer.sink.last.eq(read_done | identify),
			cmd_buffer.sink.success.eq(~read_error & ~d2h_error),
			cmd_buffer.sink.failed.eq(read_error | d2h_error),
			If(cmd_buffer.sink.stb & cmd_buffer.sink.ack,
				If(cmd_buffer.sink.failed,
					data_buffer.reset.eq(1)
				),
				If(read_done | identify,
					NextState("IDLE")
				).Else(
					NextState("WAIT_READ_DATA_OR_REG_D2H")
				)
			)
		)

		self.out_fsm = out_fsm = FSM(reset_state="IDLE")
		out_fsm.act("IDLE",
			If(cmd_buffer.source.stb,
				If((cmd_buffer.source.read | cmd_buffer.source.identify) & cmd_buffer.source.success,
					NextState("PRESENT_RESPONSE_WITH_DATA"),
				).Else(
					NextState("PRESENT_RESPONSE_WITHOUT_DATA"),
				)
			)
		)

		self.comb += [
			source.write.eq(cmd_buffer.source.write),
			source.read.eq(cmd_buffer.source.read),
			source.identify.eq(cmd_buffer.source.identify),
			source.last.eq(cmd_buffer.source.last),
			source.success.eq(cmd_buffer.source.success),
			source.failed.eq(cmd_buffer.source.failed),
			source.data.eq(data_buffer.source.data)
		]

		out_fsm.act("PRESENT_RESPONSE_WITH_DATA",
			source.stb.eq(data_buffer.source.stb),
			source.sop.eq(data_buffer.source.sop),
			source.eop.eq(data_buffer.source.eop),

			data_buffer.source.ack.eq(source.ack),

			If(source.stb & source.eop & source.ack,
				cmd_buffer.source.ack.eq(1),
				NextState("IDLE")
			)
		)
		out_fsm.act("PRESENT_RESPONSE_WITHOUT_DATA",
			source.stb.eq(1),
			source.sop.eq(1),
			source.eop.eq(1),
			If(source.stb & source.ack,
				cmd_buffer.source.ack.eq(1),
				NextState("IDLE")
			)
		)

		self.comb += [
			to_tx.dma_activate.eq(dma_activate),
			to_tx.d2h_error.eq(d2h_error)
		]

class LiteSATACommand(Module):
	def __init__(self, transport):
		self.tx = LiteSATACommandTX(transport)
		self.rx = LiteSATACommandRX(transport)
		self.comb += [
			self.rx.to_tx.connect(self.tx.from_rx),
			self.tx.to_rx.connect(self.rx.from_tx)
		]
		self.sink, self.source = self.tx.sink, self.rx.source
