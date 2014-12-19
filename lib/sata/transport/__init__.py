from lib.sata.common import *

def _get_item(obj, name, width):
	if "_lsb" in name:
		item = getattr(obj, name.replace("_lsb", ""))[:width]
	elif "_msb" in name:
		item = getattr(obj, name.replace("_msb", ""))[width:2*width]
	else:
		item = getattr(obj, name)
	return item

def _encode_cmd(obj, description, signal):
	r = []
	for k, v in sorted(description.items()):
		start = v.dword*32 + v.offset
		end = start + v.width
		item = _get_item(obj, k, v.width)
		r.append(signal[start:end].eq(item))
	return r

class SATATransportTX(Module):
	def __init__(self, link):
		self.sink = sink = Sink(transport_tx_description(32))

		###

		cmd_ndwords = max(fis_reg_h2d_cmd_len, fis_data_cmd_len)
		encoded_cmd = Signal(cmd_ndwords*32)

		counter = Counter(max=cmd_ndwords+1)
		self.submodules += counter

		cmd_len = Signal(counter.width)
		cmd_with_data = Signal()

		cmd_send = Signal()
		data_send = Signal()
		cmd_done = Signal()

		def test_type(name):
			return sink.type == fis_types[name]

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		fsm.act("IDLE",
			counter.reset.eq(1),
			If(sink.stb & sink.sop,
				If(test_type("REG_H2D"),
					NextState("SEND_REG_H2D_CMD")
				).Elif(test_type("DATA"),
					NextState("SEND_DATA_CMD")
				).Else(
					sink.ack.eq(1)
				)
			).Else(
				sink.ack.eq(1)
			)
		)
		fsm.act("SEND_REG_H2D_CMD",
			_encode_cmd(sink, fis_reg_h2d_layout, encoded_cmd),
			cmd_len.eq(fis_reg_h2d_cmd_len-1),
			cmd_send.eq(1),
			If(cmd_done,
				sink.ack.eq(1),
				NextState("IDLE")
			)
		)
		fsm.act("SEND_DATA_CMD",
			_encode_cmd(sink, fis_data_layout, encoded_cmd),
			cmd_len.eq(fis_data_cmd_len-1),
			cmd_with_data.eq(1),
			cmd_send.eq(1),
			If(cmd_done,
				NextState("SEND_DATA")
			)
		)
		fsm.act("SEND_DATA",
			data_send.eq(1),
			sink.ack.eq(link.sink.ack),
			If(sink.stb & sink.eop & sink.ack,
				NextState("IDLE")
			)
		)

		cmd_cases = {}
		for i in range(cmd_ndwords):
			cmd_cases[i] = [link.sink.d.eq(encoded_cmd[32*i:32*(i+1)])]

		self.comb += \
			If(cmd_send,
				link.sink.stb.eq(sink.stb),
				link.sink.sop.eq(counter.value == 0),
				link.sink.eop.eq((counter.value == cmd_len) & ~cmd_with_data),
				Case(counter.value, cmd_cases),
				counter.ce.eq(sink.stb & link.sink.ack),
				cmd_done.eq((counter.value == cmd_len) & link.sink.stb & link.sink.ack)
			).Elif(data_send,
				link.sink.stb.eq(sink.stb),
				link.sink.sop.eq(0),
				link.sink.eop.eq(sink.eop),
				link.sink.d.eq(sink.data),
			)

def _decode_cmd(signal, description, obj):
	r = []
	for k, v in sorted(description.items()):
		start = v.dword*32+v.offset
		end = start+v.width
		item = _get_item(obj, k, v.width)
		r.append(item.eq(signal[start:end]))
	return r

class SATATransportRX(Module):
	def __init__(self, link):
		self.source = source = Source(transport_rx_description(32))

		###

		cmd_ndwords = max(fis_reg_d2h_cmd_len, fis_dma_activate_d2h_cmd_len, fis_data_cmd_len)
		encoded_cmd = Signal(cmd_ndwords*32)

		counter = Counter(max=cmd_ndwords+1)
		self.submodules += counter

		cmd_len = Signal(counter.width)

		cmd_receive = Signal()
		data_receive = Signal()
		cmd_done = Signal()
		data_done = Signal()

		def test_type(name):
			return link.source.d[:8] == fis_types[name]

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		data_sop = Signal()

		fsm.act("IDLE",
			counter.reset.eq(1),
			If(link.source.stb & link.source.sop,
				If(test_type("REG_D2H"),
					NextState("RECEIVE_REG_D2H_CMD")
				).Elif(test_type("DMA_ACTIVATE_D2H"),
					NextState("RECEIVE_DMA_ACTIVATE_D2H_CMD")
				).Elif(test_type("DATA"),
					NextState("RECEIVE_DATA_CMD"),
				).Else(
					link.source.ack.eq(1)
				)
			).Else(
				link.source.ack.eq(1)
			)
		)
		fsm.act("RECEIVE_REG_D2H_CMD",
			cmd_len.eq(fis_reg_d2h_cmd_len-1),
			cmd_receive.eq(1),
			If(cmd_done,
				NextState("PRESENT_REG_D2H_CMD")
			)
		)
		fsm.act("PRESENT_REG_D2H_CMD",
			source.stb.eq(1),
			source.sop.eq(1),
			source.eop.eq(1),
			_decode_cmd(encoded_cmd, fis_reg_d2h_layout, source),
			If(source.stb & source.ack,
				NextState("IDLE")
			)
		)
		fsm.act("RECEIVE_DMA_ACTIVATE_D2H_CMD",
			cmd_len.eq(fis_dma_activate_d2h_cmd_len-1),
			cmd_receive.eq(1),
			If(cmd_done,
				NextState("PRESENT_DMA_ACTIVATE_D2H_CMD")
			)
		)
		fsm.act("PRESENT_DMA_ACTIVATE_D2H_CMD",
			source.stb.eq(1),
			source.sop.eq(1),
			source.eop.eq(1),
			_decode_cmd(encoded_cmd, fis_dma_activate_d2h_layout, source),
			If(source.stb & source.ack,
				NextState("IDLE")
			)
		)
		fsm.act("RECEIVE_DATA_CMD",
			cmd_len.eq(fis_data_cmd_len-1),
			cmd_receive.eq(1),
			If(cmd_done,
				NextState("PRESENT_DATA")
			)
		)
		fsm.act("PRESENT_DATA",
			data_receive.eq(1),
			source.stb.eq(link.source.stb),
			_decode_cmd(encoded_cmd, fis_data_layout, source),
			source.sop.eq(data_sop),
			source.eop.eq(link.source.eop),
			source.data.eq(link.source.d),
			If(source.stb & source.eop & source.ack,
				NextState("IDLE")
			)
		)

		self.sync += \
			If(fsm.ongoing("RECEIVE_DATA_CMD"),
				data_sop.eq(1)
			).Elif(fsm.ongoing("PRESENT_DATA"),
				If(source.stb & source.ack,
					data_sop.eq(0)
				)
			)

		cmd_cases = {}
		for i in range(cmd_ndwords):
			cmd_cases[i] = [encoded_cmd[32*i:32*(i+1)].eq(link.source.d)]

		self.comb += \
			If(cmd_receive & link.source.stb,
				counter.ce.eq(1)
			)
		self.sync += \
			If(cmd_receive,
				Case(counter.value, cmd_cases),
			)
		self.comb += cmd_done.eq((counter.value == cmd_len) & link.source.ack)
		self.comb += link.source.ack.eq(cmd_receive | (data_receive & source.ack))

class SATATransport(Module):
	def __init__(self, link):
		self.tx = SATATransportTX(link)
		self.rx = SATATransportRX(link)
		self.sink, self.source = self.tx.sink, self.rx.source
