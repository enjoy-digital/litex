from lib.sata.common import *
from lib.sata.frontend.common import *
from lib.sata.frontend.arbiter import SATAArbiter

class SATACrossbar(Module):
	def __init__(self, dw):
		self.dw = dw
		self.slaves = []
		self.master = SATAMasterPort(dw)

	def get_port(self):
		master = SATAMasterPort(self.dw)
		slave = SATASlavePort(self.dw)
		self.comb += master.connect(slave)
		self.slaves.append(slave)
		return master

	def get_ports(self, n):
		masters = []
		for i in range(n):
			masters.append(self.get_port())
		return masters

	def do_finalize(self):
		self.arbiter = SATAArbiter(self.slaves, self.master)
