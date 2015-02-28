from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.frontend.common import *
from misoclib.mem.litesata.frontend.arbiter import LiteSATAArbiter

class LiteSATACrossbar(Module):
	def __init__(self, core):
		self.users = []
		self.master = LiteSATAMasterPort(32)
		self.comb += [
			self.master.source.connect(core.sink),
			core.source.connect(self.master.sink)
		]

	def get_port(self):
		port = LiteSATAUserPort(32)
		self.users += [port]
		return port

	def get_ports(self, n):
		ports = []
		for i in range(n):
			ports.append(self.get_port())
		return ports

	def do_finalize(self):
		arbiter = LiteSATAArbiter(self.users, self.master)
		self.submodules += arbiter