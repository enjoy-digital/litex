from fractions import Fraction
from math import ceil
from operator import itemgetter

from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bus import wishbone, wishbone2asmi, csr, wishbone2csr, dfi
from migen.bank import csrgen

from milkymist import m1crg, lm32, norflash, uart, s6ddrphy, dfii, asmicon, \
	identifier, timer, minimac3, framebuffer, asmiprobe, dvisampler
from cif import get_macros

version = get_macros("common/version.h")["VERSION"][1:-1]

clk_freq = (83 + Fraction(1, 3))*1000000
sram_size = 4096 # in bytes
l2_size = 8192 # in bytes

clk_period_ns = 1000000000/clk_freq
def ns(t, margin=True):
	if margin:
		t += clk_period_ns/2
	return ceil(t/clk_period_ns)

sdram_phy = asmicon.PhySettings(
	dfi_d=64, 
	nphases=2,
	rdphase=0,
	wrphase=1
)
sdram_geom = asmicon.GeomSettings(
	bank_a=2,
	row_a=13,
	col_a=10
)
sdram_timing = asmicon.TimingSettings(
	tRP=ns(15),
	tRCD=ns(15),
	tWR=ns(15),
	tREFI=ns(7800, False),
	tRFC=ns(70),
	
	CL=3,
	rd_delay=4,

	read_time=32,
	write_time=16
)

class M1ClockPads:
	def __init__(self, platform):
		self.clk50 = platform.request("clk50")
		self.trigger_reset = platform.request("user_btn", 1)
		self.norflash_rst_n = platform.request("norflash_rst_n")
		self.vga_clk = platform.request("vga_clock")
		ddram_clock = platform.request("ddram_clock")
		self.ddr_clk_p = ddram_clock.p
		self.ddr_clk_n = ddram_clock.n
		eth_clocks = platform.request("eth_clocks")
		self.eth_phy_clk = eth_clocks.phy
		self.eth_rx_clk = eth_clocks.rx
		self.eth_tx_clk = eth_clocks.tx

class SoC(Module):
	csr_base = 0xe0000000
	csr_map = {
		"uart":					0,
		"dfii":					1,
		"identifier":			2,
		"timer0":				3,
		"minimac":				4,
		"fb":					5,
		"asmiprobe":			6,
		"dvisampler0":			7,
		"dvisampler0_edid_mem":	8,
		"dvisampler1":			9,
		"dvisampler1_edid_mem":	10,
	}

	interrupt_map = {
		"uart":			0,
		"timer0":		1,
		"minimac":		2,
	}

	def __init__(self, platform):
		#
		# ASMI
		#
		self.submodules.asmicon = asmicon.ASMIcon(sdram_phy, sdram_geom, sdram_timing)
		asmiport_wb = self.asmicon.hub.get_port()
		asmiport_fb = self.asmicon.hub.get_port(2)
		self.asmicon.finalize()
		
		#
		# DFI
		#
		self.submodules.ddrphy = s6ddrphy.S6DDRPHY(platform.request("ddram"))
		self.submodules.dfii = dfii.DFIInjector(sdram_geom.mux_a, sdram_geom.bank_a, sdram_phy.dfi_d,
			sdram_phy.nphases)
		self.submodules.dficon0 = dfi.Interconnect(self.dfii.master, self.ddrphy.dfi)
		self.submodules.dficon1 = dfi.Interconnect(self.asmicon.dfi, self.dfii.slave)

		#
		# WISHBONE
		#
		self.submodules.cpu = lm32.LM32()
		self.submodules.norflash = norflash.NorFlash(platform.request("norflash"), 12)
		self.submodules.sram = wishbone.SRAM(sram_size)
		self.submodules.minimac = minimac3.MiniMAC(platform.request("eth"))
		self.submodules.wishbone2asmi = wishbone2asmi.WB2ASMI(l2_size//4, asmiport_wb)
		self.submodules.wishbone2csr = wishbone2csr.WB2CSR()
		
		# norflash     0x00000000 (shadow @0x80000000)
		# SRAM/debug   0x10000000 (shadow @0x90000000)
		# USB          0x20000000 (shadow @0xa0000000)
		# Ethernet     0x30000000 (shadow @0xb0000000)
		# SDRAM        0x40000000 (shadow @0xc0000000)
		# CSR bridge   0x60000000 (shadow @0xe0000000)
		self.submodules.wishbonecon = wishbone.InterconnectShared(
			[
				self.cpu.ibus,
				self.cpu.dbus
			], [
				(lambda a: a[26:29] == 0, self.norflash.bus),
				(lambda a: a[26:29] == 1, self.sram.bus),
				(lambda a: a[26:29] == 3, self.minimac.membus),
				(lambda a: a[27:29] == 2, self.wishbone2asmi.wishbone),
				(lambda a: a[27:29] == 3, self.wishbone2csr.wishbone)
			],
			register=True)
		
		#
		# CSR
		#
		self.submodules.uart = uart.UART(platform.request("serial"), clk_freq, baud=115200)
		self.submodules.identifier = identifier.Identifier(0x4D31, version, int(clk_freq))
		self.submodules.timer0 = timer.Timer()
		self.submodules.fb = framebuffer.Framebuffer(platform.request("vga"), asmiport_fb)
		self.submodules.asmiprobe = asmiprobe.ASMIprobe(self.asmicon.hub)
		self.submodules.dvisampler0 = dvisampler.DVISampler(platform.request("dvi_in", 0))
		self.submodules.dvisampler1 = dvisampler.DVISampler(platform.request("dvi_in", 1))

		self.submodules.csrbankarray = csrgen.BankArray(self,
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override])
		self.submodules.csrcon = csr.Interconnect(self.wishbone2csr.csr, self.csrbankarray.get_buses())

		#
		# Interrupts
		#
		for k, v in sorted(self.interrupt_map.items(), key=itemgetter(1)):
			self.comb += self.cpu.interrupt[v].eq(getattr(self, k).ev.irq)
		
		#
		# Clocking
		#
		self.submodules.crg = m1crg.M1CRG(M1ClockPads(platform), clk_freq)
		self.comb += [
			self.ddrphy.clk4x_wr_strb.eq(self.crg.clk4x_wr_strb),
			self.ddrphy.clk4x_rd_strb.eq(self.crg.clk4x_rd_strb)
		]
