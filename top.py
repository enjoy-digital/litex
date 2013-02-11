from fractions import Fraction
from math import ceil

from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import wishbone, wishbone2asmi, csr, wishbone2csr, dfi

from milkymist import m1crg, lm32, norflash, uart, s6ddrphy, dfii, asmicon, \
	identifier, timer, minimac3, framebuffer, asmiprobe
from cmacros import get_macros

MHz = 1000000
clk_freq = (83 + Fraction(1, 3))*MHz
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

csr_macros = get_macros("common/csrbase.h")
def csr_offset(name):
	base = int(csr_macros[name + "_BASE"], 0)
	assert((base >= 0xe0000000) and (base <= 0xe0010000))
	return (base - 0xe0000000)//0x800

interrupt_macros = get_macros("common/interrupt.h")
def interrupt_n(name):
	return int(interrupt_macros[name + "_INTERRUPT"], 0)

version = get_macros("common/version.h")["VERSION"][1:-1]

class SoC:
	def __init__(self):
		#
		# ASMI
		#
		self.asmicon = asmicon.ASMIcon(sdram_phy, sdram_geom, sdram_timing)
		asmiport_wb = self.asmicon.hub.get_port()
		asmiport_fb = self.asmicon.hub.get_port(2)
		self.asmicon.finalize()
		
		#
		# DFI
		#
		self.ddrphy = s6ddrphy.S6DDRPHY(sdram_geom.mux_a, sdram_geom.bank_a, sdram_phy.dfi_d)
		self.dfii = dfii.DFIInjector(csr_offset("DFII"),
			sdram_geom.mux_a, sdram_geom.bank_a, sdram_phy.dfi_d, sdram_phy.nphases)
		self.dficon0 = dfi.Interconnect(self.dfii.master, self.ddrphy.dfi)
		self.dficon1 = dfi.Interconnect(self.asmicon.dfi, self.dfii.slave)

		#
		# WISHBONE
		#
		self.cpu = lm32.LM32()
		self.norflash = norflash.NorFlash(25, 12)
		self.sram = wishbone.SRAM(sram_size)
		self.minimac = minimac3.MiniMAC(csr_offset("MINIMAC"))
		self.wishbone2asmi = wishbone2asmi.WB2ASMI(l2_size//4, asmiport_wb)
		self.wishbone2csr = wishbone2csr.WB2CSR()
		
		# norflash     0x00000000 (shadow @0x80000000)
		# SRAM/debug   0x10000000 (shadow @0x90000000)
		# USB          0x20000000 (shadow @0xa0000000)
		# Ethernet     0x30000000 (shadow @0xb0000000)
		# SDRAM        0x40000000 (shadow @0xc0000000)
		# CSR bridge   0x60000000 (shadow @0xe0000000)
		self.wishbonecon = wishbone.InterconnectShared(
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
		self.uart = uart.UART(csr_offset("UART"), clk_freq, baud=115200)
		self.identifier = identifier.Identifier(csr_offset("ID"), 0x4D31, version, int(clk_freq))
		self.timer = timer.Timer(csr_offset("TIMER0"))
		self.fb = framebuffer.Framebuffer(csr_offset("FB"), asmiport_fb)
		self.asmiprobe = asmiprobe.ASMIprobe(csr_offset("ASMIPROBE"), self.asmicon.hub)
		self.csrcon = csr.Interconnect(self.wishbone2csr.csr, [
			self.uart.bank.bus,
			self.dfii.bank.bus,
			self.identifier.bank.bus,
			self.timer.bank.bus,
			self.minimac.bank.bus,
			self.fb.bank.bus,
			self.asmiprobe.bank.bus
		])
		
		#
		# Clocking
		#
		self.crg = m1crg.M1CRG(50*MHz, clk_freq)

	def get_fragment(self):
		comb = [
			#
			# Interrupts
			#
			self.cpu.interrupt[interrupt_n("UART")].eq(self.uart.events.irq),
			self.cpu.interrupt[interrupt_n("TIMER0")].eq(self.timer.events.irq),
			self.cpu.interrupt[interrupt_n("MINIMAC")].eq(self.minimac.events.irq),
			#
			# DDR PHY strobes
			#
			self.ddrphy.clk4x_wr_strb.eq(self.crg.clk4x_wr_strb),
			self.ddrphy.clk4x_rd_strb.eq(self.crg.clk4x_rd_strb)
		]
		glue = Fragment(comb)
		return glue + autofragment.from_attributes(self)
