from migen.fhdl.structure import *
from migen.fhdl.specials import Instance
from migen.fhdl.module import Module
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.bus import wishbone

_count_width = 11

class MiniMAC(Module, AutoCSR):
	def __init__(self, pads):
		# CPU interface
		self._phy_reset = CSRStorage(reset=1)
		self._rx_count_0 = CSRStatus(_count_width)
		self._rx_count_1 = CSRStatus(_count_width)
		self._tx_count = CSRStorage(_count_width, write_from_dev=True)
		self._tx_start = CSR()
		
		self.submodules.ev = EventManager()
		self.ev.rx0 = EventSourcePulse()
		self.ev.rx1 = EventSourcePulse()
		self.ev.tx = EventSourcePulse()
		self.ev.finalize()
		
		self.membus = wishbone.Interface()
		
		###

		init = Signal(reset=1)
		self.sync += init.eq(0)
		rx_ready_0 = Signal()
		rx_ready_1 = Signal()
		rx_pending_0 = self.ev.rx0.pending
		rx_pending_1 = self.ev.rx1.pending
		rx_pending_0_r = Signal()
		rx_pending_1_r = Signal()
		self.comb += [
			pads.rst_n.eq(~self._phy_reset.storage),
			
			rx_ready_0.eq(init | (rx_pending_0_r & ~rx_pending_0)),
			rx_ready_1.eq(init | (rx_pending_1_r & ~rx_pending_1)),
			
			self._tx_count.dat_w.eq(0),
			self._tx_count.we.eq(self.ev.tx.trigger)
		]
		self.sync += [
			rx_pending_0_r.eq(rx_pending_0),
			rx_pending_1_r.eq(rx_pending_1)
		]
		self.specials += Instance("minimac3",
				Instance.Input("sys_clk", ClockSignal()),
				Instance.Input("sys_rst", ResetSignal()),

				Instance.Output("rx_done_0", self.ev.rx0.trigger),
				Instance.Output("rx_count_0", self._rx_count_0.status),
				Instance.Output("rx_done_1", self.ev.rx1.trigger),
				Instance.Output("rx_count_1", self._rx_count_1.status),
				Instance.Input("rx_ready_0", rx_ready_0),
				Instance.Input("rx_ready_1", rx_ready_1),

				Instance.Input("tx_start", self._tx_start.re),
				Instance.Input("tx_count", self._tx_count.storage),
				Instance.Output("tx_done", self.ev.tx.trigger),
				
				Instance.Input("wb_adr_i", self.membus.adr),
				Instance.Input("wb_dat_i", self.membus.dat_w),
				Instance.Input("wb_sel_i", self.membus.sel),
				Instance.Input("wb_stb_i", self.membus.stb),
				Instance.Input("wb_cyc_i", self.membus.cyc),
				Instance.Input("wb_we_i", self.membus.we),
				Instance.Output("wb_dat_o", self.membus.dat_r),
				Instance.Output("wb_ack_o", self.membus.ack),
				
				Instance.Input("phy_tx_clk", ClockSignal("eth_tx")),
				Instance.Output("phy_tx_data", pads.tx_data),
				Instance.Output("phy_tx_en", pads.tx_en),
				Instance.Output("phy_tx_er", pads.tx_er),
				Instance.Input("phy_rx_clk", ClockSignal("eth_rx")),
				Instance.Input("phy_rx_data", pads.rx_data),
				Instance.Input("phy_dv", pads.dv),
				Instance.Input("phy_rx_er", pads.rx_er),
				Instance.Input("phy_col", pads.col),
				Instance.Input("phy_crs", pads.crs))
