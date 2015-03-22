from migen.fhdl.std import *
from migen.actorlib.structuring import *
from migen.genlib.fsm import FSM, NextState

from misoclib.com.liteusb.common import *

class LiteUSBPacketizer(Module):
	def __init__(self):
		self.sink = sink = Sink(user_layout)
		self.source = source = Source(phy_layout)

		# Packet description
		#   - preamble : 4 bytes
		#   - dst      : 1 byte
		#   - length   : 4 bytes
		#   - payload
		header = [
			# preamble
			0x5A,
			0xA5,
			0x5A,
			0xA5,
			# dst
			sink.dst,
			# length
			sink.length[24:32],
			sink.length[16:24],
			sink.length[8:16],
			sink.length[0:8],
		]

		header_unpack = Unpack(len(header), phy_layout)
		self.submodules += header_unpack

		for i, byte in enumerate(header):
			chunk = getattr(header_unpack.sink.payload, "chunk" + str(i))
			self.comb += chunk.d.eq(byte)

		fsm = FSM()
		self.submodules += fsm

		fsm.act("WAIT_SOP",
			If(sink.stb & sink.sop, NextState("SEND_HEADER"))
		)

		fsm.act("SEND_HEADER",
			header_unpack.sink.stb.eq(1),
			source.stb.eq(1),
			source.d.eq(header_unpack.source.d),
			header_unpack.source.ack.eq(source.ack),
			If(header_unpack.sink.ack, NextState("SEND_DATA"))
		)

		fsm.act("SEND_DATA",
			source.stb.eq(sink.stb),
			source.d.eq(sink.d),
			sink.ack.eq(source.ack),
			If(source.ack & sink.eop, NextState("WAIT_SOP"))
		)

#
# TB
#
src_data = [
	(0x01, 4,
		[0x0, 0x1, 0x2, 0x3]
	),
	(0x16, 8,
		[0x0, 0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0x7]
	),
	(0x22, 16,
		[0x0, 0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0x7, 0x8, 0x9, 0xA, 0xB, 0xC, 0xD, 0xE, 0xF]
	),
]

class PacketizerSourceModel(Module, Source, RandRun):
	def __init__(self, data):
		Source.__init__(self, user_layout, True)
		RandRun.__init__(self, 25)
		self.data = data

		self._stb = 0
		self._sop = 0
		self._eop = 0
		self._frame_cnt = 0
		self._payload_cnt = 0

	def do_simulation(self, selfp):
		RandRun.do_simulation(self, selfp)
		dst, length, payload = self.data[self._frame_cnt]

		if selfp.stb and selfp.ack:
			if self._payload_cnt == length-1:
				self._frame_cnt += 1
				self._payload_cnt = 0
			else:
				self._payload_cnt += 1
			if self.run:
				self._stb = 1
			else:
				self._stb = 0

		if self.run and not self._stb:
			self._stb = 1

		self._sop = int((self._payload_cnt == 0))
		self._eop = int((self._payload_cnt == length-1))

		selfp.stb = self._stb
		selfp.sop = self._sop & self._stb
		selfp.eop = self._eop & self._stb
		selfp.dst = dst
		selfp.length = length
		selfp.d = payload[self._payload_cnt]

		if self._frame_cnt == len(self.data):
			raise StopSimulation

class PacketizerSinkModel(Module, Sink, RandRun):
	def __init__(self):
		Sink.__init__(self, phy_layout)
		RandRun.__init__(self, 25)

	def do_simulation(self, selfp):
		RandRun.do_simulation(self, selfp)
		if self.run:
			selfp.ack = 1
		else:
			selfp.ack = 0


class TB(Module):
	def __init__(self):
		self.submodules.source = PacketizerSourceModel(src_data)
		self.submodules.dut = LiteUSBPacketizer()
		self.submodules.sink = PacketizerSinkModel()

		self.comb +=[
			self.source.connect(self.dut.sink),
			self.dut.source.connect(self.sink),
		]

def main():
	from migen.sim.generic import run_simulation
	run_simulation(TB(), ncycles=400, vcd_name="tb_packetizer.vcd")

if __name__ == "__main__":
	main()
