from litesata.common import *
from litesata.frontend.common import *
from litesata.frontend.arbiter import LiteSATAArbiter

class LiteSATACrossbar(Module):
	def __init__(self, core):
		self.slaves = []
		self.master = LiteSATAMasterPort(32)
		self.comb += [
			self.master.source.connect(core.sink),
			core.source.connect(self.master.sink)
		]

	def get_port(self):
		master = LiteSATAMasterPort(32)
		slave = LiteSATASlavePort(32)
		self.comb += master.connect(slave)
		self.slaves.append(slave)
		return master

	def get_ports(self, n):
		masters = []
		for i in range(n):
			masters.append(self.get_port())
		return masters

	def do_finalize(self):
		self.arbiter = LiteSATAArbiter(self.slaves, self.master)
