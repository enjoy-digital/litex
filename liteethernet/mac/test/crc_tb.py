from migen.fhdl.std import *
from migen.actorlib.crc import *

from misoclib.ethmac.common import *
from misoclib.ethmac.test.common import *

payload = [
	0x00, 0x0A, 0xE6, 0xF0, 0x05, 0xA3, 0x00, 0x12,
	0x34, 0x56, 0x78, 0x90, 0x08, 0x00, 0x45, 0x00,
	0x00, 0x30, 0xB3, 0xFE, 0x00, 0x00, 0x80, 0x11,
	0x72, 0xBA, 0x0A, 0x00, 0x00, 0x03, 0x0A, 0x00,
	0x00, 0x02, 0x04, 0x00, 0x04, 0x00, 0x00, 0x1C,
	0x89, 0x4D, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05,
	0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D,
	0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13
]

crc = [
	0x7A, 0xD5, 0x6B, 0xB3
]

mux = {
	"inserter": 0,
	"checker": 1,
	"both": 2
}

class TB(Module):
	def __init__(self, random_level=50):
		sm = self.submodules
		sm.streamer = PacketStreamer(eth_description(8))
		sm.streamer_randomizer = AckRandomizer(eth_description(8), random_level)
		sm.logger = PacketLogger(eth_description(8))
		sm.logger_randomizer = AckRandomizer(eth_description(8), random_level)

		self.comb += [
			self.streamer.source.connect(self.streamer_randomizer.sink),
			self.logger_randomizer.source.connect(self.logger.sink)
		]

		sm.crc32_inserter = CRC32Inserter(eth_description(8))
		sm.crc32_checker = CRC32Checker(eth_description(8))

		self.mux = Signal(2)
		self.comb += [
			If(self.mux == mux["inserter"],
				self.streamer_randomizer.source.connect(self.crc32_inserter.sink),
				self.crc32_inserter.source.connect(self.logger_randomizer.sink)
			).Elif(self.mux == mux["checker"],
				self.streamer_randomizer.source.connect(self.crc32_checker.sink),
				self.crc32_checker.source.connect(self.logger_randomizer.sink)
			).Elif(self.mux == mux["both"],
				self.streamer_randomizer.source.connect(self.crc32_inserter.sink),
				self.crc32_inserter.source.connect(self.crc32_checker.sink),
				self.crc32_checker.source.connect(self.logger_randomizer.sink)
			)
		]

	def gen_simulation(self, selfp):
		selfp.mux = mux["inserter"]
		print("streamer --> crc32_inserter --> logger:")
		self.streamer.send(Packet(payload))
		yield from self.logger.receive()
		s, l, e = check(payload+crc, self.logger.packet)
		print("shift "+ str(s) + " / length " + str(l) + " / errors " + str(e))

		selfp.mux = mux["checker"]
		print("streamer --> crc32_checker --> logger:")
		self.streamer.send(Packet(payload+crc))
		yield from self.logger.receive()
		s, l, e = check(payload, self.logger.packet)
		print("shift "+ str(s) + " / length " + str(l) + " / errors " + str(e))

		selfp.mux = mux["both"]
		print("streamer --> crc32_inserter --> crc32_checker --> logger:")
		self.streamer.send(Packet(payload))
		yield from self.logger.receive()
		s, l, e = check(payload, self.logger.packet)
		print("shift "+ str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
	from migen.sim.generic import run_simulation
	run_simulation(TB(), ncycles=1000, vcd_name="my.vcd")
