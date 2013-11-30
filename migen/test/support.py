import unittest
from migen.fhdl.std import *
from migen.sim.generic import Simulator
from migen.fhdl import verilog

class SimBench(Module):
	callback = None
	def do_simulation(self, s):
		if self.callback is not None:
			return self.callback(self, s)

class SimCase:
	TestBench = SimBench

	def setUp(self, *args, **kwargs):
		self.tb = self.TestBench(*args, **kwargs)

	def test_to_verilog(self):
		verilog.convert(self.tb)

	def run_with(self, cb, cycles=-1):
		self.tb.callback = cb
		with Simulator(self.tb) as s:
			s.run(cycles)
