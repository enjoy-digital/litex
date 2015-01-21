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

		is_write = Signal()
		is_read = Signal()
		is_identify = Signal()

		self.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			sink.ack.eq(0),
			If(sink.stb & sink.sop,
				NextState("SEND_CMD")
			).Else(
				sink.ack.eq(1)
			)
		)
		self.sync += \
			If(fsm.ongoing("IDLE"),
				is_write.eq(sink.write),
				is_read.eq(sink.read),
				is_identify.eq(sink.identify),
			)

		fsm.act("SEND_CMD",
			transport.sink.stb.eq(sink.stb),
			transport.sink.sop.eq(1),
			transport.sink.eop.eq(1),
			transport.sink.c.eq(1),
			If(transport.sink.stb & transport.sink.ack,
				If(is_write,
					NextState("WAIT_DMA_ACTIVATE")
				).Else(
					sink.ack.eq(1),
					NextState("IDLE")
				)
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

			sink.ack.eq(transport.sink.ack),
			If(sink.stb & sink.ack,
				If(sink.eop,
					NextState("IDLE")
				).Elif(dwords_counter.value == (fis_max_dwords-1),
					NextState("WAIT_DMA_ACTIVATE")
				)
			)
		)
		self.comb += \
			If(fsm.ongoing("SEND_DATA"),
				transport.sink.type.eq(fis_types["DATA"]),
			).Else(
				transport.sink.type.eq(fis_types["REG_H2D"]),
				If(is_write,
					transport.sink.command.eq(regs["WRITE_DMA_EXT"])
				).Elif(is_read,
					transport.sink.command.eq(regs["READ_DMA_EXT"]),
				).Else(
					transport.sink.command.eq(regs["IDENTIFY_DEVICE"]),
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

		def test_type(name):
			return transport.source.type == fis_types[name]

		is_identify = Signal()
		is_dma_activate = Signal()
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

		read_error = Signal()
		clr_read_error = Signal()
		set_read_error = Signal()
		self.sync += \
			If(clr_read_error,
				read_error.eq(0)
			).Elif(set_read_error,
				read_error.eq(1)
			)

		self.fsm = fsm = FSM(reset_state="IDLE")
		fsm.act("IDLE",
			self.dwords_counter.reset.eq(1),
			transport.source.ack.eq(1),
			clr_d2h_error.eq(1),
			clr_read_error.eq(1),
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
				is_identify.eq(from_tx.identify)
			)
		fsm.act("WAIT_WRITE_ACTIVATE_OR_REG_D2H",
			transport.source.ack.eq(1),
			If(transport.source.stb,
				If(test_type("DMA_ACTIVATE_D2H"),
					is_dma_activate.eq(1),
				).Elif(test_type("REG_D2H"),
					set_d2h_error.eq(transport.source.status[reg_d2h_status["err"]]),
					NextState("PRESENT_WRITE_RESPONSE")
				)
			)
		)
		fsm.act("PRESENT_WRITE_RESPONSE",
			source.stb.eq(1),
			source.sop.eq(1),
			source.eop.eq(1),
			source.write.eq(1),
			source.last.eq(1),
			source.failed.eq(transport.source.error | d2h_error),
			If(source.stb & source.ack,
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

		fsm.act("PRESENT_READ_DATA",
			set_read_error.eq(transport.source.error),
			source.stb.eq(transport.source.stb),
			source.sop.eq(transport.source.sop),
			source.eop.eq(transport.source.eop),
			source.read.eq(~is_identify),
			source.identify.eq(is_identify),
			source.failed.eq(transport.source.error),
			source.last.eq(is_identify),
			source.data.eq(transport.source.data),
			transport.source.ack.eq(source.ack),
			If(source.stb & source.ack,
				self.dwords_counter.ce.eq(~read_done),
				If(source.eop,
					If(is_identify,
						NextState("IDLE")
					).Else(
						NextState("WAIT_READ_DATA_OR_REG_D2H")
					)
				)
			)
		)

		fsm.act("PRESENT_READ_RESPONSE",
			source.stb.eq(1),
			source.sop.eq(1),
			source.eop.eq(1),
			source.read.eq(1),
			source.last.eq(1),
			source.failed.eq(~read_done | read_error | d2h_error),
			If(source.stb & source.ack,
				NextState("IDLE")
			)
		)

		self.comb += [
			to_tx.dma_activate.eq(is_dma_activate),
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
