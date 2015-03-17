from migen.genlib.io import DDROutput

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.generic import *

class LiteEthPHYGMIITX(Module):
	def __init__(self, pads):
		self.sink = sink = Sink(eth_phy_description(8))
		###
		if hasattr(pads, "tx_er"):
			self.sync += pads.tx_er.eq(0)
		self.sync += [
			pads.tx_en.eq(sink.stb),
			pads.tx_data.eq(sink.data)
		]
		self.comb += sink.ack.eq(1)

class LiteEthPHYGMIIRX(Module):
	def __init__(self, pads):
		self.source = source = Source(eth_phy_description(8))
		###
		dv_d = Signal()
		self.sync += dv_d.eq(pads.dv)

		sop = Signal()
		eop = Signal()
		self.comb += [
			sop.eq(pads.dv & ~dv_d),
			eop.eq(~pads.dv & dv_d)
		]
		self.sync += [
			source.stb.eq(pads.dv),
			source.sop.eq(sop),
			source.data.eq(pads.rx_data)
		]
		self.comb += source.eop.eq(eop)

class LiteEthPHYGMIICRG(Module, AutoCSR):
	def __init__(self, clock_pads, pads, with_hw_init_reset):
		self._reset = CSRStorage()
		###
		self.clock_domains.cd_eth_rx = ClockDomain()
		self.clock_domains.cd_eth_tx = ClockDomain()
		self.specials += DDROutput(1, 0, clock_pads.gtx, ClockSignal("eth_tx"))
		self.comb += [
			self.cd_eth_rx.clk.eq(clock_pads.rx),		# Let the synthesis tool insert
			self.cd_eth_tx.clk.eq(self.cd_eth_rx.clk)	# the appropriate clock buffer
		]

		if with_hw_init_reset:
			reset = Signal()
			counter_done = Signal()
			self.submodules.counter = counter = Counter(max=512)
			self.comb += [
				counter_done.eq(counter.value == 256),
				counter.ce.eq(~counter_done),
				reset.eq(~counter_done | self._reset.storage)
			]
		else:
			reset = self._reset.storage
		self.comb += pads.rst_n.eq(~reset)
		self.specials += [
			AsyncResetSynchronizer(self.cd_eth_tx, reset),
			AsyncResetSynchronizer(self.cd_eth_rx, reset),
		]

class LiteEthPHYGMII(Module, AutoCSR):
	def __init__(self, clock_pads, pads, with_hw_init_reset=True):
		self.dw = 8
		self.submodules.crg = LiteEthPHYGMIICRG(clock_pads, pads, with_hw_init_reset)
		self.submodules.tx = RenameClockDomains(LiteEthPHYGMIITX(pads), "eth_tx")
		self.submodules.rx = RenameClockDomains(LiteEthPHYGMIIRX(pads), "eth_rx")
		self.sink, self.source = self.tx.sink, self.rx.source
