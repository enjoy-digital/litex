import os

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
from liteeth.generic import *
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

class UDPSoC(GenSoC, AutoCSR):
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

		# Create loopback on UDP port 6000 (dw=8)
		loopback_port = self.core.udp.crossbar.get_port(6000, dw=8)
		loopback_buffer = PacketBuffer(eth_udp_user_description(8), 8192, 8)
		self.submodules += loopback_buffer
		self.comb += Port.connect(loopback_port, loopback_buffer)

		# Create loopback on UDP port 8000 (dw=32)
		loopback_port = self.core.udp.crossbar.get_port(8000, dw=32)
		loopback_buffer = PacketBuffer(eth_udp_user_description(32), 2048, 8)
		self.submodules += loopback_buffer
		self.comb += Port.connect(loopback_port, loopback_buffer)

class UDPSoCDevel(UDPSoC, AutoCSR):
	csr_map = {
		"la":			20
	}
	csr_map.update(UDPSoC.csr_map)
	def __init__(self, platform):
		UDPSoC.__init__(self, platform)

		self.core_icmp_rx_fsm_state = Signal(4)
		self.core_icmp_tx_fsm_state = Signal(4)
		self.core_udp_rx_fsm_state = Signal(4)
		self.core_udp_tx_fsm_state = Signal(4)
		self.core_ip_rx_fsm_state = Signal(4)
		self.core_ip_tx_fsm_state = Signal(4)
		self.core_arp_rx_fsm_state = Signal(4)
		self.core_arp_tx_fsm_state = Signal(4)
		self.core_arp_table_fsm_state = Signal(4)

		debug = (
			self.core.mac.core.sink.stb,
			self.core.mac.core.sink.sop,
			self.core.mac.core.sink.eop,
			self.core.mac.core.sink.ack,
			self.core.mac.core.sink.data,

			self.core.mac.core.source.stb,
			self.core.mac.core.source.sop,
			self.core.mac.core.source.eop,
			self.core.mac.core.source.ack,
			self.core.mac.core.source.data,

			self.core.icmp.echo.sink.stb,
			self.core.icmp.echo.sink.sop,
			self.core.icmp.echo.sink.eop,
			self.core.icmp.echo.sink.ack,
			self.core.icmp.echo.sink.data,

			self.core.icmp.echo.source.stb,
			self.core.icmp.echo.source.sop,
			self.core.icmp.echo.source.eop,
			self.core.icmp.echo.source.ack,
			self.core.icmp.echo.source.data,

			self.core.ip.crossbar.master.sink.stb,
			self.core.ip.crossbar.master.sink.sop,
			self.core.ip.crossbar.master.sink.eop,
			self.core.ip.crossbar.master.sink.ack,
			self.core.ip.crossbar.master.sink.data,
			self.core.ip.crossbar.master.sink.ip_address,
			self.core.ip.crossbar.master.sink.protocol,

			self.phy.sink.stb,
			self.phy.sink.sop,
			self.phy.sink.eop,
			self.phy.sink.ack,
			self.phy.sink.data,

			self.phy.source.stb,
			self.phy.source.sop,
			self.phy.source.eop,
			self.phy.source.ack,
			self.phy.source.data,

			self.core_icmp_rx_fsm_state,
			self.core_icmp_tx_fsm_state,
			self.core_udp_rx_fsm_state,
			self.core_udp_tx_fsm_state,
			self.core_ip_rx_fsm_state,
			self.core_ip_tx_fsm_state,
			self.core_arp_rx_fsm_state,
			self.core_arp_tx_fsm_state,
			self.core_arp_table_fsm_state,
		)

		self.submodules.la = LiteScopeLA(debug, 4096)
		self.la.trigger.add_port(LiteScopeTerm(self.la.dw))

	def do_finalize(self):
		UDPSoC.do_finalize(self)
		self.comb += [
			self.core_icmp_rx_fsm_state.eq(self.core.icmp.rx.fsm.state),
			self.core_icmp_tx_fsm_state.eq(self.core.icmp.tx.fsm.state),
			self.core_udp_rx_fsm_state.eq(self.core.udp.rx.fsm.state),
			self.core_udp_tx_fsm_state.eq(self.core.udp.tx.fsm.state),
			self.core_ip_rx_fsm_state.eq(self.core.ip.rx.fsm.state),
			self.core_ip_tx_fsm_state.eq(self.core.ip.tx.fsm.state),
			self.core_arp_rx_fsm_state.eq(self.core.arp.rx.fsm.state),
			self.core_arp_tx_fsm_state.eq(self.core.arp.tx.fsm.state),
			self.core_arp_table_fsm_state.eq(self.core.arp.table.fsm.state)
		]

	def do_exit(self, vns):
		self.la.export(vns, "test/la.csv")

default_subtarget = UDPSoC
