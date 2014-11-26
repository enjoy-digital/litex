# 1:2 frequency-ratio DDR / LPDDR / DDR2 PHY for Spartan-6
#
# Assert dfi_wrdata_en and present the data
# on dfi_wrdata_mask/dfi_wrdata in the same
# cycle as the write command.
#
# Assert dfi_rddata_en in the same cycle as the read
# command. The data will come back on dfi_rddata
# 5 cycles later, along with the assertion
# of dfi_rddata_valid.
#
# This PHY only supports CAS Latency 3.
# Read commands must be sent on phase 0.
# Write commands must be sent on phase 1.
#

from migen.fhdl.std import *
from migen.bus.dfi import *
from migen.genlib.record import *

from misoclib import sdram

class S6DDRPHY(Module):
	def __init__(self, pads, memtype, rd_bitslip, wr_bitslip, dqs_ddr_alignment):
		if memtype not in ["DDR", "LPDDR", "DDR2"]:
			raise NotImplementedError("S6DDRPHY only supports DDR, LPDDR and DDR2")
		a = flen(pads.a)
		ba = flen(pads.ba)
		d = flen(pads.dq)
		nphases = 2

		self.phy_settings = sdram.PhySettings(
			memtype=memtype,
			dfi_d=2*d,
			nphases=nphases,
			rdphase=0,
			wrphase=1,
			rdcmdphase=1,
			wrcmdphase=0,
			cl=3,
			read_latency=5,
			write_latency=0
		)

		self.dfi = Interface(a, ba, self.phy_settings.dfi_d, nphases)
		self.clk4x_wr_strb = Signal()
		self.clk4x_rd_strb = Signal()

		###

		# sys_clk           : system clk, used for dfi interface
		# sdram_half_clk    : half rate sdram clk
		# sdram_full_wr_clk : full rate sdram write clk
		# sdram_full_rd_clk : full rate sdram read clk
		sd_sys = getattr(self.sync, "sys")
		sd_sdram_half = getattr(self.sync, "sdram_half")

		sys_clk = ClockSignal("sys")
		sdram_half_clk = ClockSignal("sdram_half")
		sdram_full_wr_clk = ClockSignal("sdram_full_wr")
		sdram_full_rd_clk = ClockSignal("sdram_full_rd")

		#
		# Command/address
		#

		# select active phase
		#             sys_clk   ----____----____
		#  phase_sel(nphases=2) 0   1   0   1     Half Rate
		phase_sel = Signal(log2_int(nphases))
		sys_clk_d = Signal()

		sd_sdram_half += [
			If(sys_clk & ~sys_clk_d,
				phase_sel.eq(0)
			).Else(
				phase_sel.eq(phase_sel+1)
			),
			sys_clk_d.eq(sys_clk)
		]

		# register dfi cmds on half_rate clk
		r_dfi = Array(Record(phase_cmd_description(a, ba)) for i in range(nphases))
		for n, phase in enumerate(self.dfi.phases):
			sd_sdram_half +=[
				r_dfi[n].address.eq(phase.address),
				r_dfi[n].bank.eq(phase.bank),
				r_dfi[n].cs_n.eq(phase.cs_n),
				r_dfi[n].cke.eq(phase.cke),
				r_dfi[n].cas_n.eq(phase.cas_n),
				r_dfi[n].ras_n.eq(phase.ras_n),
				r_dfi[n].we_n.eq(phase.we_n)
			]

		# output cmds
		sd_sdram_half += [
			pads.a.eq(r_dfi[phase_sel].address),
			pads.ba.eq(r_dfi[phase_sel].bank),
			pads.cke.eq(r_dfi[phase_sel].cke),
			pads.ras_n.eq(r_dfi[phase_sel].ras_n),
			pads.cas_n.eq(r_dfi[phase_sel].cas_n),
			pads.we_n.eq(r_dfi[phase_sel].we_n)
		]
		if hasattr(pads, "cs_n"):
			sd_sdram_half += pads.cs_n.eq(r_dfi[phase_sel].cs_n)

		#
		# Bitslip
		#
		bitslip_cnt = Signal(4)
		bitslip_inc = Signal()

		sd_sys += [
			If(bitslip_cnt == rd_bitslip,
				bitslip_inc.eq(0)
			).Else(
				bitslip_cnt.eq(bitslip_cnt+1),
				bitslip_inc.eq(1)
			)
		]

		#
		# DQ/DQS/DM data
		#
		sdram_half_clk_n = Signal()
		self.comb += sdram_half_clk_n.eq(~sdram_half_clk)

		postamble = Signal()
		drive_dqs = Signal()
		dqs_t_d0 = Signal()
		dqs_t_d1 = Signal()

		dqs_o = Signal(d//8)
		dqs_t = Signal(d//8)

		self.comb += [
			dqs_t_d0.eq(~(drive_dqs | postamble)),
			dqs_t_d1.eq(~drive_dqs),
		]

		for i in range(d//8):
			# DQS output
			self.specials += Instance("ODDR2",
				p_DDR_ALIGNMENT=dqs_ddr_alignment,
				p_INIT=0,
				p_SRTYPE="ASYNC",

				i_C0=sdram_half_clk,
				i_C1=sdram_half_clk_n,

				i_CE=1,
				i_D0=0,
				i_D1=1,
				i_R=0,
				i_S=0,

				o_Q=dqs_o[i]
			)

			# DQS tristate cmd
			self.specials += Instance("ODDR2",
				p_DDR_ALIGNMENT=dqs_ddr_alignment,
				p_INIT=0,
				p_SRTYPE="ASYNC",

				i_C0=sdram_half_clk,
				i_C1=sdram_half_clk_n,

				i_CE=1,
				i_D0=dqs_t_d0,
				i_D1=dqs_t_d1,
				i_R=0,
				i_S=0,

				o_Q=dqs_t[i]
			)

			# DQS tristate buffer
			if hasattr(pads, "dqs_n"):
				self.specials += Instance("OBUFTDS",
					i_I=dqs_o[i],
					i_T=dqs_t[i],

					o_O=pads.dqs[i],
					o_OB=pads.dqs_n[i],
				)
			else:
				self.specials += Instance("OBUFT",
					i_I=dqs_o[i],
					i_T=dqs_t[i],

					o_O=pads.dqs[i]
				)

		sd_sdram_half += postamble.eq(drive_dqs)

		d_dfi = [Record(phase_wrdata_description(nphases*d)+phase_rddata_description(nphases*d))
			for i in range(2*nphases)]

		for n, phase in enumerate(self.dfi.phases):
			self.comb += [
				d_dfi[n].wrdata.eq(phase.wrdata),
				d_dfi[n].wrdata_mask.eq(phase.wrdata_mask),
				d_dfi[n].wrdata_en.eq(phase.wrdata_en),
				d_dfi[n].rddata_en.eq(phase.rddata_en),
			]
			sd_sys += [
				d_dfi[nphases+n].wrdata.eq(phase.wrdata),
				d_dfi[nphases+n].wrdata_mask.eq(phase.wrdata_mask)
			]


		drive_dq = Signal()
		drive_dq_n = [Signal() for i in range(2)]
		self.comb += drive_dq_n[0].eq(~drive_dq)
		sd_sys += drive_dq_n[1].eq(drive_dq_n[0])

		dq_t = Signal(d)
		dq_o = Signal(d)
		dq_i = Signal(d)

		dq_wrdata = []
		for i in range(2):
			for j in reversed(range(nphases)):
				dq_wrdata.append(d_dfi[i*nphases+j].wrdata[:d])
				dq_wrdata.append(d_dfi[i*nphases+j].wrdata[d:])

		for i in range(d):
			# Data serializer
			self.specials += Instance("OSERDES2",
				p_DATA_WIDTH=4,
				p_DATA_RATE_OQ="SDR",
				p_DATA_RATE_OT="SDR",
				p_SERDES_MODE="NONE",
				p_OUTPUT_MODE="SINGLE_ENDED",

				o_OQ=dq_o[i],
				i_OCE=1,
				i_CLK0=sdram_full_wr_clk,
				i_CLK1=0,
				i_IOCE=self.clk4x_wr_strb,
				i_RST=0,
				i_CLKDIV=sys_clk,

				i_D1=dq_wrdata[wr_bitslip+3][i],
				i_D2=dq_wrdata[wr_bitslip+2][i],
				i_D3=dq_wrdata[wr_bitslip+1][i],
				i_D4=dq_wrdata[wr_bitslip+0][i],

				o_TQ=dq_t[i],
				i_T1=drive_dq_n[(wr_bitslip+3)//4],
				i_T2=drive_dq_n[(wr_bitslip+2)//4],
				i_T3=drive_dq_n[(wr_bitslip+1)//4],
				i_T4=drive_dq_n[(wr_bitslip+0)//4],
				i_TRAIN=0,
				i_TCE=1,
				i_SHIFTIN1=0,
				i_SHIFTIN2=0,
				i_SHIFTIN3=0,
				i_SHIFTIN4=0,
			)

			# Data deserializer
			self.specials += Instance("ISERDES2",
				p_DATA_WIDTH=4,
				p_DATA_RATE="SDR",
				p_BITSLIP_ENABLE="TRUE",
				p_SERDES_MODE="NONE",
				p_INTERFACE_TYPE="RETIMED",

				i_D=dq_i[i],
				i_CE0=1,
				i_CLK0=sdram_full_rd_clk,
				i_CLK1=0,
				i_IOCE=self.clk4x_rd_strb,
				i_RST=ResetSignal(),
				i_CLKDIV=sys_clk,
				i_BITSLIP=bitslip_inc,

				o_Q1=d_dfi[0*nphases+0].rddata[i+d],
				o_Q2=d_dfi[0*nphases+0].rddata[i],
				o_Q3=d_dfi[0*nphases+1].rddata[i+d],
				o_Q4=d_dfi[0*nphases+1].rddata[i],
			)

			# Data buffer
			self.specials += Instance("IOBUF",
				i_I=dq_o[i],
				o_O=dq_i[i],
				i_T=dq_t[i],
				io_IO=pads.dq[i]
			)

		dq_wrdata_mask = []
		for i in range(2):
			for j in reversed(range(nphases)):
				dq_wrdata_mask.append(d_dfi[i*nphases+j].wrdata_mask[:d//8])
				dq_wrdata_mask.append(d_dfi[i*nphases+j].wrdata_mask[d//8:])

		for i in range(d//8):
			# Mask serializer
			self.specials += Instance("OSERDES2",
				p_DATA_WIDTH=4,
				p_DATA_RATE_OQ="SDR",
				p_DATA_RATE_OT="SDR",
				p_SERDES_MODE="NONE",
				p_OUTPUT_MODE="SINGLE_ENDED",

				o_OQ=pads.dm[i],
				i_OCE=1,
				i_CLK0=sdram_full_wr_clk,
				i_CLK1=0,
				i_IOCE=self.clk4x_wr_strb,
				i_RST=0,
				i_CLKDIV=sys_clk,

				i_D1=dq_wrdata_mask[wr_bitslip+3][i],
				i_D2=dq_wrdata_mask[wr_bitslip+2][i],
				i_D3=dq_wrdata_mask[wr_bitslip+1][i],
				i_D4=dq_wrdata_mask[wr_bitslip+0][i],

				i_TRAIN=0,
				i_TCE=0,
				i_SHIFTIN1=0,
				i_SHIFTIN2=0,
				i_SHIFTIN3=0,
				i_SHIFTIN4=0,
			)

		#
		# ODT
		#
		# ODT not yet supported
		if hasattr(pads, "odt"):
			self.comb += pads.odt.eq(0)

		#
		# DQ/DQS/DM control
		#
		self.comb += drive_dq.eq(d_dfi[self.phy_settings.wrphase].wrdata_en)

		d_dfi_wrdata_en = Signal()
		sd_sys += d_dfi_wrdata_en.eq(d_dfi[self.phy_settings.wrphase].wrdata_en)

		r_dfi_wrdata_en = Signal(2)
		sd_sdram_half += r_dfi_wrdata_en.eq(Cat(d_dfi_wrdata_en, r_dfi_wrdata_en[0]))

		self.comb += drive_dqs.eq(r_dfi_wrdata_en[1])

		rddata_sr = Signal(self.phy_settings.read_latency)
		sd_sys += rddata_sr.eq(Cat(rddata_sr[1:self.phy_settings.read_latency],
			d_dfi[self.phy_settings.rdphase].rddata_en))

		for n, phase in enumerate(self.dfi.phases):
			self.comb += [
				phase.rddata.eq(d_dfi[n].rddata),
				phase.rddata_valid.eq(rddata_sr[0]),
			]
