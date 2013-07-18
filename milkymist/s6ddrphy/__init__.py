# 1:2 frequency-ratio DDR / LPDDR / DDR2 PHY for 
# Spartan-6
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

# Todo:
#	- use CSR for bitslip?
#	- add configurable CAS Latency
#	- automatically determines wrphase / rdphase / latencies

from migen.fhdl.std import *
from migen.bus.dfi import *
from migen.genlib.record import *

from milkymist import lasmicon

class S6DDRPHY(Module):
	def __init__(self, pads, memtype, nphases, cl, bitslip):
		if memtype not in ["DDR", "LPDDR", "DDR2"]:
			raise NotImplementedError("S6DDRPHY only supports DDR, LPDDR and DDR2")
		if cl != 3:
			raise NotImplementedError("S6DDRPHY only supports CAS LATENCY 3")

		a = flen(pads.a)
		ba = flen(pads.ba)
		d = flen(pads.dq)

		self.phy_settings = lasmicon.PhySettings(
			memtype=memtype,
			dfi_d=2*d,
			nphases=nphases,
			rdphase=0,
			wrphase=1,
			cl=cl,
			read_latency=5,
			write_latency=0
		)

		self.dfi = Interface(a, ba, nphases*d, nphases)
		self.clk4x_wr_strb = Signal()
		self.clk4x_rd_strb = Signal()

		###

		# sys_clk           : system clk, used for dfi interface
		# sdram_half_clk    : half rate sdram clk 
		# sdram_full_wr_clk : full rate sdram write clk
		# sdram_full_rd_clk : full rate sdram write clk
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
		#  phase_sel(nphases=1) 0       0
		#  phase_sel(nphases=2) 0   1   0   1
		#  phase_sel(nphases=4) 0 1 2 3 0 1 2 3
		phase_sel = Signal(log2_int(nphases))
		sys_clk_d = Signal()

		sd_sdram_half += [
			If(sys_clk & ~sys_clk_d, phase_sel.eq(0)
			).Else(phase_sel.eq(phase_sel+1)),
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
			If(bitslip_cnt == bitslip, 
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
				Instance.Parameter("DDR_ALIGNMENT", "C1"),
				Instance.Parameter("INIT", 0),
				Instance.Parameter("SRTYPE", "ASYNC"),

				Instance.Input("C0", sdram_half_clk),
				Instance.Input("C1", sdram_half_clk_n),

				Instance.Input("CE", 1),
				Instance.Input("D0", 0),
				Instance.Input("D1", 1),
				Instance.Input("R", 0),
				Instance.Input("S", 0),

				Instance.Output("Q", dqs_o[i])
			)

			# DQS tristate cmd
			self.specials += Instance("ODDR2",
				Instance.Parameter("DDR_ALIGNMENT", "C1"),
				Instance.Parameter("INIT", 0),
				Instance.Parameter("SRTYPE", "ASYNC"),

				Instance.Input("C0", sdram_half_clk),
				Instance.Input("C1", sdram_half_clk_n),

				Instance.Input("CE", 1),
				Instance.Input("D0", dqs_t_d0),
				Instance.Input("D1", dqs_t_d1),
				Instance.Input("R", 0),
				Instance.Input("S", 0),

				Instance.Output("Q", dqs_t[i])
			)

			# DQS tristate buffer
			if hasattr(pads, "dqs_n"):
				self.specials += Instance("OBUFTDS",
					Instance.Input("I", dqs_o[i]),
					Instance.Input("T", dqs_t[i]),

					Instance.Output("O", pads.dqs[i]),
					Instance.Output("OB", pads.dqs_n[i]),
				)
			else:
				self.specials += Instance("OBUFT",
					Instance.Input("I", dqs_o[i]),
					Instance.Input("T", dqs_t[i]),

					Instance.Output("O", pads.dqs[i])
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
		drive_dq_n = Signal()
		d_drive_dq = Signal()
		d_drive_dq_n = Signal()
		self.comb += [
			drive_dq_n.eq(~drive_dq),
			d_drive_dq_n.eq(~d_drive_dq)
		]

		dq_t = Signal(d)
		dq_o = Signal(d)
		dq_i = Signal(d)

		for i in range(d):
			# Data serializer
			self.specials += Instance("OSERDES2",
				Instance.Parameter("DATA_WIDTH", 4),
				Instance.Parameter("DATA_RATE_OQ", "SDR"),
				Instance.Parameter("DATA_RATE_OT", "SDR"),
				Instance.Parameter("SERDES_MODE", "NONE"),
				Instance.Parameter("OUTPUT_MODE", "SINGLE_ENDED"),

				Instance.Output("OQ", dq_o[i]),
				Instance.Input("OCE", 1),
				Instance.Input("CLK0", sdram_full_wr_clk),
				Instance.Input("CLK1", 0),
				Instance.Input("IOCE", self.clk4x_wr_strb),
				Instance.Input("RST", 0),
				Instance.Input("CLKDIV", sys_clk),

				Instance.Input("D1", d_dfi[1*nphases+0].wrdata[i]),
				Instance.Input("D2", d_dfi[1*nphases+1].wrdata[i+d]),
				Instance.Input("D3", d_dfi[1*nphases+1].wrdata[i]),
				Instance.Input("D4", d_dfi[0*nphases+0].wrdata[i+d]),
				Instance.Output("TQ", dq_t[i]),
				Instance.Input("T1", d_drive_dq_n),
				Instance.Input("T2", d_drive_dq_n),
				Instance.Input("T3", d_drive_dq_n),
				Instance.Input("T4", drive_dq_n),
				Instance.Input("TRAIN", 0),
				Instance.Input("TCE", 1),
				Instance.Input("SHIFTIN1", 0),
				Instance.Input("SHIFTIN2", 0),
				Instance.Input("SHIFTIN3", 0),
				Instance.Input("SHIFTIN4", 0),

				Instance.Output("SHIFTOUT1"),
				Instance.Output("SHIFTOUT2"),
				Instance.Output("SHIFTOUT3"),
				Instance.Output("SHIFTOUT4"),
			)

			# Data deserializer
			self.specials += Instance("ISERDES2",
				Instance.Parameter("DATA_WIDTH", 4),
				Instance.Parameter("DATA_RATE", "SDR"),
				Instance.Parameter("BITSLIP_ENABLE", "TRUE"),
				Instance.Parameter("SERDES_MODE", "NONE"),
				Instance.Parameter("INTERFACE_TYPE", "RETIMED"),

				Instance.Input("D", dq_i[i]),
				Instance.Input("CE0", 1),
				Instance.Input("CLK0", sdram_full_rd_clk),
				Instance.Input("CLK1", 0),
				Instance.Input("IOCE", self.clk4x_rd_strb),
				Instance.Input("RST", ResetSignal()),
				Instance.Input("CLKDIV", sys_clk),
				Instance.Output("SHIFTIN"),
				Instance.Input("BITSLIP", bitslip_inc),
				Instance.Output("FABRICOUT"),

				Instance.Output("Q1", d_dfi[0*nphases+0].rddata[i+d]),
				Instance.Output("Q2", d_dfi[0*nphases+0].rddata[i]),
				Instance.Output("Q3", d_dfi[0*nphases+1].rddata[i+d]),
				Instance.Output("Q4", d_dfi[0*nphases+1].rddata[i]),

				Instance.Output("DFB"),
				Instance.Output("CFB0"),
				Instance.Output("CFB1"),
				Instance.Output("VALID"),
				Instance.Output("INCDEC"),
				Instance.Output("SHIFTOUT")
			)

			# Data buffer
			self.specials += Instance("IOBUF",
				Instance.Input("I", dq_o[i]),
				Instance.Output("O", dq_i[i]),
				Instance.Input("T", dq_t[i]),
				Instance.InOut("IO", pads.dq[i])
			)

		for i in range(d//8):
			# Mask serializer
			self.specials += Instance("OSERDES2",
				Instance.Parameter("DATA_WIDTH", 4),
				Instance.Parameter("DATA_RATE_OQ", "SDR"),
				Instance.Parameter("DATA_RATE_OT", "SDR"),
				Instance.Parameter("SERDES_MODE", "NONE"),
				Instance.Parameter("OUTPUT_MODE", "SINGLE_ENDED"),

				Instance.Output("OQ", pads.dm[i]),
				Instance.Input("OCE", 1),
				Instance.Input("CLK0", sdram_full_wr_clk),
				Instance.Input("CLK1", 0),
				Instance.Input("IOCE", self.clk4x_wr_strb),
				Instance.Input("RST", 0),
				Instance.Input("CLKDIV", sys_clk),

				Instance.Input("D1", d_dfi[1*nphases+0].wrdata_mask[i]),
				Instance.Input("D2", d_dfi[1*nphases+1].wrdata_mask[i+d//8]),
				Instance.Input("D3", d_dfi[1*nphases+1].wrdata_mask[i]),
				Instance.Input("D4", d_dfi[0*nphases+0].wrdata_mask[i+d//8]),
				Instance.Output("TQ"),
				Instance.Input("T1"),
				Instance.Input("T2"),
				Instance.Input("T3"),
				Instance.Input("T4"),
				Instance.Input("TRAIN", 0),
				Instance.Input("TCE", 0),
				Instance.Input("SHIFTIN1", 0),
				Instance.Input("SHIFTIN2", 0),
				Instance.Input("SHIFTIN3", 0),
				Instance.Input("SHIFTIN4", 0),

				Instance.Output("SHIFTOUT1"),
				Instance.Output("SHIFTOUT2"),
				Instance.Output("SHIFTOUT3"),
				Instance.Output("SHIFTOUT4"),
			)

		# 
		# DQ/DQS/DM control
		#
		self.comb += drive_dq.eq(d_dfi[self.phy_settings.wrphase].wrdata_en)
		sd_sys += d_drive_dq.eq(drive_dq)

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
