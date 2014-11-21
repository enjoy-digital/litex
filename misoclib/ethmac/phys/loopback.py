from migen.fhdl.std import *
from migen.flow.actor import Sink, Source
from migen.bank.description import *
from migen.genlib.record import *

from misoclib.ethmac.std import *

class LoopbackPHYCRG(Module, AutoCSR):
	def __init__(self):
		self._reset = CSRStorage()
		###
		self.clock_domains.cd_eth_rx = ClockDomain()
		self.clock_domains.cd_eth_tx = ClockDomain()
		self.comb += [
			self.cd_eth_rx.clk.eq(ClockSignal()),
			self.cd_eth_tx.clk.eq(ClockSignal())
		]

		reset = self._reset.storage
		self.comb += [
			self.cd_eth_rx.rst.eq(reset),
			self.cd_eth_tx.rst.eq(reset)
		]

class LoopbackPHY(Module, AutoCSR):
	def __init__(self):
		self.dw = 8
		###
		self.submodules.crg = LoopbackPHYCRG()
		self.sink = sink = Sink(eth_description(8))
		self.source = source = Source(eth_description(8))
		self.comb += Record.connect(self.sink, self.source)
