from lib.sata.common import *
from lib.sata.phy.datapath import SATAPHYDatapath

from lib.sata.test.common import *

class DataPacket(list):
	def __init__(self, data=[]):
		self.ongoing = False
		self.done = False
		for d in data:
			self.append(d)

class DataStreamer(PacketStreamer):
	def __init__(self):
		PacketStreamer.__init__(self, phy_description(32), DataPacket)

	def do_simulation(self, selfp):
		PacketStreamer.do_simulation(self, selfp)
		selfp.source.charisk = 0
		# Note: for simplicity we generate charisk by detecting
		# primitives in data
		for k, v in primitives.items():
			try:
				if self.source_data == v:
					selfp.source.charisk = 0b0001
			except:
				pass

class DataLogger(PacketLogger):
	def __init__(self):
		PacketLogger.__init__(self, phy_description(32), DataPacket)

class TRX(Module):
	def __init__(self):
		self.sink = Sink(phy_description(32))
		self.source = Source(phy_description(32))
		self.comb += Record.connect(self.sink, self.source)

class CTRL(Module):
	def __init__(self):
		self.sink = Sink(phy_description(32))
		self.source = Source(phy_description(32))
		self.ready = Signal(reset=1)

class TB(Module):
	def __init__(self):
		# use sys_clk for each clock_domain
		self.clock_domains.cd_sata_rx = ClockDomain()
		self.clock_domains.cd_sata_tx = ClockDomain()
		self.comb += [
			self.cd_sata_rx.clk.eq(ClockSignal()),
			self.cd_sata_rx.rst.eq(ResetSignal()),
			self.cd_sata_tx.clk.eq(ClockSignal()),
			self.cd_sata_tx.rst.eq(ResetSignal()),
		]

		self.streamer = DataStreamer()
		self.streamer_randomizer = Randomizer(phy_description(32), level=0)
		self.trx = TRX()
		self.ctrl = CTRL()
		self.datapath = SATAPHYDatapath(self.trx, self.ctrl)
		self.logger_randomizer = Randomizer(phy_description(32), level=0)
		self.logger = DataLogger()

		self.pipeline = Pipeline(
			self.streamer,
			self.streamer_randomizer,
			self.datapath,
			self.logger_randomizer,
			self.logger
		)

	def gen_simulation(self, selfp):
		streamer_packet = DataPacket([seed_to_data(i, False) for i in range(512)])
		yield from self.streamer.send(streamer_packet)
		yield from self.logger.receive(512)
		for d in self.logger.packet:
			r = "%08x " %d
			r +=decode_primitive(d)
			print(r)

		# check results
		#s, l, e = check(streamer_packet, self.logger.packet)
		#print("shift "+ str(s) + " / length " + str(l) + " / errors " + str(e))


if __name__ == "__main__":
	run_simulation(TB(), ncycles=4096, vcd_name="my.vcd", keep_files=True)
