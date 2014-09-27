from math import ceil

from migen.fhdl.std import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.fsm import FSM, NextState

from lib.sata.k7sataphy.std import *

class K7SATAPHYReconfig(Module):
	def __init__(self, channel_drp, mmcm_drp):
		self.speed = Signal(3)
		###
		speed_r = Signal(3)
		speed_change = Signal()
		self.sync += speed_r.eq(self.speed)
		self.comb += speed_change.eq(self.speed != speed_r)

		drp_sel = Signal()
		drp = DRPBus()
		self.comb += \
			If(drp_sel,
				drp.connect(mmcm_drp)
			).Else(
				drp.connect(channel_drp)
			)

class K7SATAPHYClocking(Module):
	def __init__(self, pads, gtx, clk_freq):
		self.reset = Signal()

		self.clock_domains.cd_sata = ClockDomain()
		self.clock_domains.cd_sata_tx = ClockDomain()
		self.clock_domains.cd_sata_rx = ClockDomain()

	# CPLL
		# (SATA3) 150MHz / VCO @ 3GHz / Line rate @ 6Gbps
		# (SATA2 & SATA1) VCO still @ 3 GHz, Line rate is decreased with output divivers.
		# When changing rate, reconfiguration of the CPLL over DRP is needed to:
		#  - update the output divider
		#  - update the equalizer configuration (specific for each line rate).
		refclk = Signal()
		self.specials += Instance("IBUFDS_GTE2",
			i_CEB=0,
			i_I=pads.refclk_p,
			i_IB=pads.refclk_n,
			o_O=refclk
		)
		self.comb += gtx.gtrefclk0.eq(refclk)

	# TX clocking
		# (SATA3) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 300MHz (16-bits), sata clk @ 150MHz (32-bits)
		# (SATA2) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 150MHz (16-bits), sata clk @ 75MHz (32-bits)
		# (SATA1) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 75MHz (16-bits), sata clk @ 37.5MHz (32-bits)
		# When changing rate, reconfiguration of the MMCM is needed to update the output divider.		
		mmcm_reset = Signal()
		mmcm_locked = Signal()
		mmcm_drp = DRPBus()
		mmcm_fb = Signal()
		mmcm_clk_i = Signal()
		mmcm_clk0_o = Signal()
		mmcm_clk1_o = Signal()
		self.specials += [
			Instance("BUFG", i_I=gtx.txoutclk, o_O=mmcm_clk_i),
			Instance("MMCME2_ADV",
				p_BANDWIDTH="HIGH", p_COMPENSATION="ZHOLD", i_RST=mmcm_reset, o_LOCKED=mmcm_locked,

				# DRP
				i_DCLK=mmcm_drp.clk, i_DEN=mmcm_drp.en, o_DRDY=mmcm_drp.rdy, i_DWE=mmcm_drp.we,
				i_DADDR=mmcm_drp.addr, i_DI=mmcm_drp.di, o_DO=mmcm_drp.do,

				# VCO
				p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=6.666,
				p_CLKFBOUT_MULT_F=8.000, p_CLKFBOUT_PHASE=0.000, p_DIVCLK_DIVIDE=1,
				i_CLKIN1=mmcm_clk_i, i_CLKFBIN=mmcm_fb, o_CLKFBOUT=mmcm_fb,

				# CLK0
				p_CLKOUT0_DIVIDE_F=4.000, p_CLKOUT0_PHASE=0.000, o_CLKOUT0=mmcm_clk0_o,

				# CLK1
				p_CLKOUT1_DIVIDE=8, p_CLKOUT1_PHASE=0.000, o_CLKOUT1=mmcm_clk1_o,
			),
			Instance("BUFG", i_I=mmcm_clk0_o, o_O=self.cd_sata_tx.clk),
			Instance("BUFG", i_I=mmcm_clk1_o, o_O=self.cd_sata.clk),
		]
		self.comb += [
			gtx.txusrclk.eq(self.cd_sata_tx.clk),
			gtx.txusrclk2.eq(self.cd_sata_tx.clk)
		]

	# RX clocking
		# (SATA3) sata_rx recovered clk @ 300MHz from CPLL RXOUTCLK
		# (SATA2) sata_rx recovered clk @ 150MHz from CPLL RXOUTCLK
		# (SATA1) sata_rx recovered clk @ 150MHz from CPLL RXOUTCLK		
		self.specials += [
			Instance("BUFG", i_I=gtx.rxoutclk, o_O=self.cd_sata_rx.clk),
		]
		self.comb += [
			gtx.rxusrclk.eq(self.cd_sata_rx.clk),
			gtx.rxusrclk2.eq(self.cd_sata_rx.clk)
		]

	# TX buffer bypass logic
		self.comb += [
			gtx.txphdlyreset.eq(0),
			gtx.txphalignen.eq(0),
			gtx.txdlyen.eq(0),
			gtx.txphalign.eq(0),
			gtx.txphinit.eq(0)
		]

	# RX buffer bypass logic
		self.comb += [
			gtx.rxphdlyreset.eq(0),
			gtx.rxdlyen.eq(0),
			gtx.rxphalign.eq(0),
			gtx.rxphalignen.eq(0),
		]


	# Configuration Reset
		# After configuration, GTX resets can not be asserted for 500ns
		# See AR43482
		reset_en = Signal()
		clk_period_ns = 1000000000/clk_freq
		reset_en_cnt_max = ceil(500/clk_period_ns)
		reset_en_cnt = Signal(max=reset_en_cnt_max, reset=reset_en_cnt_max-1)
		self.sync += If(~reset_en, reset_en_cnt.eq(reset_en_cnt-1))
		self.comb += reset_en.eq(reset_en_cnt == 0)


		# once channel TX is reseted, reset TX buffer
		txbuffer_reseted = Signal()
		self.sync += \
			If(gtx.txresetdone,
				If(~txbuffer_reseted,
					gtx.txdlysreset.eq(1),
					txbuffer_reseted.eq(1)
				).Else(
					gtx.txdlysreset.eq(0)
				)
			)

		# once channel RX is reseted, reset RX buffer
		rxbuffer_reseted = Signal()
		self.sync += \
			If(gtx.rxresetdone,
				If(~rxbuffer_reseted,
					gtx.rxdlysreset.eq(1),
					rxbuffer_reseted.eq(1)
				).Else(
					gtx.rxdlysreset.eq(0)
				)
			)

	# Reset
		# initial reset generation
		rst_cnt = Signal(8)
		rst_cnt_done = Signal()
		self.sync += \
			If(~rst_cnt_done,
				rst_cnt.eq(rst_cnt+1)
			)
		self.comb += rst_cnt_done.eq(rst_cnt==255)

		self.comb += [
		# GTXE2
			gtx.rxuserrdy.eq(gtx.cplllock),
			gtx.txuserrdy.eq(gtx.cplllock),
		# TX
			gtx.gttxreset.eq(reset_en & (self.reset | ~gtx.cplllock)),
		# RX
			gtx.gtrxreset.eq(reset_en & (self.reset | ~gtx.cplllock)),
		# PLL
			gtx.cpllreset.eq(self.reset | ~reset_en)
		]
		# SATA TX/RX clock domains
		self.specials += [
			AsyncResetSynchronizer(self.cd_sata_tx, ~mmcm_locked | ~gtx.txresetdone),
			AsyncResetSynchronizer(self.cd_sata_rx, ~gtx.cplllock | ~gtx.rxphaligndone),
			AsyncResetSynchronizer(self.cd_sata, ResetSignal("sata_tx") | ResetSignal("sata_rx")),
		]

	# Dynamic Reconfiguration
		self.submodules.reconfig = K7SATAPHYReconfig(mmcm_drp, gtx.drp)
