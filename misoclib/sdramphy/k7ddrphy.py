# tCK=5ns CL=8 CWL=6

from migen.fhdl.std import *
from migen.bus.dfi import *

from misoclib import lasmicon

class K7DDRPHY(Module):
	def __init__(self, pads, memtype):
		a = flen(pads.a)
		ba = flen(pads.ba)
		d = flen(pads.dq)
		nphases = 4

		self.phy_settings = lasmicon.PhySettings(
			memtype=memtype,
			dfi_d=2*d,
			nphases=nphases,
			rdphase=0,
			wrphase=2,
			rdcmdphase=1,
			wrcmdphase=0,
			cl=8,
			cwl=6,
			read_latency=8,
			write_latency=2
		)

		self.dfi = Interface(a, ba, self.phy_settings.dfi_d, nphases)

		sd_clk_se = Signal()
		self.specials += [
			Instance("OSERDESE2",
				p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
				p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="SDR",
				p_SERDES_MODE="MASTER",

				o_OQ=sd_clk_se,
				i_OCE=1,
				i_RST=ResetSignal(),
				i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
				i_D1=0, i_D2=1, i_D3=0, i_D4=1,
				i_D5=0, i_D6=1, i_D7=0, i_D8=1
			),
			Instance("OBUFDS",
				i_I=sd_clk_se,
				o_O=pads.clk_p,
				o_OB=pads.clk_n
			)
		]

		for i in range(a):
			self.specials += \
				Instance("OSERDESE2",
					p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
					p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="SDR",
					p_SERDES_MODE="MASTER",

					o_OQ=pads.a[i],
					i_OCE=1,
					i_RST=ResetSignal(),
					i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
					i_D1=self.dfi.phases[0].address[i], i_D2=self.dfi.phases[0].address[i],
					i_D3=self.dfi.phases[1].address[i], i_D4=self.dfi.phases[1].address[i],
					i_D5=self.dfi.phases[2].address[i], i_D6=self.dfi.phases[2].address[i],
					i_D7=self.dfi.phases[3].address[i], i_D8=self.dfi.phases[3].address[i]
				)
		for i in range(ba):
			self.specials += \
				Instance("OSERDESE2",
					p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
					p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="SDR",
					p_SERDES_MODE="MASTER",

					o_OQ=pads.ba[i],
					i_OCE=1,
					i_RST=ResetSignal(),
					i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
					i_D1=self.dfi.phases[0].bank[i], i_D2=self.dfi.phases[0].bank[i],
					i_D3=self.dfi.phases[1].bank[i], i_D4=self.dfi.phases[1].bank[i],
					i_D5=self.dfi.phases[2].bank[i], i_D6=self.dfi.phases[2].bank[i],
					i_D7=self.dfi.phases[3].bank[i], i_D8=self.dfi.phases[3].bank[i]
				)
		for name in "ras_n", "cas_n", "we_n", "cs_n", "cke", "odt", "reset_n":
			self.specials += \
				Instance("OSERDESE2",
					p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
					p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="SDR",
					p_SERDES_MODE="MASTER",

					o_OQ=getattr(pads, name),
					i_OCE=1,
					i_RST=ResetSignal(),
					i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
					i_D1=getattr(self.dfi.phases[0], name), i_D2=getattr(self.dfi.phases[0], name),
					i_D3=getattr(self.dfi.phases[1], name), i_D4=getattr(self.dfi.phases[1], name),
					i_D5=getattr(self.dfi.phases[2], name), i_D6=getattr(self.dfi.phases[2], name),
					i_D7=getattr(self.dfi.phases[3], name), i_D8=getattr(self.dfi.phases[3], name)
				)

		oe = Signal()
		for i in range(d//8):
			self.specials += \
				Instance("OSERDESE2",
					p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
					p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="SDR",
					p_SERDES_MODE="MASTER",

					o_OQ=pads.dm[i],
					i_OCE=1,
					i_RST=ResetSignal(),
					i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
					i_D1=self.dfi.phases[0].wrdata_mask[i], i_D2=self.dfi.phases[0].wrdata_mask[d//8+i],
					i_D3=self.dfi.phases[1].wrdata_mask[i], i_D4=self.dfi.phases[1].wrdata_mask[d//8+i],
					i_D5=self.dfi.phases[2].wrdata_mask[i], i_D6=self.dfi.phases[2].wrdata_mask[d//8+i],
					i_D7=self.dfi.phases[3].wrdata_mask[i], i_D8=self.dfi.phases[3].wrdata_mask[d//8+i]
				)
			dqs_nodelay = Signal()
			dqs_delayed = Signal()
			dqs_t = Signal()
			self.specials += [
				Instance("OSERDESE2",
					p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
					p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="SDR",
					p_SERDES_MODE="MASTER",

					o_OFB=dqs_nodelay, o_TQ=dqs_t,
					i_OCE=1, i_TCE=1,
					i_RST=ResetSignal(),
					i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
					i_D1=1, i_D2=0, i_D3=1, i_D4=0,
					i_D5=1, i_D6=0, i_D7=1, i_D8=0,
					i_T1=~oe
				),
				Instance("ODELAYE2",
					p_DELAY_SRC="ODATAIN", p_SIGNAL_PATTERN="DATA",
					p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE", p_REFCLK_FREQUENCY=200.0,
					p_PIPE_SEL="FALSE", p_ODELAY_TYPE="FIXED", p_ODELAY_VALUE=6,

					o_ODATAIN=dqs_nodelay, o_DATAOUT=dqs_delayed
				),
				Instance("OBUFTDS",
					i_I=dqs_delayed, i_T=dqs_t,
					o_O=pads.dqs_p[i], o_OB=pads.dqs_n[i]
				)
			]

		for i in range(d):
			dq_o_nodelay = Signal()
			dq_o_delayed = Signal()
			dq_i_nodelay = Signal()
			dq_i_delayed = Signal()
			dq_t = Signal()
			self.specials += [
				Instance("OSERDESE2",
					p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
					p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="SDR",
					p_SERDES_MODE="MASTER",

					o_OQ=dq_o_nodelay, o_TQ=dq_t,
					i_OCE=1, i_TCE=1,
					i_RST=ResetSignal(),
					i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
					i_D1=self.dfi.phases[0].wrdata[i], i_D2=self.dfi.phases[0].wrdata[d+i],
					i_D3=self.dfi.phases[1].wrdata[i], i_D4=self.dfi.phases[1].wrdata[d+i],
					i_D5=self.dfi.phases[2].wrdata[i], i_D6=self.dfi.phases[2].wrdata[d+i],
					i_D7=self.dfi.phases[3].wrdata[i], i_D8=self.dfi.phases[3].wrdata[d+i],
					i_T1=~oe
				),
				Instance("ISERDESE2",
					p_DATA_WIDTH=8, p_DATA_RATE="DDR",
					p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
					p_NUM_CE=1, p_IOBDELAY="BOTH",

					i_DDLY=dq_i_delayed,
					i_CE1=1,
					i_RST=ResetSignal(),
					i_CLK=ClockSignal("sys4x"), i_CLKB=~ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
					o_Q8=self.dfi.phases[0].rddata[i], o_Q7=self.dfi.phases[0].rddata[d+i],
					o_Q6=self.dfi.phases[1].rddata[i], o_Q5=self.dfi.phases[1].rddata[d+i],
					o_Q4=self.dfi.phases[2].rddata[i], o_Q3=self.dfi.phases[2].rddata[d+i],
					o_Q2=self.dfi.phases[3].rddata[i], o_Q1=self.dfi.phases[3].rddata[d+i]
				),
				Instance("ODELAYE2",
					p_DELAY_SRC="ODATAIN", p_SIGNAL_PATTERN="DATA",
					p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE", p_REFCLK_FREQUENCY=200.0,
					p_PIPE_SEL="FALSE", p_ODELAY_TYPE="FIXED", p_ODELAY_VALUE=0,

					o_ODATAIN=dq_o_nodelay, o_DATAOUT=dq_o_delayed
				),
				Instance("IDELAYE2",
					p_DELAY_SRC="IDATAIN", p_SIGNAL_PATTERN="DATA",
					p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE", p_REFCLK_FREQUENCY=200.0,
					p_PIPE_SEL="FALSE", p_IDELAY_TYPE="FIXED", p_IDELAY_VALUE=6,

					i_IDATAIN=dq_i_nodelay, o_DATAOUT=dq_i_delayed
				),
				Instance("IOBUF",
					i_I=dq_o_delayed, o_O=dq_i_nodelay, i_T=dq_t,
					io_IO=pads.dq[i]
				)
			]

		# total read latency = 8:
		#  2 cycles through OSERDESE2
		#  4 cycles CAS
		#  2 cycles through ISERDESE2
		rddata_en = self.dfi.phases[self.phy_settings.rdphase].rddata_en
		for i in range(7):
			n_rddata_en = Signal()
			self.sync += n_rddata_en.eq(rddata_en)
			rddata_en = n_rddata_en
		self.sync += [phase.rddata_valid.eq(rddata_en) for phase in self.dfi.phases]

		last_wrdata_en = Signal(5)
		wrphase = self.dfi.phases[self.phy_settings.wrphase]
		self.sync += last_wrdata_en.eq(Cat(wrphase.wrdata_en, last_wrdata_en[:4]))
		self.comb += oe.eq(last_wrdata_en[2+0] | last_wrdata_en[2+1] | last_wrdata_en[2+2])
