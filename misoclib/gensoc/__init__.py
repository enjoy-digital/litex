import os
from operator import itemgetter
from collections import defaultdict
from math import ceil

from migen.fhdl.std import *
from migen.bank import csrgen
from migen.bus import wishbone, csr, lasmibus, dfi
from migen.bus import wishbone2lasmi, wishbone2csr

from misoclib import lm32, mor1kx, uart, dfii, lasmicon, identifier, timer, memtest
from misoclib.lasmicon.minicon import Minicon

class GenSoC(Module):
	csr_base = 0xe0000000
	csr_map = {
		"crg":					0, # user
		"uart":					1, # provided by default
		"identifier":			2, # provided
		"timer0":				3, # provided
		"buttons":				4, # user
		"leds":					5, # user
	}
	interrupt_map = {
		"uart":			0,
		"timer0":		1,
	}
	known_platform_id = defaultdict(lambda: 0x554E, {
		"mixxeo":		0x4D58,
		"m1":			0x4D31,
		"papilio_pro":	0x5050,
		"kc705":		0x4B37
	})

	def __init__(self, platform, clk_freq, cpu_reset_address, sram_size=4096, l2_size=0, with_uart=True, cpu_type="lm32"):
		self.clk_freq = clk_freq
		self.cpu_reset_address = cpu_reset_address
		self.sram_size = sram_size
		self.l2_size = l2_size
		self.cpu_type = cpu_type
		self.cpu_memory_regions = []
		self._rom_registered = False

		# Wishbone
		if cpu_type == "lm32":
			self.submodules.cpu = lm32.LM32(cpu_reset_address)
		elif cpu_type == "or1k":
			self.submodules.cpu = mor1kx.MOR1KX(cpu_reset_address)
		else:
			raise ValueError("Unsupported CPU type: "+cpu_type)
		self.submodules.sram = wishbone.SRAM(sram_size)
		self.submodules.wishbone2csr = wishbone2csr.WB2CSR()

		# rom          0x00000000 (shadow @0x80000000) from register_rom
		# SRAM/debug   0x10000000 (shadow @0x90000000) provided
		# CSR bridge   0x60000000 (shadow @0xe0000000) provided
		self._wb_masters = [self.cpu.ibus, self.cpu.dbus]
		self._wb_slaves = [
			(lambda a: a[26:29] == 1, self.sram.bus),
			(lambda a: a[27:29] == 3, self.wishbone2csr.wishbone)
		]
		self.add_cpu_memory_region("sram", 0x10000000, sram_size)

		# CSR
		if with_uart:
			self.submodules.uart = uart.UART(platform.request("serial"), clk_freq, baud=115200)
		self.submodules.identifier = identifier.Identifier(self.known_platform_id[platform.name], int(clk_freq),
			log2_int(l2_size) if l2_size else 0)
		self.submodules.timer0 = timer.Timer()

		# add CPU Verilog sources
		if cpu_type == "lm32":
			platform.add_sources(os.path.join("verilog", "lm32", "submodule", "rtl"),
				"lm32_cpu.v", "lm32_instruction_unit.v", "lm32_decoder.v",
				"lm32_load_store_unit.v", "lm32_adder.v", "lm32_addsub.v", "lm32_logic_op.v",
				"lm32_shifter.v", "lm32_multiplier.v", "lm32_mc_arithmetic.v",
				"lm32_interrupt.v", "lm32_ram.v", "lm32_dp_ram.v", "lm32_icache.v",
				"lm32_dcache.v", "lm32_debug.v", "lm32_itlb.v", "lm32_dtlb.v")
			platform.add_verilog_include_path(os.path.join("verilog", "lm32"))
		if cpu_type == "or1k":
			platform.add_source_dir(os.path.join("verilog", "mor1kx", "submodule", "rtl", "verilog"))

	def register_rom(self, rom_wb_if, bios_size=0xa000):
		if self._rom_registered:
			raise FinalizeError
		self._rom_registered = True

		self.add_wb_slave(lambda a: a[26:29] == 0, rom_wb_if)
		self.add_cpu_memory_region("rom", self.cpu_reset_address, bios_size)

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

	def do_finalize(self):
		if not self._rom_registered:
			raise FinalizeError("Need to call GenSoC.register_rom()")

		# Wishbone
		self.submodules.wishbonecon = wishbone.InterconnectShared(self._wb_masters,
			self._wb_slaves, register=True)

		# CSR
		self.submodules.csrbankarray = csrgen.BankArray(self,
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override])
		self.submodules.csrcon = csr.Interconnect(self.wishbone2csr.csr, self.csrbankarray.get_buses())

		# Interrupts
		for k, v in sorted(self.interrupt_map.items(), key=itemgetter(1)):
			if hasattr(self, k):
				self.comb += self.cpu.interrupt[v].eq(getattr(self, k).ev.irq)

	def ns(self, t, margin=True):
		clk_period_ns = 1000000000/self.clk_freq
		if margin:
			t += clk_period_ns/2
		return ceil(t/clk_period_ns)

class IntegratedBIOS:
	def __init__(self, bios_size=0x8000):
		self.submodules.rom = wishbone.SRAM(bios_size, read_only=True)
		self.register_rom(self.rom.bus, bios_size)

	def init_bios_memory(self, data):
		self.rom.mem.init = data

class SDRAMSoC(GenSoC):
	csr_map = {
		"dfii":					6,
		"lasmicon":				7,
		"memtest_w":				8,
		"memtest_r":				9
	}
	csr_map.update(GenSoC.csr_map)

	def __init__(self, platform, clk_freq, cpu_reset_address, with_memtest=False, sram_size=4096, l2_size=8192, with_uart=True, ramcon_type="lasmicon", **kwargs):
		GenSoC.__init__(self, platform, clk_freq, cpu_reset_address, sram_size, l2_size, with_uart, **kwargs)
		self.with_memtest = with_memtest
		self.ramcon_type = ramcon_type
		self._sdram_phy_registered = False

	def register_sdram_phy(self, phy_dfi, phy_settings, sdram_geom, sdram_timing):
		if self._sdram_phy_registered:
			raise FinalizeError
		self._sdram_phy_registered = True

		# DFI
		self.submodules.dfii = dfii.DFIInjector(sdram_geom.mux_a, sdram_geom.bank_a,
			phy_settings.dfi_d, phy_settings.nphases)
		self.submodules.dficon0 = dfi.Interconnect(self.dfii.master, phy_dfi)

		if self.ramcon_type == "lasmicon":
			# LASMI
			self.submodules.lasmicon = lasmicon.LASMIcon(phy_settings, sdram_geom, sdram_timing)
			self.submodules.dficon1 = dfi.Interconnect(self.lasmicon.dfi, self.dfii.slave)

			self.submodules.lasmixbar = lasmibus.Crossbar([self.lasmicon.lasmic], self.lasmicon.nrowbits)

			if self.with_memtest:
				self.submodules.memtest_w = memtest.MemtestWriter(self.lasmixbar.get_master())
				self.submodules.memtest_r = memtest.MemtestReader(self.lasmixbar.get_master())

			# Wishbone bridge: map SDRAM at 0x40000000 (shadow @0xc0000000)
			self.submodules.wishbone2lasmi = wishbone2lasmi.WB2LASMI(self.l2_size//4, self.lasmixbar.get_master())
			self.add_wb_slave(lambda a: a[27:29] == 2, self.wishbone2lasmi.wishbone)
			self.add_cpu_memory_region("sdram", 0x40000000,
				2**self.lasmicon.lasmic.aw*self.lasmicon.lasmic.dw*self.lasmicon.lasmic.nbanks//8)
		elif self.ramcon_type == "minicon":
			rdphase = phy_settings.rdphase
			self.submodules.minicon = sdramcon = Minicon(phy_settings, sdram_geom, sdram_timing)
			self.submodules.dficon1 = dfi.Interconnect(sdramcon.dfi, self.dfii.slave)
			sdram_width = flen(sdramcon.bus.dat_r)

			if (sdram_width == 32):
				self.add_wb_slave(lambda a: a[27:29] == 2, sdramcon.bus)
			elif (sdram_width < 32):
				self.submodules.dc = dc = wishbone.DownConverter(32, sdram_width)
				self.submodules.intercon = wishbone.InterconnectPointToPoint(dc.wishbone_o, sdramcon.bus)
				self.add_wb_slave(lambda a: a[27:29] == 2, dc.wishbone_i)
			else:
				raise NotImplementedError("Unsupported SDRAM width of {} > 32".format(sdram_width))

			# map SDRAM at 0x40000000 (shadow @0xc0000000)
			self.add_cpu_memory_region("sdram", 0x40000000,
				2**(sdram_geom.bank_a+sdram_geom.row_a+sdram_geom.col_a)*sdram_width//8)
		else:
			raise ValueError("Unsupported SDRAM controller type: {}".format(self.ramcon_type))

	def do_finalize(self):
		if not self._sdram_phy_registered:
			raise FinalizeError("Need to call SDRAMSoC.register_sdram_phy()")
		GenSoC.do_finalize(self)
