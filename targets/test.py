from migen.fhdl.std import *
from migen.bank import csrgen
from migen.bus import wishbone, csr
from migen.bus import wishbone2csr
from migen.genlib.resetsync import AsyncResetSynchronizer

from miscope.uart2wishbone import UART2Wishbone

from misoclib import identifier
from lib.sata.k7sataphy import K7SATAPHY

class _CRG(Module):
	def __init__(self, platform):
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_por = ClockDomain(reset_less=True)

		clk200 = platform.request("clk200")
		clk200_se = Signal()
		self.specials += Instance("IBUFDS", i_I=clk200.p, i_IB=clk200.n, o_O=clk200_se)

		pll_locked = Signal()
		pll_fb = Signal()
		pll_sys = Signal()
		self.specials += [
			Instance("PLLE2_BASE",
				p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

				# VCO @ 1GHz
				p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=5.0,
				p_CLKFBOUT_MULT=5, p_DIVCLK_DIVIDE=1,
				i_CLKIN1=clk200_se, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

				# 166.66MHz
				p_CLKOUT0_DIVIDE=6, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=pll_sys,

				p_CLKOUT1_DIVIDE=2, p_CLKOUT1_PHASE=0.0, #o_CLKOUT1=,

				p_CLKOUT2_DIVIDE=2, p_CLKOUT2_PHASE=0.0, #o_CLKOUT2=,

				p_CLKOUT3_DIVIDE=2, p_CLKOUT3_PHASE=0.0, #o_CLKOUT3=,

				p_CLKOUT4_DIVIDE=2, p_CLKOUT4_PHASE=0.0, #o_CLKOUT4=
			),
			Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
			AsyncResetSynchronizer(self.cd_sys, ~pll_locked),
		]

class UART2WB(Module):
	csr_base = 0x00000000
	csr_data_width = 8
	csr_map = {
		"uart2wb":			0,
		"identifier":		2,
	}
	interrupt_map = {}
	cpu_type = None
	def __init__(self, platform, clk_freq):
		self.submodules.uart2wb = UART2Wishbone(platform.request("serial"), clk_freq)

		# CSR bridge   0x00000000 (shadow @0x00000000)
		self.submodules.wishbone2csr = wishbone2csr.WB2CSR(bus_csr=csr.Interface(self.csr_data_width))
		self._wb_masters = [self.uart2wb.wishbone]
		self._wb_slaves = [(lambda a: a[23:25] == 0, self.wishbone2csr.wishbone)]

		# CSR
		self.submodules.identifier = identifier.Identifier(0, int(clk_freq), 0)

	def add_wb_master(self, wbm):
		if self.finalized:
			raise FinalizeError
		self._wb_masters.append(wbm)

	def add_wb_slave(self, address_decoder, interface):
		if self.finalized:
			raise FinalizeError
		self._wb_slaves.append((address_decoder, interface))

	def do_finalize(self):
		# Wishbone
		self.submodules.wishbonecon = wishbone.InterconnectShared(self._wb_masters,
			self._wb_slaves, register=True)

		# CSR
		self.submodules.csrbankarray = csrgen.BankArray(self,
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override],
			data_width=self.csr_data_width)
		self.submodules.csrcon = csr.Interconnect(self.wishbone2csr.csr, self.csrbankarray.get_buses())

class TestDesign(UART2WB):
	default_platform = "kc705"
	csr_map = {
		"mila":				10
	}
	csr_map.update(UART2WB.csr_map)

	def __init__(self, platform, **kwargs):
		clk_freq = 166666*1000
		UART2WB.__init__(self, platform, clk_freq)
		self.submodules.crg = _CRG(platform)

		self.submodules.sataphy_host = K7SATAPHY(platform.request("sata_host"), clk_freq, 
			host=True, default_speed="SATA1")
		self.comb += [
			self.sataphy_host.sink.stb.eq(1),
			self.sataphy_host.sink.d.eq(0x12345678)
		]

		import os
		from miscope import trigger, miio, mila
		from mibuild.tools import write_to_file
		from migen.fhdl import verilog

		term = trigger.Term(width=64)
		self.submodules.mila = mila.MiLa(width=64, depth=2048, ports=[term], with_rle=True)

		gtx = self.sataphy_host.gtx
		ctrl = self.sataphy_host.ctrl

		mila_dat = (
			gtx.rxresetdone,
			gtx.txresetdone,

			gtx.rxuserrdy,
			gtx.txuserrdy,

			gtx.rxcominitdet,
			gtx.rxcomwakedet,

			gtx.txcomfinish,
			gtx.txcominit,
			gtx.txcomwake,

		)

		self.comb += [
			self.mila.sink.stb.eq(1),
			self.mila.sink.dat.eq(Cat(*mila_dat))
		]

		try:
			gen_mila_csv = kwargs.pop('gen_mila_csv')
		except:
			gen_mila_csv = False

		if gen_mila_csv: 
			r, ns = verilog.convert(self, return_ns=True)
			mila_csv = self.mila.get_csv(mila_dat, ns)
			write_to_file(os.path.join(platform.soc_ext_path, "test", "mila.csv"), mila_csv)

default_subtarget = TestDesign
