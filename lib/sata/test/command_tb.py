import random, copy

from migen.fhdl.std import *
from migen.genlib.record import *
from migen.sim.generic import run_simulation

from lib.sata.common import *
from lib.sata.link import SATALink
from lib.sata.transport import SATATransport
from lib.sata.command import SATACommand

from lib.sata.test.hdd import *
from lib.sata.test.common import *

class CommandTXPacket(list):
	def __init__(self, write=0, read=0,  identify=0, address=0, length=0, data=[]):
		self.ongoing = False
		self.done = False
		self.write = write
		self.read = read
		self.identify = identify
		self.address = address
		self.length = length
		for d in data:
			self.append(d)

class CommandStreamer(Module):
	def __init__(self):
		self.source = Source(command_tx_description(32))
		###
		self.packets = []
		self.packet = CommandTXPacket()
		self.packet.done = 1
		self.length = 0

	def send(self, packet, blocking=True):
		packet = copy.deepcopy(packet)
		self.packets.append(packet)
		if blocking:
			while packet.done == 0:
				yield

	def do_simulation(self, selfp):
		if len(self.packets) and self.packet.done:
			self.packet = self.packets.pop(0)

		selfp.source.write = self.packet.write
		selfp.source.read = self.packet.read
		selfp.source.identify = self.packet.identify
		selfp.source.address = self.packet.address
		selfp.source.length = self.packet.length

		if not self.packet.ongoing and not self.packet.done:
			selfp.source.stb = 1
			selfp.source.sop = 1
			if len(self.packet) > 0:
				selfp.source.data = self.packet.pop(0)
			self.packet.ongoing = True
		elif selfp.source.stb == 1 and selfp.source.ack == 1:
			selfp.source.sop = 0
			selfp.source.eop = (len(self.packet) == 1)
			if len(self.packet) > 0:
				selfp.source.stb = 1
				selfp.source.data = self.packet.pop(0)
			else:
				self.packet.done = 1
				selfp.source.stb = 0

class CommandRXPacket(list):
	def __init__(self):
		self.ongoing = False
		self.done = False
		self.write = 0
		self.read = 0
		self.identify = 0
		self.success = 0
		self.failed = 0

class CommandLogger(Module):
	def __init__(self):
		self.sink = Sink(command_rx_description(32))
		###
		self.packet = CommandRXPacket()

	def receive(self):
		self.packet.done = 0
		while self.packet.done == 0:
			yield

	def do_simulation(self, selfp):
		selfp.sink.ack = 1
		if selfp.sink.stb == 1 and selfp.sink.sop == 1:
			self.packet = CommandRXPacket()
			self.packet.write = selfp.sink.write
			self.packet.read = selfp.sink.read
			self.packet.identify = selfp.sink.identify
			self.packet.sucess = selfp.sink.success
			self.packet.failed = selfp.sink.failed
			self.packet.append(selfp.sink.data)
		elif selfp.sink.stb:
			self.packet.append(selfp.sink.data)
		if (selfp.sink.stb == 1 and selfp.sink.eop == 1):
			self.packet.done = True

class TB(Module):
	def __init__(self):
		self.submodules.hdd = HDD(
				phy_debug=False,
				link_random_level=25, link_debug=False,
				transport_debug=False, transport_loopback=False,
				command_debug=False,
				mem_debug=True)
		self.submodules.link = SATALink(self.hdd.phy)
		self.submodules.transport = SATATransport(self.link)
		self.submodules.command = SATACommand(self.transport)

		self.submodules.streamer = CommandStreamer()
		streamer_ack_randomizer = AckRandomizer(command_tx_description(32), level=0)
		self.submodules += streamer_ack_randomizer
		self.submodules.logger = CommandLogger()
		logger_ack_randomizer = AckRandomizer(command_rx_description(32), level=25)
		self.submodules += logger_ack_randomizer
		self.comb += [
			Record.connect(self.streamer.source, streamer_ack_randomizer.sink),
			Record.connect(streamer_ack_randomizer.source, self.command.sink),
			Record.connect(self.command.source, logger_ack_randomizer.sink),
			Record.connect(logger_ack_randomizer.source, self.logger.sink)
		]

	def gen_simulation(self, selfp):
		self.hdd.allocate_mem(0x00000000, 64*1024*1024)
		write_data = [i for i in range(128)]
		write_packet = CommandTXPacket(write=1, address=1024, length=len(write_data), data=write_data)
		yield from self.streamer.send(write_packet)
		yield from self.logger.receive()
		read_packet = CommandTXPacket(read=1, address=1024, length=len(write_data))
		yield from self.streamer.send(read_packet)
		yield from self.logger.receive()
		read_data = self.logger.packet
		yield from self.logger.receive()

		# check results
		s, l, e = check(write_data, read_data)
		print("shift "+ str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
	run_simulation(TB(), ncycles=1024, vcd_name="my.vcd", keep_files=True)
