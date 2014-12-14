from migen.fhdl.std import *
from migen.bank import csrgen
from migen.bus import wishbone, csr
from migen.bus import wishbone2csr
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.bank.description import *

from miscope.uart2wishbone import UART2Wishbone

from misoclib import identifier
from lib.sata.common import *
from lib.sata.phy.k7sataphy import K7SATAPHY

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

				# 166.66MHz
				p_CLKOUT0_DIVIDE=6, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=pll_sys,

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

class SimDesign(UART2WB):
	default_platform = "kc705"

	def __init__(self, platform, export_mila=False):
		clk_freq = 166666*1000
		UART2WB.__init__(self, platform, clk_freq)
		self.submodules.crg = _CRG(platform)

		self.submodules.sataphy_host = K7SATAPHY(platform.request("sata_host"), clk_freq, host=True)
		self.comb += [
			self.sataphy_host.sink.stb.eq(1),
			self.sataphy_host.sink.data.eq(primitives["SYNC"]),
			self.sataphy_host.sink.charisk.eq(0b0001)
		]
		self.submodules.sataphy_device = K7SATAPHY(platform.request("sata_device"), clk_freq, host=False)
		self.comb += [
			self.sataphy_device.sink.stb.eq(1),
			self.sataphy_device.sink.data.eq(primitives["SYNC"]),
			self.sataphy_device.sink.charisk.eq(0b0001)
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

class TestDesign(UART2WB, AutoCSR):
	default_platform = "kc705"
	csr_map = {
		"mila":				10,
	}
	csr_map.update(UART2WB.csr_map)

	def __init__(self, platform, mila=True, export_mila=False):
		clk_freq = 166666*1000
		UART2WB.__init__(self, platform, clk_freq)
		self.submodules.crg = _CRG(platform)

		self.submodules.sataphy_host = K7SATAPHY(platform.request("sata_host"), clk_freq, host=True, default_speed="SATA2")
		self.comb += [
			self.sataphy_host.sink.stb.eq(1),
			self.sataphy_host.sink.data.eq(primitives["SYNC"]),
			self.sataphy_host.sink.charisk.eq(0b0001)
		]

		self.submodules.clock_leds = ClockLeds(platform)

		if mila:
			import os
			from miscope import MiLa, Term, UART2Wishbone

			gtx = self.sataphy_host.gtx
			ctrl = self.sataphy_host.ctrl
			crg = self.sataphy_host.crg

			debug = (
				gtx.rxresetdone,
				gtx.txresetdone,

				gtx.rxuserrdy,
				gtx.txuserrdy,

				gtx.rxelecidle,
				gtx.rxcominitdet,
				gtx.rxcomwakedet,

				gtx.txcomfinish,
				gtx.txcominit,
				gtx.txcomwake,

				ctrl.sink.stb,
				ctrl.sink.data,
				ctrl.sink.charisk,
				ctrl.align_detect,

				self.sataphy_host.source.stb,
				self.sataphy_host.source.data,
				self.sataphy_host.source.charisk,
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