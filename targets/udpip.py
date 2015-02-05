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

class UDPIPBISTGeneratorUnit(Module):
	def __init__(self):
		self.start = Signal()
		self.src_port = Signal(16)
		self.dst_port = Signal(16)
		self.ip_address = Signal(32)
		self.length = Signal(16)
		self.done = Signal()

		self.source = source = Source(eth_udp_user_description(8))
		###

		counter = Counter(bits_sign=16)
		self.submodules += counter

		self.fsm = fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			self.done.eq(1),
			counter.reset.eq(1),
			If(self.start,
				NextState("SEND")
			)
		)
		self.comb += [
			source.sop.eq(counter.value == 0),
			source.eop.eq(counter.value == (self.length-1)),
			source.src_port.eq(self.src_port),
			source.dst_port.eq(self.dst_port),
			source.ip_address.eq(self.ip_address),
			source.data.eq(counter.value)
		]
		fsm.act("SEND",
			source.stb.eq(1),
			If(source.stb & source.ack,
				counter.ce.eq(1),
				If(source.eop,
					NextState("IDLE")
				)
			)
		)

class UDPIPBISTGenerator(UDPIPBISTGeneratorUnit, AutoCSR):
	def __init__(self):
		self._start = CSR()
		self._src_port = CSRStorage(16)
		self._dst_port = CSRStorage(16)
		self._ip_address = CSRStorage(32)
		self._length = CSRStorage(16)
		self._done = CSRStatus()
		###
		UDPIPBISTGeneratorUnit.__init__(self)

		self.comb += [
			self.start.eq(self._start.r & self._start.re),
			self.src_port.eq(self._src_port.storage),
			self.dst_port.eq(self._dst_port.storage),
			self.ip_address.eq(self._ip_address.storage),
			self.length.eq(self._length.storage),
			self._done.status.eq(self.done)
		]

class UDPIPSoC(GenSoC, AutoCSR):
	default_platform = "kc705"
	csr_map = {
		"ethphy":			11,
		"udpipcore":		12,
		"bist_generator": 	13
	}
	csr_map.update(GenSoC.csr_map)
	def __init__(self, platform):
		clk_freq = 166*1000000
		GenSoC.__init__(self, platform, clk_freq)
		self.submodules.crg = _CRG(platform)

		# Ethernet PHY and UDP/IP
		self.submodules.ethphy = LiteEthPHYGMII(platform.request("eth_clocks"), platform.request("eth"))
		self.submodules.udpipcore = LiteEthUDPIPCore(self.ethphy, 0x12345678, 0x10e2d5000000)

		# BIST
		self.submodules.bist_generator = UDPIPBISTGenerator()
		self.comb += [
			Record.connect(self.bist_generator.source, self.udpipcore.sink),
			self.udpipcore.source.ack.eq(1)
		]

class UDPIPSoCDevel(UDPIPSoC, AutoCSR):
	csr_map = {
		"la":			20
	}
	csr_map.update(UDPIPSoC.csr_map)
	def __init__(self, platform):
		UDPIPSoC.__init__(self, platform)

		debug = (
			Signal(),
			Signal()
		)

		self.submodules.la = LiteScopeLA(debug, 2048)
		self.la.trigger.add_port(LiteScopeTerm(self.la.dw))
		atexit.register(self.exit, platform)

	def do_finalize(self):
		UDPIPSoC.do_finalize(self)

	def exit(self, platform):
		if platform.vns is not None:
			self.la.export(platform.vns, "../test/la.csv")

default_subtarget = UDPIPSoC
