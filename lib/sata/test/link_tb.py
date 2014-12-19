from lib.sata.common import *
from lib.sata.link import SATALink

from lib.sata.test.common import *
from lib.sata.test.hdd import *

from migen.actorlib.structuring import *

class LinkStreamer(PacketStreamer):
	def __init__(self):
		PacketStreamer.__init__(self, link_description(32), LinkTXPacket)

class LinkLogger(PacketLogger):
	def __init__(self):
		PacketLogger.__init__(self, link_description(32), LinkRXPacket)

class TB(Module):
	def __init__(self):
		self.hdd = HDD(
				link_debug=False, link_random_level=50,
				transport_debug=False, transport_loopback=True)
		self.link = InsertReset(SATALink(self.hdd.phy))

		self.streamer = LinkStreamer()
		self.streamer_randomizer = Randomizer(link_description(32), level=50)

		self.logger_randomizer = Randomizer(link_description(32), level=50)
		self.logger = LinkLogger()

		self.pipeline = Pipeline(
			self.streamer,
			self.streamer_randomizer,
			self.link,
			self.logger_randomizer,
			self.logger
		)

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
