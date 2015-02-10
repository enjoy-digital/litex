from collections import OrderedDict

from liteeth.common import *
from liteeth.generic.arbiter import Arbiter
from liteeth.generic.dispatcher import Dispatcher
from liteeth.core.ip.common import *

class LiteEthIPV4Crossbar(Module):
	def __init__(self):
		self.users = OrderedDict()
		self.master = LiteEthIPV4MasterPort(8)

	def get_port(self, protocol):
		if protocol in self.users.keys():
			raise ValueError("Protocol {0:#x} already assigned".format(protocol))
		port = LiteEthIPV4UserPort(8)
		self.users[protocol] = port
		return port

	def do_finalize(self):
		# TX arbitrate
		sinks = [port.sink for port in self.users.values()]
		self.submodules.ip_arbiter = Arbiter(sinks, self.master.source)

		# RX dispatch
		sources = [port.source for port in self.users.values()]
		self.submodules.ip_dispatcher = Dispatcher(self.master.sink, sources, one_hot=True)
		cases = {}
		cases["default"] = self.ip_dispatcher.sel.eq(0)
		for i, (k, v) in enumerate(self.users.items()):
			cases[k] = self.ip_dispatcher.sel.eq(2**i)
		self.comb += \
			Case(self.master.sink.protocol, cases)
