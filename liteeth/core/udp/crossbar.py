from collections import OrderedDict

from liteeth.common import *
from liteeth.generic.arbiter import Arbiter
from liteeth.generic.dispatcher import Dispatcher
from liteeth.core.udp.common import *

class LiteEthUDPCrossbar(Module):
	def __init__(self):
		self.users = OrderedDict()
		self.master = LiteEthUDPMasterPort(8)

	def get_port(self, udp_port, dw=8):
		if udp_port in self.users.keys():
			raise ValueError("Port {0:#x} already assigned".format(udp_port))
		user_port = LiteEthUDPUserPort(dw)
		internal_port = LiteEthUDPUserPort(8)
		if dw != 8:
			converter = Converter(eth_udp_user_description(user_port.dw), eth_udp_user_description(8))
			self.submodules += converter
			self.comb += [
				Record.connect(user_port.sink, converter.sink),
				Record.connect(converter.source, internal_port.sink)
			]
			converter = Converter(eth_udp_user_description(8), eth_udp_user_description(user_port.dw))
			self.submodules += converter
			self.comb += [
				Record.connect(internal_port.source, converter.sink),
				Record.connect(converter.source, user_port.source)
			]
			self.users[udp_port] = internal_port
		else:
			self.users[udp_port] = user_port
		return user_port

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
