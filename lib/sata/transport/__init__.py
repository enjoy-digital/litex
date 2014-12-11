from lib.sata.std import *
from lib.sata.transport.std import *

def _encode_cmd(obj, layout, signal):
	r = []
	for k, v in sorted(layout.items()):
		start = v.word*32 + v.offset
		end = start + v.width
		r.append(signal[start:end].eq(getattr(obj, k)))
	return r

class SATATransportLayerTX(Module):
	def __init__(self, link):
		self.cmd = cmd = Sink(transport_cmd_tx_layout())
		self.data = data = Sink(transport_data_layout(32))

		###

		cmd_ndwords = max(fis_reg_h2d_cmd_len, fis_dma_setup_cmd_len, fis_data_cmd_len)
		encoded_cmd = Signal(cmd_ndwords*32)

		cnt = Signal(max=cmd_ndwords+1)
		clr_cnt = Signal()
		inc_cnt = Signal()

		cmd_len = Signal(flen(cnt))
		cmd_with_data = Signal()

		cmd_send = Signal()
		data_send = Signal()
		cmd_done = Signal()
		data_done = Signal()

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		# FSM
		fsm.act("IDLE",
			clr_cnt.eq(1),
			If(cmd.stb,
				If(cmd.type == fis_types["REG_H2D"],
					NextState("SEND_REG_H2D_CMD")
				).Elif(cmd.type == "DMA_SETUP_CMD",
					NextState("SEND_DMA_SETUP")
				).Elif(cmd.type == "DATA_CMD"),
					NextState("SEND_DATA")
				).Else(
					# XXX: Generate error to command layer?
					cmd.ack.eq(1)
				)
			)
		)
		fsm.act("SEND_REG_H2D_CMD",
			_encode_cmd(self.cmd, fis_reg_h2d_layout, encoded_cmd),
			cmd_len.eq(fis_reg_h2d_cmd_len),
			cmd_send.eq(1)
			If(ack_cmd,
				NextState.eq("ACK")
			)
		)
		fsm.act("SEND_DMA_SETUP_CMD",
			_encode_cmd(self.cmd, fis_dma_setup_layout, encoded_cmd),
			cmd_len.eq(fis_dma_setup_cmd_len),
			cmd_send.eq(1),
			If(ack_cmd,
				NextState.eq("ACK")
			)
		)
		fsm.act("SEND_DATA_CMD",
			_encode_cmd(self.cmd, fis_data_layout, encoded_cmd),
			cmd_len.eq(fis_send_data_cmd_len),
			cmd_width_data.eq(1),
			cmd_send.eq(1),
			If(cmd_done,
				NextState.eq("SEND_DATA")
			)
		)
		fsm.act("SEND_DATA",
			data_send.eq(1),
			If(data_done,
				NextState.eq("ACK")
			)
		)
		fsm.act("ACK",
			cmd.ack.eq(1),
			NextState.eq("IDLE")
		)

		cmd_cases = {}
		for i in range(cmd_ndwords):
			cmd_cases[i] = [link.sink.d.eq(encoded_cmd[32*i:32*(i+1)])]

		self.comb += \
			If(cmd_send,
				link.sink.stb.eq(1),
				link.sink.sop.eq(cnt==0),
				link.sink.eop.eq((cnt==cmd_len) & ~cmd_with_data),
				Case(cnt, cmd_cases),
				inc_cnt.eq(link.sink.ack),
				cmd_done.eq(cnt==cmd_len)
			).Elif(data_send,
				link.sink.stb.eq(data.stb),
				link.sink.sop.eq(0),
				link.sink.eop.eq(data.eop),
				link.sink.d.eq(data.d),
				data.ack.eq(link.sink.ack),
				data_done.eq(data.eop & data.ack)
			)

		self.sync += \
			If(clr_cnt,
				cnt.eq(0)
			).Elif(inc_cnt,
				cnt.eq(cnt+1)
			)

def _decode_cmd(signal, layout, obj):
	r = []
	for k, v in sorted(layout.items()):
		start = v.word*32+v.offset
		end = start+v.width
		r.append(getattr(obj, k).eq(signal[start:end]))
	return r

class SATATransportLayerRX(Module):
	def __init__(self, link):
		self.cmd = Source(transport_cmd_rx_layout())
		self.data = Source(transport_data_layout(32))

		###

		cmd_ndwords = max(fis_reg_d2h_cmd_len, fis_dma_activate_d2h_cmd_len, fis_dma_setup_cmd_len,
						fis_data_cmd_len, fis_pio_setup_d2h_len)
		encoded_cmd = Signal(cmd_ndwords*32)

		cnt = Signal(max=cmd_ndwords+1)
		clr_cnt = Signal()
		inc_cnt = Signal()

		cmd_len = Signal(flen(cnt))

		cmd_receive = Signal()
		data_receive = Signal()
		cmd_done = Signal()
		data_done = Signal()

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm

		def test_type(name):
			return link.source.d[:8] == fis_types[name]

		fsm.act("IDLE",
			If(link.source.stb & link.source.sop,
				If(test_type("REG_D2H"]),
					NextState("RECEIVE_REG_D2H_CMD")
				).Elif(test_type("DMA_ACTIVATE_D2H"),
					NextState("RECEIVE_DMA_ACTIVATE_D2H_CMD")
				).Elif(test_type("DMA_SETUP"),
					NextState("RECEIVE_DMA_SETUP_CMD"),
				).Elif(test_type("DATA"),
					NextState("RECEIVE_DATA_CMD"),
				).Elif(test_type("PIO_SETUP_D2H"),
					NextState("RECEIVE_PIO_SETUP_D2H_CMD"),
				).Else(
					# XXX: Better to ack?
					link.source.ack.eq(1)
				)
			).Else(
				link.source.ack.eq(1)
			)
		)
		fsm.act("RECEIVE_REG_D2H_CMD",
			cmd_len.eq(fis_reg_d2h_cmd_len),
			cmd_receive.eq(1),
			If(cmd_done,
				NextState("PRESENT_REG_D2H_CMD")
			)
		)
		fsm.act("PRESENT_REG_D2H_CMD",
			cmd.stb.eq(1),
			_decode_cmd(encoded_cmd, fis_reg_d2h_layout ,cmd),
			If(cmd.ack,
				NextState("IDLE")
			)
		)
		fsm.act("RECEIVE_DMA_ACTIVATE_D2H_CMD",
			cmd_len.eq(fis_dma_activate_d2h_cmd_len),
			cmd_receive.eq(1),
			If(cmd_done,
				NextState("PRESENT_DMA_ACTIVATE_D2H_CMD")
			)
		)
		fsm.act("PRESENT_DMA_ACTIVATE_D2H_CMD",
			cmd.stb.eq(1),
			_decode_cmd(encoded_cmd, fis_dma_activate_d2h_layout ,cmd),
			If(cmd.ack,
				NextState("IDLE")
			)
		)
		fsm.act("RECEIVE_DMA_SETUP_CMD",
			cmd_len.eq(fis_dma_setup_cmd_len),
			cmd_receive.eq(1),
			If(cmd_done,
				NextState("PRESENT_DMA_SETUP_CMD")
			)
		)
		fsm.act("PRESENT_DMA_SETUP_CMD",
			cmd.stb.eq(1),
			_decode_cmd(encoded_cmd, fis_pio_setup_d2h_layout ,cmd),
			If(cmd.ack,
				NextState("IDLE")
			)
		)
		fsm.act("RECEIVE_DATA_CMD",
			cmd_len.eq(fis_data_cmd_len),
			cmd_receive.eq(1),
			If(cmd_done,
				NextState("RECEIVE_DATA")
			)
		)
		fsm.act("RECEIVE_DATA",
			data_receive.eq(1),
			If(data_done,
				NextState("PRESENT_DATA_CMD")
			)
		)
		fsm.act("DECODE_DATA",
			cmd.stb.eq(1),
			_decode_cmd(encoded_cmd, fis_data_layout ,cmd),
			If(cmd.ack,
				NextState("IDLE")
			)
		)
		fsm.act("RECEIVE_PIO_SETUP_D2H_CMD",
			cmd_len.eq(fis_pio_setup_d2h_len),
			cmd_receive.eq(1),
			If(cmd_done,
				NextState("PRESENT_PIO_SETUP_D2H_CMD")
			)
		)
		fsm.act("PRESENT_PIO_SETUP_D2H_CMD",
			cmd.stb.eq(1),
			_decode_cmd(encoded_cmd, fis_pio_setup_d2h_layout ,cmd),
			If(cmd.ack,
				NextState("IDLE")
			)
		)

		cmd_cases = {}
		for i in range(cmd_ndwords):
			cmd_cases[i] = [encoded_cmd[32*i:32*(i+1)]).eq(link.source.d)]

		self.sync += \
			If(cmd_receive,
				If(link.source.stb,
					Case(cnt, cmd_cases),
					inc_cnt.eq(1),
				).Else(
					inc_cnt.eq(0)
				)
			)
		self.comb += cmd_done.eq(cnt==cmd_len)

		self.comb += \
			If(data_receive,
				data.stb.eq(link.source.stb),
				data.sop.eq(0), # XXX
				data.eop.eq(link.source.eop),
				data.d.eq(link.source.d),
				data_done.eq(link.source.stb & link.source.eop)
			)
		self.comb += link.source.ack.eq(cmd_receive | (data_receive & data.ack))

class SATATransportLayer(Module):
	def __init__(self, link):
		self.submodules.tx = SATATransportLayerTX(link)
		self.submodules.rx = SATATransportLayerRX(link)
