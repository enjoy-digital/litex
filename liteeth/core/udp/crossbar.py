from collections import OrderedDict

from liteeth.common import *
from liteeth.generic.arbiter import Arbiter
from liteeth.generic.dispatcher import Dispatcher
from liteeth.core.udp.common import *

class LiteEthUDPCrossbar(Module):
	def __init__(self):
		self.users = OrderedDict()
		self.master = LiteEthUDPMasterPort(8)

	def get_port(self, udp_port):
		port = LiteEthUDPUserPort(8)
		if udp_port in self.users.keys():
			raise ValueError("Port {0:#x} already assigned".format(udp_port))
		self.users[udp_port] = port
		return port

	def do_finalize(self):
		# TX arbitrate
		sinks = [port.sink for port in self.users.values()]
		self.submodules.udp_arbiter = Arbiter(sinks, self.master.source)

		# RX dispatch
		sources = [port.source for port in self.users.values()]
		self.submodules.udp_dispatcher = Dispatcher(self.master.sink, sources, one_hot=True)
		cases = {}
		cases["default"] = self.udp_dispatcher.sel.eq(0)
		for i, (k, v) in enumerate(self.users.items()):
			cases[k] = self.udp_dispatcher.sel.eq(2**i)
		self.comb += \
			Case(self.master.sink.dst_port, cases)
