from migen.fhdl.std import *
from migen.bank import csrgen
from migen.bus import wishbone, csr
from migen.bus import wishbone2csr
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.bank.description import *

from miscope.uart2wishbone import UART2Wishbone

from misoclib import identifier
from lib.sata.common import *
from lib.sata.phy import SATAPHY
from lib.sata.link.cont import SATACONTInserter, SATACONTRemover

from migen.genlib.cdc import *

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

				# 100MHz
				p_CLKOUT0_DIVIDE=5, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=pll_sys,

				p_CLKOUT1_DIVIDE=2, p_CLKOUT1_PHASE=0.0, #o_CLKOUT1=,

				p_CLKOUT2_DIVIDE=2, p_CLKOUT2_PHASE=0.0, #o_CLKOUT2=,

				p_CLKOUT3_DIVIDE=2, p_CLKOUT3_PHASE=0.0, #o_CLKOUT3=,

				p_CLKOUT4_DIVIDE=2, p_CLKOUT4_PHASE=0.0, #o_CLKOUT4=
			),
			Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
			AsyncResetSynchronizer(self.cd_sys, ~pll_locked | platform.request("cpu_reset")),
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

class SimDesign(UART2WB):
	default_platform = "kc705"

	def __init__(self, platform, export_mila=False):
		clk_freq = 200*1000000
		UART2WB.__init__(self, platform, clk_freq)
		self.submodules.crg = _CRG(platform)

		self.submodules.sata_phy_host = SATAPHY(platform.request("sata_host"), clk_freq, host=True)
		self.comb += [
			self.sata_phy_host.sink.stb.eq(1),
			self.sata_phy_host.sink.data.eq(primitives["SYNC"]),
			self.sata_phy_host.sink.charisk.eq(0b0001)
		]
		self.submodules.sata_phy_device = SATAPHY(platform.request("sata_device"), clk_freq, host=False)
		self.comb += [
			self.sata_phy_device.sink.stb.eq(1),
			self.sata_phy_device.sink.data.eq(primitives["SYNC"]),
			self.sata_phy_device.sink.charisk.eq(0b0001)
		]


class ClockLeds(Module):
	def __init__(self, platform):
		led_sata_rx = platform.request("user_led", 0)
		led_sata_tx = platform.request("user_led", 1)

		sata_rx_cnt = Signal(32)
		sata_tx_cnt = Signal(32)

		self.sync.sata_rx += \
			If(sata_rx_cnt == 0,
				led_sata_rx.eq(~led_sata_rx),
				sata_rx_cnt.eq(150*1000*1000//2)
			).Else(
				sata_rx_cnt.eq(sata_rx_cnt-1)
			)

		self.sync.sata_tx += \
			If(sata_tx_cnt == 0,
				led_sata_tx.eq(~led_sata_tx),
				sata_tx_cnt.eq(150*1000*1000//2)
			).Else(
				sata_tx_cnt.eq(sata_tx_cnt-1)
			)

class VeryBasicPHYStim(Module, AutoCSR):
	def __init__(self, phy):
		self._enable = CSRStorage()
		self._tx_primitive = CSRStorage(32)
		self._rx_primitive = CSRStatus(32)

		self.submodules.cont_inserter = SATACONTInserter(phy_description(32))
		self.submodules.cont_remover = SATACONTRemover(phy_description(32))
		self.comb += [
			self.cont_inserter.source.connect(phy.sink),
			phy.source.connect(self.cont_remover.sink)
		]
		self.sync += [
			self.cont_inserter.sink.stb.eq(1),
			self.cont_inserter.sink.charisk.eq(0b0001),
			If(self._enable.storage,
				self.cont_inserter.sink.data.eq(self._tx_primitive.storage),
				If(self.cont_remover.source.stb & (self.cont_remover.source.charisk == 0b0001),
					self._rx_primitive.status.eq(self.cont_remover.source.data)
				)
			).Else(
				self.cont_inserter.sink.data.eq(primitives["SYNC"]),
			)
		]

class TestDesign(UART2WB, AutoCSR):
	default_platform = "kc705"
	csr_map = {
		"mila":				10,
		"stim":             11
	}
	csr_map.update(UART2WB.csr_map)

	def __init__(self, platform, mila=True, export_mila=False):
		clk_freq = 200*1000000
		UART2WB.__init__(self, platform, clk_freq)
		self.submodules.crg = _CRG(platform)

		self.submodules.sata_phy = SATAPHY(platform.request("sata_host"), clk_freq, host=True, speed="SATA1")
		self.submodules.stim = VeryBasicPHYStim(self.sata_phy)

		self.submodules.clock_leds = ClockLeds(platform)

		if mila:
			import os
			from miscope import MiLa, Term, UART2Wishbone

			trx = self.sata_phy.trx
			ctrl = self.sata_phy.ctrl
			crg = self.sata_phy.crg

			debug = (
				trx.rxresetdone,
				trx.txresetdone,

				trx.rxuserrdy,
				trx.txuserrdy,

				trx.rxelecidle,
				trx.rxcominitdet,
				trx.rxcomwakedet,

				trx.txcomfinish,
				trx.txcominit,
				trx.txcomwake,

				ctrl.ready,
				ctrl.sink.data,
				ctrl.sink.charisk,

				self.sata_phy.source.stb,
				self.sata_phy.source.data,
				self.sata_phy.source.charisk,

				self.sata_phy.sink.stb,
				self.sata_phy.sink.data,
				self.sata_phy.sink.charisk,
			)

			self.comb += platform.request("user_led", 2).eq(crg.ready)
			self.comb += platform.request("user_led", 3).eq(ctrl.ready)

			self.submodules.mila = MiLa(depth=512, dat=Cat(*debug))
			self.mila.add_port(Term)

			if export_mila:
				mila_filename = os.path.join(platform.soc_ext_path, "test", "mila.csv")
				self.mila.export(self, debug, mila_filename)

#default_subtarget = SimDesign
default_subtarget = TestDesign