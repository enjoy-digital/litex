from litesata.common import *

class K7LiteSATAPHYCRG(Module):
	def __init__(self, pads, gtx, revision, clk_freq):
		self.reset = Signal()
		self.ready = Signal()

		self.cd_sata_tx = ClockDomain()
		self.cd_sata_rx = ClockDomain()

	# CPLL
		# (SATA3) 150MHz / VCO @ 3GHz / Line rate @ 6Gbps
		# (SATA2 & SATA1) VCO still @ 3 GHz, Line rate is decreased with output dividers.
		refclk = Signal()
		self.specials += Instance("IBUFDS_GTE2",
			i_CEB=0,
			i_I=pads.refclk_p,
			i_IB=pads.refclk_n,
			o_O=refclk
		)
		self.comb += gtx.gtrefclk0.eq(refclk)

	# TX clocking
		# (SATA3) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 300MHz (16-bits)
		# (SATA2) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 150MHz (16-bits)
		# (SATA1) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 75MHz (16-bits)
		mmcm_reset = Signal()
		mmcm_locked = Signal()
		mmcm_fb = Signal()
		mmcm_clk_i = Signal()
		mmcm_clk0_o = Signal()
		mmcm_div_config = {
			"SATA1" : 	16.0,
			"SATA2" :	8.0,
			"SATA3" : 	4.0
			}
		mmcm_div = mmcm_div_config[revision]
		self.specials += [
			Instance("BUFG", i_I=gtx.txoutclk, o_O=mmcm_clk_i),
			Instance("MMCME2_ADV",
				p_BANDWIDTH="HIGH", p_COMPENSATION="ZHOLD", i_RST=mmcm_reset, o_LOCKED=mmcm_locked,

				# DRP
				i_DCLK=0, i_DEN=0, i_DWE=0, #o_DRDY=,
				i_DADDR=0, i_DI=0, #o_DO=,

				# VCO
				p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=6.666,
				p_CLKFBOUT_MULT_F=8.000, p_CLKFBOUT_PHASE=0.000, p_DIVCLK_DIVIDE=1,
				i_CLKIN1=mmcm_clk_i, i_CLKFBIN=mmcm_fb, o_CLKFBOUT=mmcm_fb,

				# CLK0
				p_CLKOUT0_DIVIDE_F=mmcm_div, p_CLKOUT0_PHASE=0.000, o_CLKOUT0=mmcm_clk0_o,
			),
			Instance("BUFG", i_I=mmcm_clk0_o, o_O=self.cd_sata_tx.clk),
		]
		self.comb += [
			gtx.txusrclk.eq(self.cd_sata_tx.clk),
			gtx.txusrclk2.eq(self.cd_sata_tx.clk)
		]

	# RX clocking
		# (SATA3) sata_rx recovered clk @ 300MHz from GTX RXOUTCLK
		# (SATA2) sata_rx recovered clk @ 150MHz from GTX RXOUTCLK
		# (SATA1) sata_rx recovered clk @ 150MHz from GTX RXOUTCLK
		self.specials += [
			Instance("BUFG", i_I=gtx.rxoutclk, o_O=self.cd_sata_rx.clk),
		]
		self.comb += [
			gtx.rxusrclk.eq(self.cd_sata_rx.clk),
			gtx.rxusrclk2.eq(self.cd_sata_rx.clk)
		]

	# Configuration Reset
		# After configuration, GTX's resets have to stay low for at least 500ns
		# See AR43482
		reset_en = Signal()
		clk_period_ns = 1000000000/clk_freq
		reset_en_cnt_max = math.ceil(500/clk_period_ns)
		reset_en_cnt = Signal(max=reset_en_cnt_max, reset=reset_en_cnt_max-1)
		self.sync += \
			If(self.reset,
				reset_en_cnt.eq(reset_en_cnt.reset)
			).Elif(~reset_en,
				reset_en_cnt.eq(reset_en_cnt-1)
			)
		self.comb += reset_en.eq(reset_en_cnt == 0)

	# TX Reset FSM
		tx_reset_fsm = InsertReset(FSM(reset_state="IDLE"))
		self.submodules += tx_reset_fsm
		self.comb += tx_reset_fsm.reset.eq(self.reset)
		tx_reset_fsm.act("IDLE",
			If(reset_en,
				NextState("RESET_GTX"),
			)
		)
		tx_reset_fsm.act("RESET_GTX",
			gtx.gttxreset.eq(1),
			If(gtx.cplllock & mmcm_locked,
				NextState("RELEASE_GTX")
			)
		)
		tx_reset_fsm.act("RELEASE_GTX",
			gtx.txuserrdy.eq(1),
			If(gtx.txresetdone,
				NextState("READY")
			)
		)
		tx_reset_fsm.act("READY",
			gtx.txuserrdy.eq(1)
		)

	# RX Reset FSM
		rx_reset_fsm = InsertReset(FSM(reset_state="IDLE"))
		self.submodules += rx_reset_fsm
		self.comb += rx_reset_fsm.reset.eq(self.reset)

		rx_reset_fsm.act("IDLE",
			If(reset_en,
				NextState("RESET_GTX"),
			)
		)
		rx_reset_fsm.act("RESET_GTX",
			gtx.gtrxreset.eq(1),
			If(gtx.cplllock & mmcm_locked,
				NextState("RELEASE_GTX")
			)
		)
		rx_reset_fsm.act("RELEASE_GTX",
			gtx.rxuserrdy.eq(1),
			If(gtx.rxresetdone,
				NextState("READY")
			)
		)
		rx_reset_fsm.act("READY",
			gtx.rxuserrdy.eq(1)
		)

	# Ready
		self.tx_ready = tx_reset_fsm.ongoing("READY")
		self.rx_ready = rx_reset_fsm.ongoing("READY")
		self.comb += self.ready.eq(self.tx_ready & self.rx_ready)

	# Reset PLL
		self.comb += gtx.cpllreset.eq(ResetSignal() | self.reset | ~reset_en)

	# Reset MMCM
		self.comb += mmcm_reset.eq(ResetSignal() | self.reset | ~gtx.cplllock)

	# Reset for SATA TX/RX clock domains
		self.specials += [
			AsyncResetSynchronizer(self.cd_sata_tx, ~self.tx_ready),
			AsyncResetSynchronizer(self.cd_sata_rx, ~self.rx_ready),
		]
