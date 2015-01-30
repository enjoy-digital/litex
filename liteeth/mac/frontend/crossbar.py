from collections import OrderedDict

from liteeth.common import *
from liteeth.generic.arbiter import Arbiter
from liteeth.generic.dispatcher import Dispatcher
from liteeth.mac.frontend.common import *

class LiteEthMACCrossbar(Module):
	def __init__(self):
		self.users = OrderedDict()
		self.master = LiteEthMACMasterPort(8)

	def get_port(self, ethernet_type):
		port = LiteEthMACUserPort(8)
		if ethernet_type in self.users.keys():
			raise ValueError("Ethernet type {} already used")
		self.users[ethernet_type] = port
		return port

	def do_finalize(self):
		# TX arbitrate
		sinks = [port.sink for port in self.users.values()]
		self.submodules.mac_arbiter = Arbiter(sinks, self.master.source)

		# RX dispatch
		sources = [port.source for port in self.users.values()]
		self.submodules.mac_dispatcher = Dispatcher(self.master.sink, sources, one_hot=True)
		cases = {}
		cases["default"] = self.mac_dispatcher.sel.eq(0)
		for i, (k, v) in enumerate(self.users.items()):
			cases[k] = self.mac_dispatcher.sel.eq(2**i)
		self.comb += \
			Case(self.master.sink.ethernet_type, cases)
