from liteeth.common import *
from liteeth.generic import *

class LiteEthPHYMIITX(Module):
	def __init__(self, pads):
		self.sink = sink = Sink(eth_phy_description(8))
		###
		tx_en_r = Signal()
		tx_data_r = Signal(4)
		self.sync += [
			pads.tx_er.eq(0),
			pads.tx_en.eq(tx_en_r),
			pads.tx_data.eq(tx_data_r),
		]

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			sink.ack.eq(1),
			If(sink.stb & sink.sop,
				sink.ack.eq(0),
				NextState("SEND_LO")
			)
		)
		fsm.act("SEND_LO",
			tx_data_r.eq(sink.data[0:4]),
			tx_en_r.eq(1),
			NextState("SEND_HI")
		)
		fsm.act("SEND_HI",
			tx_data_r.eq(sink.data[4:8]),
			tx_en_r.eq(1),
			sink.ack.eq(1),
			If(sink.stb & sink.eop,
				NextState("IDLE")
			).Else(
				NextState("SEND_LO")
			)
		)

class LiteEthPHYMIIRX(Module):
	def __init__(self, pads):
		self.source = source = Source(eth_phy_description(8))
		###
		sop = source.sop
		set_sop = Signal()
		clr_sop = Signal()
		self.sync += \
			If(clr_sop,
				sop.eq(0)
			).Elif(set_sop,
				sop.eq(1)
			)

		lo = Signal(4)
		hi = Signal(4)
		load_nibble = Signal(2)
		self.sync  += \
			If(load_nibble[0],
				lo.eq(pads.rx_data)
			).Elif(load_nibble[1],
				hi.eq(pads.rx_data)
			)
		self.comb += [
			source.data.eq(Cat(lo, hi))
		]

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			set_sop.eq(1),
			If(pads.dv,
				load_nibble.eq(0b01),
				NextState("LOAD_HI")
			)
		)
		fsm.act("LOAD_LO",
			source.stb.eq(1),
			If(pads.dv,
				clr_sop.eq(1),
				load_nibble.eq(0b01),
				NextState("LOAD_HI")
			).Else(
				source.eop.eq(1),
				NextState("IDLE")
			)
		)
		fsm.act("LOAD_HI",
			load_nibble.eq(0b10),
			NextState("LOAD_LO")
		)

class LiteEthPHYMIICRG(Module, AutoCSR):
	def __init__(self, clock_pads, pads, with_hw_init_reset):
		self._reset = CSRStorage()
		###
		self.sync.base50 += clock_pads.phy.eq(~clock_pads.phy)

		self.clock_domains.cd_eth_rx = ClockDomain()
		self.clock_domains.cd_eth_tx = ClockDomain()
		self.comb += self.cd_eth_rx.clk.eq(clock_pads.rx)
		self.comb += self.cd_eth_tx.clk.eq(clock_pads.tx)

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

class LiteEthPHYMII(Module, AutoCSR):
	def __init__(self, clock_pads, pads, with_hw_init_reset=True):
		self.dw = 8
		self.submodules.crg = LiteEthPHYMIICRG(clock_pads, pads, with_hw_init_reset)
		self.submodules.tx = RenameClockDomains(LiteEthPHYMIITX(pads), "eth_tx")
		self.submodules.rx = RenameClockDomains(LiteEthPHYMIIRX(pads), "eth_rx")
		self.sink, self.source = self.tx.sink, self.rx.source
