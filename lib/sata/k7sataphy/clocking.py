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
	def __init__(self, pads, gtx):
		self.reset = Signal()
		self.transceiver_reset = Signal()

		self.clock_domains.cd_sata = ClockDomain()
		self.clock_domains.cd_sata_tx = ClockDomain()
		self.clock_domains.cd_sata_rx = ClockDomain()

	# TX clocking
		refclk = Signal()
		self.specials += Instance("IBUFDS_GTE2",
			i_CEB=0,
			i_I=pads.refclk_p,
			i_IB=pads.refclk_n,
			o_O=refclk
		)
		self.comb += gtx.gtrefclk0.eq(refclk)

		mmcm_reset = Signal()
		mmcm_locked = Signal()
		mmcm_drp = DRPBus()
		mmcm_fb = Signal()
		mmcm_clk_i = Signal()
		mmcm_clk0_o = Signal()
		mmcm_clk1_o = Signal()
		self.specials += [
			Instance("BUFG", i_I=refclk, o_O=mmcm_clk_i),
			Instance("MMCME2_ADV",
				p_BANDWIDTH="HIGH", p_COMPENSATION="ZHOLD", i_RST=mmcm_reset, o_LOCKED=mmcm_locked,

				# DRP
				i_DCLK=mmcm_drp.clk, i_DEN=mmcm_drp.en, o_DRDY=mmcm_drp.rdy, i_DWE=mmcm_drp.we,
				i_DADDR=mmcm_drp.addr, i_DI=mmcm_drp.di, o_DO=mmcm_drp.do,

				# VCO
				p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=6.666,
				p_CLKFBOUT_MULT_F=8.000, p_CLKFBOUT_PHASE=0.000, p_DIVCLK_DIVIDE=2,
				i_CLKIN1=mmcm_clk_i, i_CLKFBIN=mmcm_fb, o_CLKFBOUT=mmcm_fb,

				# CLK0
				p_CLKOUT0_DIVIDE_F=4.000, p_CLKOUT0_PHASE=0.000, o_CLKOUT0=mmcm_clk0_o,

				# CLK1
				p_CLKOUT1_DIVIDE=8, p_CLKOUT1_PHASE=0.000, o_CLKOUT1=mmcm_clk1_o,
			),
			Instance("BUFG", i_I=mmcm_clk0_o, o_O=self.cd_sata_tx.clk),
			Instance("BUFG", i_I=mmcm_clk1_o, o_O=self.cd_sata.clk),
		]

	# RX clocking
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

	# RX buffer bypass logic
		self.comb += [
			gtx.rxphdlyreset.eq(0),
			gtx.rxdlyen.eq(0),
			gtx.rxphalign.eq(0),
			gtx.rxphalignen.eq(0),
		]

		# wait till CDR is locked
		cdr_cnt = Signal(14, reset=0b10011100010000)
		cdr_locked = Signal()
		self.sync += \
			If(cdr_cnt != 0,
				cdr_cnt.eq(cdr_cnt - 1)
			).Else(
				cdr_locked.eq(1)
			)

		# once CDR is locked and channel RX reseted, reset RX buffer
		rxbuffer_reseted = Signal()
		self.sync += \
			If(cdr_locked & gtx.rxresetdone,
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
			gtx.gttxreset.eq(rst_cnt_done & (self.reset | self.transceiver_reset | ~gtx.cplllock)),
		# RX
			gtx.gtrxreset.eq(rst_cnt_done & (self.reset | self.transceiver_reset | ~gtx.cplllock)),
		# PLL
			gtx.cpllreset.eq(rst_cnt_done & self.reset)
		]
		# SATA TX/RX clock domains
		self.specials += [
			AsyncResetSynchronizer(self.cd_sata_tx, ~mmcm_locked | ~gtx.txresetdone),
			AsyncResetSynchronizer(self.cd_sata_rx, ~gtx.cplllock | ~gtx.rxphaligndone),
			AsyncResetSynchronizer(self.cd_sata, ResetSignal("sata_tx") | ResetSignal("sata_rx")),
		]

	# Dynamic Reconfiguration
		self.submodules.reconfig = K7SATAPHYReconfig(mmcm_drp, gtx.drp)
