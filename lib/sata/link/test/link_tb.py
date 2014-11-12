from migen.fhdl.std import *
from migen.genlib.record import *
from migen.sim.generic import run_simulation

from lib.sata.std import *
from lib.sata.link import SATALinkLayer

from lib.sata.link.test.bfm import *

class LinkPacket():
	def __init__(self, d=[]):
		self.d = d
		self.start = 1
		self.done = 0

class LinkStreamer(Module):
	def __init__(self, dw):
		self.source = Source(link_layout(dw))
		###
		self.packets = []
		self.packet = LinkPacket()
		self.packet.done = 1

	def send(self, packet, blocking=True):
		self.packets.append(packet)
		if blocking:
			while packet.done == 0:
				yield

	def do_simulation(self, selfp):
		if len(self.packets) and self.packet.done:
			self.packet = self.packets.pop(0)
		if self.packet.start and not self.packet.done:
			selfp.source.stb = 1
			selfp.source.sop = 1
			selfp.source.d = self.packet.d.pop(0)
			self.packet.start = 0
		elif selfp.source.stb == 1 and selfp.source.ack == 1:
			selfp.source.sop = 0
			selfp.source.eop = (len(self.packet.d) == 1)
			if len(self.packet.d) > 0:
				selfp.source.stb = 1
				selfp.source.d = self.packet.d.pop(0)
			else:
				self.packet.done = 1
				selfp.source.stb = 0

class LinkLogger(Module):
	def __init__(self, dw):
		self.sink = Sink(link_layout(dw))
		###
		self.packet = LinkPacket()

	def receive(self):
		self.packet.done = 0
		while self.packet.done == 0:
			yield

	def do_simulation(self, selfp):
		self.packet.done = 0
		selfp.sink.ack = 1
		if selfp.sink.stb == 1 and selfp.sink.sop == 1:
			self.packet.start = 1
			self.packet.d = [selfp.sink.d]
		elif selfp.sink.stb:
			self.packet.start = 0
			self.packet.d.append(selfp.sink.d)
		if (selfp.sink.stb ==1 and selfp.sink.eop ==1):
			self.packet.done = 1

class TB(Module):
	def __init__(self):
		self.submodules.bfm = BFM(32, debug=True)
		self.submodules.link_layer = SATALinkLayer(self.bfm.phy)

		self.submodules.streamer = LinkStreamer(32)
		self.submodules.logger = LinkLogger(32)
		self.comb += [
			Record.connect(self.streamer.source, self.link_layer.sink),
			Record.connect(self.link_layer.source, self.logger.sink)
		]

	def gen_simulation(self, selfp):
		for i in range(200):
			yield
		for i in range(8):
			yield from self.streamer.send(LinkPacket([0, 1, 2, 3]))

if __name__ == "__main__":
	run_simulation(TB(), ncycles=512, vcd_name="my.vcd", keep_files=True)
