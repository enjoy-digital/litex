from migen.genlib.io import DDROutput
from migen.flow.plumbing import Multiplexer, Demultiplexer

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.generic import *

from misoclib.com.liteeth.phy.gmii import LiteEthPHYGMIIMIICRG
from misoclib.com.liteeth.phy.mii import LiteEthPHYMIITX, LiteEthPHYMIIRX
from misoclib.com.liteeth.phy.gmii import LiteEthPHYGMIITX, LiteEthPHYGMIIRX

modes = {
	"GMII"	: 0,
	"MII"	: 1
}

class LiteEthPHYGMIIMIITX(Module):
	def __init__(self, pads, mode):
		self.sink = sink = Sink(eth_phy_description(8))
		###
		tx_pads_layout = [("tx_er", 1), ("tx_en", 1), ("tx_data", 8)]

		gmii_tx_pads = Record(tx_pads_layout)
		gmii_tx = LiteEthPHYGMIITX(gmii_tx_pads)
		self.submodules += gmii_tx

		mii_tx_pads = Record(tx_pads_layout)
		mii_tx = LiteEthPHYMIITX(mii_tx_pads)
		self.submodules += mii_tx

		demux = Demultiplexer(eth_phy_description(8), 2)
		self.submodules += demux
		self.comb += [
			demux.sel.eq(mode==modes["MII"]),
			Record.connect(sink, demux.sink),
			Record.connect(demux.source0, gmii_tx.sink),
			Record.connect(demux.source1, mii_tx.sink),
		]

		if hasattr(pads, "tx_er"):
			self.comb += pads.tx_er.eq(0)
		self.sync += [
			If(mode==modes["MII"],
				pads.tx_en.eq(mii_tx_pads.tx_en),
				pads.tx_data.eq(mii_tx_pads.tx_data),
			).Else(
				pads.tx_en.eq(gmii_tx_pads.tx_en),
				pads.tx_data.eq(gmii_tx_pads.tx_data),
			)
		]

class LiteEthPHYGMIIMIIRX(Module):
	def __init__(self, pads, mode):
		self.source = source = Source(eth_phy_description(8))
		###
		gmii_rx = LiteEthPHYGMIIRX(pads)
		self.submodules += gmii_rx

		mii_rx = LiteEthPHYMIIRX(pads)
		self.submodules += mii_rx

		mux = Multiplexer(eth_phy_description(8), 2)
		self.submodules += mux
		self.comb += [
			mux.sel.eq(mode==modes["MII"]),
			Record.connect(gmii_rx.source, mux.sink0),
			Record.connect(mii_rx.source, mux.sink1),
			Record.connect(mux.source, source)
		]

class LiteEthPHYGMIIMII(Module, AutoCSR):
	def __init__(self, clock_pads, pads, with_hw_init_reset=True):
		self.dw = 8
		self._mode = CSRStorage()
		mode = self._mode.storage
		# Note: we can use GMII CRG since it also handles tx clock pad used for MII
		self.submodules.crg = LiteEthPHYGMIICRG(clock_pads, pads, with_hw_init_reset)
		self.submodules.tx = RenameClockDomains(LiteEthPHYGMIIMIITX(pads, mode), "eth_tx")
		self.submodules.rx = RenameClockDomains(LiteEthPHYGMIIMIIRX(pads, mode), "eth_rx")
		self.sink, self.source = self.tx.sink, self.rx.source
