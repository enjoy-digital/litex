import os, atexit

from migen.bank import csrgen
from migen.bus import wishbone, csr
from migen.bus import wishbone2csr
from migen.genlib.cdc import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.bank.description import *

from misoclib import identifier

from litescope.common import *
from litescope.bridge.uart2wb import LiteScopeUART2WB
from litescope.frontend.la import LiteScopeLA
from litescope.core.port import LiteScopeTerm

from liteeth.common import *
from liteeth.phy.gmii import LiteEthPHYGMII
from liteeth.core import LiteEthUDPIPCore
from liteeth.core.etherbone import LiteEthEtherbone

class _CRG(Module):
	def __init__(self, platform):
		self.clock_domains.cd_sys = ClockDomain()
		self.reset = Signal()

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

				# 166MHz
				p_CLKOUT0_DIVIDE=6, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=pll_sys,

				p_CLKOUT1_DIVIDE=2, p_CLKOUT1_PHASE=0.0, #o_CLKOUT1=,

				p_CLKOUT2_DIVIDE=2, p_CLKOUT2_PHASE=0.0, #o_CLKOUT2=,

				p_CLKOUT3_DIVIDE=2, p_CLKOUT3_PHASE=0.0, #o_CLKOUT3=,

				p_CLKOUT4_DIVIDE=2, p_CLKOUT4_PHASE=0.0, #o_CLKOUT4=
			),
			Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
			AsyncResetSynchronizer(self.cd_sys, ~pll_locked | platform.request("cpu_reset") | self.reset),
		]

class GenSoC(Module):
	csr_base = 0x00000000
	csr_data_width = 32
	csr_map = {
		"bridge":			0,
		"identifier":		1,
	}
	interrupt_map = {}
	cpu_type = None
	def __init__(self, platform, clk_freq):
		self.clk_freq = clk_freq
		# UART <--> Wishbone bridge
		self.submodules.bridge = LiteScopeUART2WB(platform.request("serial"), clk_freq, baud=921600)

		# CSR bridge   0x00000000 (shadow @0x00000000)
		self.submodules.wishbone2csr = wishbone2csr.WB2CSR(bus_csr=csr.Interface(self.csr_data_width))
		self._wb_masters = [self.bridge.wishbone]
		self._wb_slaves = [(lambda a: a[23:25] == 0, self.wishbone2csr.wishbone)]
		self.cpu_csr_regions = [] # list of (name, origin, busword, csr_list/Memory)

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

	def add_cpu_memory_region(self, name, origin, length):
		self.cpu_memory_regions.append((name, origin, length))

	def add_cpu_csr_region(self, name, origin, busword, obj):
		self.cpu_csr_regions.append((name, origin, busword, obj))

	def do_finalize(self):
		# Wishbone
		self.submodules.wishbonecon = wishbone.InterconnectShared(self._wb_masters,
			self._wb_slaves, register=True)

		# CSR
		self.submodules.csrbankarray = csrgen.BankArray(self,
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override],
			data_width=self.csr_data_width)
		self.submodules.csrcon = csr.Interconnect(self.wishbone2csr.csr, self.csrbankarray.get_buses())
		for name, csrs, mapaddr, rmap in self.csrbankarray.banks:
			self.add_cpu_csr_region(name, 0xe0000000+0x800*mapaddr, flen(rmap.bus.dat_w), csrs)
		for name, memory, mapaddr, mmap in self.csrbankarray.srams:
			self.add_cpu_csr_region(name, 0xe0000000+0x800*mapaddr, flen(rmap.bus.dat_w), memory)

class EtherboneSoC(GenSoC, AutoCSR):
	default_platform = "kc705"
	csr_map = {
		"phy":		11,
		"core":		12
	}
	csr_map.update(GenSoC.csr_map)
	def __init__(self, platform):
		clk_freq = 166*1000000
		GenSoC.__init__(self, platform, clk_freq)
		self.submodules.crg = _CRG(platform)

		# Ethernet PHY and UDP/IP
		self.submodules.phy = LiteEthPHYGMII(platform.request("eth_clocks"), platform.request("eth"))
		self.submodules.core = LiteEthUDPIPCore(self.phy, 0x10e2d5000000, convert_ip("192.168.1.40"), clk_freq)

		# Etherbone
		self.submodules.etherbone = LiteEthEtherbone(self.core.udp, 20000)

class EtherboneSoCDevel(EtherboneSoC, AutoCSR):
	csr_map = {
		"la":			20
	}
	csr_map.update(EtherboneSoC.csr_map)
	def __init__(self, platform):
		EtherboneSoC.__init__(self, platform)
		debug = (
			self.etherbone.master.bus.adr,
			self.etherbone.master.bus.dat_w,
			self.etherbone.master.bus.dat_r,
			self.etherbone.master.bus.sel,
			self.etherbone.master.bus.cyc,
			self.etherbone.master.bus.stb,
			self.etherbone.master.bus.ack,
			self.etherbone.master.bus.we,
			self.etherbone.master.bus.cti,
			self.etherbone.master.bus.bte,
			self.etherbone.master.bus.err
		)

		self.submodules.la = LiteScopeLA(debug, 4096)
		self.la.trigger.add_port(LiteScopeTerm(self.la.dw))
		atexit.register(self.exit, platform)

	def do_finalize(self):
		EtherboneSoC.do_finalize(self)

	def exit(self, platform):
		if platform.vns is not None:
			self.la.export(platform.vns, "../test/la.csv")
default_subtarget = EtherboneSoC
