from migen.fhdl.std import *
from migen.bus.lasmibus import *
from migen.sim.generic import Simulator, TopLevel

from misoclib.lasmicon.bankmachine import *

from common import sdram_geom, sdram_timing, CommandLogger

def my_generator():
	for x in range(10):
		yield True, x
	for x in range(10):
		yield False, 128*x

class TB(Module):
	def __init__(self):
		self.req = Interface(32, 32, 1,
			sdram_timing.req_queue_size, sdram_timing.read_latency, sdram_timing.write_latency)
		self.submodules.dut = BankMachine(sdram_geom, sdram_timing, 2, 0, self.req)
		self.submodules.logger = CommandLogger(self.dut.cmd, True)
		self.generator = my_generator()
		self.dat_ack_cnt = 0

	def do_simulation(self, s):
		if s.rd(self.req.dat_ack):
			self.dat_ack_cnt += 1
		if s.rd(self.req.req_ack):
			try:
				we, adr = next(self.generator)
			except StopIteration:
				s.wr(self.req.stb, 0)
				if not s.rd(self.req.lock):
					s.interrupt = True
					print("data ack count: {0}".format(self.dat_ack_cnt))
				return
			s.wr(self.req.adr, adr)
			s.wr(self.req.we, we)
			s.wr(self.req.stb, 1)

def main():	
	sim = Simulator(TB(), TopLevel("my.vcd"))
	sim.run()

main()
