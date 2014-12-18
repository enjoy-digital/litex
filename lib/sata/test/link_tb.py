from lib.sata.common import *
from lib.sata.link import SATALink

from lib.sata.test.common import *
from lib.sata.test.hdd import *

class LinkStreamer(PacketStreamer):
	def __init__(self):
		PacketStreamer.__init__(self, link_description(32), LinkTXPacket)

class LinkLogger(PacketLogger):
	def __init__(self):
		PacketLogger.__init__(self, link_description(32), LinkRXPacket)

class TB(Module):
	def __init__(self):
		self.submodules.hdd = HDD(
				link_debug=False, link_random_level=50,
				transport_debug=False, transport_loopback=True)
		self.submodules.link = SATALink(self.hdd.phy)

		self.submodules.streamer = LinkStreamer()
		streamer_ack_randomizer = AckRandomizer(link_description(32), level=50)
		self.submodules += streamer_ack_randomizer
		self.submodules.logger = LinkLogger()
		logger_ack_randomizer = AckRandomizer(link_description(32), level=50)
		self.submodules += logger_ack_randomizer
		self.comb += [
			Record.connect(self.streamer.source, streamer_ack_randomizer.sink),
			Record.connect(streamer_ack_randomizer.source, self.link.sink),
			Record.connect(self.link.source, logger_ack_randomizer.sink),
			Record.connect(logger_ack_randomizer.source, self.logger.sink)
		]

	def gen_simulation(self, selfp):
		for i in range(8):
			streamer_packet = LinkTXPacket([i for i in range(64)])
			yield from self.streamer.send(streamer_packet)
			yield from self.logger.receive()

			# check results
			s, l, e = check(streamer_packet, self.logger.packet)
			print("shift "+ str(s) + " / length " + str(l) + " / errors " + str(e))


if __name__ == "__main__":
	run_simulation(TB(), ncycles=2048, vcd_name="my.vcd", keep_files=True)
