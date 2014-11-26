import os
from fractions import Fraction

from migen.fhdl.std import *
from mibuild.generic_platform import ConstraintError

from misoclib import sdram, mxcrg, norflash16, minimac3, framebuffer, gpio
from misoclib.sdram.phy import s6ddrphy
from misoclib.gensoc import SDRAMSoC
from misoclib.ethmac.phy import mii

class _MXClockPads:
	def __init__(self, platform):
		self.clk50 = platform.request("clk50")
		self.trigger_reset = 0
		try:
			self.trigger_reset = platform.request("user_btn", 1)
		except ConstraintError:
			pass
		self.norflash_rst_n = platform.request("norflash_rst_n")
		ddram_clock = platform.request("ddram_clock")
		self.ddr_clk_p = ddram_clock.p
		self.ddr_clk_n = ddram_clock.n

class BaseSoC(SDRAMSoC):
	default_platform = "mixxeo" # also supports m1

	def __init__(self, platform, **kwargs):
		SDRAMSoC.__init__(self, platform,
			clk_freq=(83 + Fraction(1, 3))*1000000,
			cpu_reset_address=0x00180000,
			**kwargs)

		sdram_geom = sdram.GeomSettings(
			bank_a=2,
			row_a=13,
			col_a=10
		)
		sdram_timing = sdram.TimingSettings(
			tRP=self.ns(15),
			tRCD=self.ns(15),
			tWR=self.ns(15),
			tWTR=2,
			tREFI=self.ns(7800, False),
			tRFC=self.ns(70),

			req_queue_size=8,
			read_time=32,
			write_time=16
		)
		self.submodules.ddrphy = s6ddrphy.S6DDRPHY(platform.request("ddram"), memtype="DDR",
			rd_bitslip=0, wr_bitslip=3, dqs_ddr_alignment="C1")
		self.register_sdram_phy(self.ddrphy.dfi, self.ddrphy.phy_settings, sdram_geom, sdram_timing)

		self.submodules.norflash = norflash16.NorFlash16(platform.request("norflash"),
			self.ns(110), self.ns(50))
		self.flash_boot_address = 0x001a0000
		self.register_rom(self.norflash.bus)

		self.submodules.crg = mxcrg.MXCRG(_MXClockPads(platform), self.clk_freq)
		self.comb += [
			self.ddrphy.clk4x_wr_strb.eq(self.crg.clk4x_wr_strb),
			self.ddrphy.clk4x_rd_strb.eq(self.crg.clk4x_rd_strb)
		]
		platform.add_platform_command("""
INST "mxcrg/wr_bufpll" LOC = "BUFPLL_X0Y2";
INST "mxcrg/rd_bufpll" LOC = "BUFPLL_X0Y3";

PIN "mxcrg/bufg_x1.O" CLOCK_DEDICATED_ROUTE = FALSE;
""")
		platform.add_source_dir(os.path.join("verilog", "mxcrg"))

class MiniSoC(BaseSoC):
	csr_map = {
		"ethphy":		10,
		"ethmac":		11,
	}
	csr_map.update(BaseSoC.csr_map)

	interrupt_map = {
		"ethmac":		2,
	}
	interrupt_map.update(BaseSoC.interrupt_map)

	def __init__(self, platform, **kwargs):
		BaseSoC.__init__(self, platform, **kwargs)

		if platform.name == "mixxeo":
			self.submodules.leds = gpio.GPIOOut(platform.request("user_led"))
		if platform.name == "m1":
			self.submodules.buttons = gpio.GPIOIn(Cat(platform.request("user_btn", 0), platform.request("user_btn", 2)))
			self.submodules.leds = gpio.GPIOOut(Cat(platform.request("user_led", i) for i in range(2)))

		self.submodules.ethphy = mii.MIIPHY(platform.request("eth_clocks"), platform.request("eth"))
		self.submodules.ethmac = ethmac.EthMAC(phy=self.ethphy, with_hw_preamble_crc=False)
		self.add_wb_slave(lambda a: a[26:29] == 3, self.ethmac.bus)
		self.add_cpu_memory_region("ethmac_mem", 0xb0000000, 0x2000)

def get_vga_dvi(platform):
	try:
		pads_vga = platform.request("vga_out")
	except ConstraintError:
		pads_vga = None
	try:
		pads_dvi = platform.request("dvi_out")
	except ConstraintError:
		pads_dvi = None
	else:
		platform.add_platform_command("""
PIN "dviout_pix_bufg.O" CLOCK_DEDICATED_ROUTE = FALSE;
""")
	return pads_vga, pads_dvi

def add_vga_tig(platform, fb):
	platform.add_platform_command("""
NET "{vga_clk}" TNM_NET = "GRPvga_clk";
NET "sys_clk" TNM_NET = "GRPsys_clk";
TIMESPEC "TSise_sucks1" = FROM "GRPvga_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSise_sucks2" = FROM "GRPsys_clk" TO "GRPvga_clk" TIG;
""", vga_clk=fb.driver.clocking.cd_pix.clk)

class FramebufferSoC(MiniSoC):
	csr_map = {
		"fb":					11,
	}
	csr_map.update(MiniSoC.csr_map)

	def __init__(self, platform, **kwargs):
		MiniSoC.__init__(self, platform, **kwargs)
		pads_vga, pads_dvi = get_vga_dvi(platform)
		self.submodules.fb = framebuffer.Framebuffer(pads_vga, pads_dvi, self.lasmixbar.get_master())
		add_vga_tig(platform, self.fb)

default_subtarget = FramebufferSoC
