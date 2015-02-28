import random, copy

from migen.sim.generic import run_simulation

from litesata.common import *

def seed_to_data(seed, random=True):
	if random:
		return (seed * 0x31415979 + 1) & 0xffffffff
	else:
		return seed

def check(p1, p2):
	p1 = copy.deepcopy(p1)
	p2 = copy.deepcopy(p2)
	if isinstance(p1, int):
		return 0, 1, int(p1 != p2)
	else:
		if len(p1) >= len(p2):
			ref, res = p1, p2
		else:
			ref, res = p2, p1
		shift = 0
		while((ref[0] != res[0]) and (len(res)>1)):
			res.pop(0)
			shift += 1
		length = min(len(ref), len(res))
		errors = 0
		for i in range(length):
			if ref.pop(0) != res.pop(0):
				errors += 1
		return shift, length, errors

def randn(max_n):
	return random.randint(0, max_n-1)

class PacketStreamer(Module):
	def __init__(self, description, packet_class):
		self.source = Source(description)
		###
		self.packets = []
		self.packet = packet_class()
		self.packet.done = 1

		self.source_data = 0

	def send(self, packet, blocking=True):
		packet = copy.deepcopy(packet)
		self.packets.append(packet)
		if blocking:
			while packet.done == 0:
				yield

	def do_simulation(self, selfp):
		if len(self.packets) and self.packet.done:
			self.packet = self.packets.pop(0)
		if not self.packet.ongoing and not self.packet.done:
			selfp.source.stb = 1
			if self.source.description.packetized:
				selfp.source.sop = 1
			if len(self.packet) > 0:
				self.source_data = self.packet.pop(0)
				if hasattr(selfp.source, "data"):
					selfp.source.data = self.source_data
				else:
					selfp.source.d = self.source_data
			self.packet.ongoing = True
		elif selfp.source.stb == 1 and selfp.source.ack == 1:
			if self.source.description.packetized:
				selfp.source.sop = 0
				selfp.source.eop = (len(self.packet) == 1)
			if len(self.packet) > 0:
				selfp.source.stb = 1
				self.source_data = self.packet.pop(0)
				if hasattr(selfp.source, "data"):
					selfp.source.data = self.source_data
				else:
					selfp.source.d = self.source_data
			else:
				self.packet.done = 1
				selfp.source.stb = 0

class PacketLogger(Module):
	def __init__(self, description, packet_class):
		self.sink = Sink(description)
		###
		self.packet_class = packet_class
		self.packet = packet_class()

	def receive(self, length=None):
		self.packet.done = 0
		if length is None:
			while self.packet.done == 0:
				yield
		else:
			while length > len(self.packet):
				yield

	def do_simulation(self, selfp):
		selfp.sink.ack = 1
		if self.sink.description.packetized:
			if selfp.sink.stb == 1 and selfp.sink.sop == 1:
				self.packet = self.packet_class()
		if selfp.sink.stb:
			if hasattr(selfp.sink, "data"):
				self.packet.append(selfp.sink.data)
			else:
				self.packet.append(selfp.sink.d)
		if self.sink.description.packetized:
			if selfp.sink.stb == 1 and selfp.sink.eop == 1:
				self.packet.done = True

class Randomizer(Module):
	def __init__(self, description, level=0):
		self.level = level

		self.sink = Sink(description)
		self.source = Source(description)

		self.run = Signal()

		self.comb += \
			If(self.run,
				Record.connect(self.sink, self.source)
			).Else(
				self.source.stb.eq(0),
				self.sink.ack.eq(0),
			)

	def do_simulation(self, selfp):
		n = randn(100)
		if n < self.level:
			selfp.run = 0
		else:
			selfp.run = 1
