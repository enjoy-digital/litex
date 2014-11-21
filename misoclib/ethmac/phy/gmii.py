from migen.fhdl.std import *
from migen.flow.actor import Sink, Source
from migen.bank.description import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from misoclib.ethmac.common import *

class GMIIPHYTX(Module):
	def __init__(self, pads):
		self.sink = sink = Sink(eth_description(8))

		###

		self.sync += [
			pads.tx_er.eq(0),
			pads.tx_en.eq(sink.stb),
			pads.tx_data.eq(sink.d)
		]
		self.comb += sink.ack.eq(1)

class GMIIPHYRX(Module):
	def __init__(self, pads):
		self.source = source = Source(eth_description(8))

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
			source.d.eq(pads.rx_data)
		]
		self.comb += source.eop.eq(eop)

# CRG is the only Xilinx specific module.
# TODO: use generic code or add support for others vendors
class GMIIPHYCRG(Module, AutoCSR):
	def __init__(self, clock_pads, pads):
		self._reset = CSRStorage()

		###

		self.clock_domains.cd_eth_rx = ClockDomain()
		self.clock_domains.cd_eth_tx = ClockDomain()
		self.specials += [
			Instance("ODDR",
				p_DDR_CLK_EDGE="SAME_EDGE",
				i_C=ClockSignal("eth_tx"), i_CE=1, i_S=0, i_R=0,
				i_D1=1, i_D2=0, o_Q=clock_pads.gtx,
			),
			Instance("BUFG", i_I=clock_pads.rx, o_O=self.cd_eth_rx.clk),
		]
		self.comb += self.cd_eth_tx.clk.eq(self.cd_eth_rx.clk)

		reset = self._reset.storage
		self.comb += pads.rst_n.eq(~reset)
		self.specials += [
			AsyncResetSynchronizer(self.cd_eth_tx, reset),
			AsyncResetSynchronizer(self.cd_eth_rx, reset),
		]

class GMIIPHY(Module, AutoCSR):
	def __init__(self, clock_pads, pads):
		self.dw = 8
		self.submodules.crg = GMIIPHYCRG(clock_pads, pads)
		self.submodules.tx = RenameClockDomains(GMIIPHYTX(pads), "eth_tx")
		self.submodules.rx = RenameClockDomains(GMIIPHYRX(pads), "eth_rx")
		self.sink, self.source = self.tx.sink, self.rx.source
