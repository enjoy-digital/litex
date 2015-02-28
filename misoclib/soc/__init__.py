import os, struct
from operator import itemgetter
from math import ceil

from migen.fhdl.std import *
from migen.bank import csrgen
from migen.bus import wishbone, csr, wishbone2csr

from misoclib.com import uart
from misoclib.cpu import CPU, lm32, mor1kx
from misoclib.cpu.peripherals import identifier, timer
from misoclib.mem.sdram.bus import dfi, lasmibus, wishbone2lasmi
from misoclib.mem.sdram import minicon,lasmicon
from misoclib.mem.sdram import dfii
from misoclib.mem.sdram import memtest

def mem_decoder(address, start=26, end=29):
	return lambda a: a[start:end] == ((address >> (start+2)) & (2**(end-start))-1)

class SoC(Module):
	csr_map = {
		"crg":					0, # user
		"uart":					1, # provided by default (optional)
		"identifier":			2, # provided by default (optional)
		"timer0":				3, # provided by default (optional)
		"buttons":				4, # user
		"leds":					5, # user
	}
	interrupt_map = {
		"uart":			0,
		"timer0":		1,
	}
	mem_map = {
		"rom":		0x00000000, # (shadow @0x80000000)
		"sram":		0x10000000, # (shadow @0x90000000)
		"sdram":	0x40000000, # (shadow @0xc0000000)
		"csr":		0x60000000, # (shadow @0xe0000000)
	}
	def __init__(self, platform, clk_freq, cpu_or_bridge=None,
				with_cpu=True, cpu_type="lm32", cpu_reset_address=0x00000000,
							   cpu_boot_file="software/bios/bios.bin",
				with_rom=False, rom_size=0x8000,
				with_sram=True, sram_size=4096,
				with_sdram=False, sdram_size=64*1024,
				with_csr=True, csr_data_width=8, csr_address_width=14,
				with_uart=True, uart_baudrate=115200,
				with_identifier=True,
				with_timer=True):
		self.platform = platform
		self.clk_freq = clk_freq
		self.cpu_or_bridge = cpu_or_bridge

		self.with_cpu = with_cpu
		self.cpu_type = cpu_type
		self.cpu_reset_address = cpu_reset_address
		self.cpu_boot_file = cpu_boot_file

		self.with_rom = with_rom
		self.rom_size = rom_size

		self.with_sram = with_sram
		self.sram_size = sram_size

		self.with_sdram = with_sdram
		self.sdram_size = sdram_size

		self.with_uart = with_uart
		self.uart_baudrate = uart_baudrate

		self.with_identifier = with_identifier

		self.with_csr = with_csr
		self.csr_data_width = csr_data_width
		self.csr_address_width = csr_address_width

		self.memory_regions = []
		self.csr_regions = [] # list of (name, origin, busword, csr_list/Memory)

		self._wb_masters = []
		self._wb_slaves = []

		if with_cpu:
			if cpu_type == "lm32":
				self.submodules.cpu = lm32.LM32(platform, cpu_reset_address)
			elif cpu_type == "or1k":
				self.submodules.cpu = mor1kx.MOR1KX(platform, cpu_reset_address)
			else:
				raise ValueError("Unsupported CPU type: "+cpu_type)
			self.cpu_or_bridge = self.cpu
			self._wb_masters += [self.cpu.ibus, self.cpu.dbus]

			if with_rom:
				self.submodules.rom = wishbone.SRAM(rom_size, read_only=True)
				self.register_mem("rom", self.mem_map["rom"], self.rom.bus, rom_size)

			if with_sram:
				self.submodules.sram = wishbone.SRAM(sram_size)
				self.register_mem("sram", self.mem_map["sram"], self.sram.bus, sram_size)

			if with_sdram:
				self.submodules.sdram = wishbone.SRAM(sdram_size)
				self.register_mem("sdram", self.mem_map["sdram"], self.sdram.bus, sdram_size)

		if with_csr:
			self.submodules.wishbone2csr = wishbone2csr.WB2CSR(bus_csr=csr.Interface(csr_data_width, csr_address_width))
			self.register_mem("csr", self.mem_map["csr"], self.wishbone2csr.wishbone)

			if with_uart:
				self.submodules.uart = uart.UART(platform.request("serial"), clk_freq, baud=uart_baudrate)

			if with_identifier:
				platform_id = 0x554E if not hasattr(platform, "identifier") else platform.identifier
				self.submodules.identifier = identifier.Identifier(platform_id, int(clk_freq))

			if with_timer:
				self.submodules.timer0 = timer.Timer()

	def init_rom(self, data):
		self.rom.mem.init = data

	def add_wb_master(self, wbm):
		if self.finalized:
			raise FinalizeError
		self._wb_masters.append(wbm)

	def add_wb_slave(self, address_decoder, interface):
		if self.finalized:
			raise FinalizeError
		self._wb_slaves.append((address_decoder, interface))

	def check_memory_region(self, name, origin):
		for n, o, l in self.memory_regions:
			if n == name or o == origin:
				raise ValueError("Memory region conflict between {} and {}".format(n, name))

	def add_memory_region(self, name, origin, length):
		self.check_memory_region(name, origin)
		self.memory_regions.append((name, origin, length))

	def register_mem(self, name, address, interface, size=None):
		self.add_wb_slave(mem_decoder(address), interface)
		if size is not None:
			self.add_memory_region(name, address, size)

	# XXX for retro-compatibilty, we should maybe use directly register_mem in targets
	def register_rom(self, interface):
		self.register_mem("rom", self.mem_map["rom"], interface, size=self.rom_size)

	def check_csr_region(self, name, origin):
		for n, o, l, obj in self.csr_regions:
			if n == name or o == origin:
				raise ValueError("CSR region conflict between {} and {}".format(n, name))

	def add_csr_region(self, name, origin, busword, obj):
		self.check_csr_region(name, origin)
		self.csr_regions.append((name, origin, busword, obj))

	def do_finalize(self):
		registered_mems = [regions[0] for regions in self.memory_regions]
		if isinstance(self.cpu_or_bridge, CPU):
			for mem in ["rom", "sram"]:
				if mem not in registered_mems:
					raise FinalizeError("CPU needs a {} to be registered with SoC.register_mem()".format(mem))

		# Wishbone
		self.submodules.wishbonecon = wishbone.InterconnectShared(self._wb_masters,
			self._wb_slaves, register=True)

		# CSR
		if self.with_csr:
			self.submodules.csrbankarray = csrgen.BankArray(self,
				lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override],
				data_width=self.csr_data_width, address_width=self.csr_address_width)
			self.submodules.csrcon = csr.Interconnect(self.wishbone2csr.csr, self.csrbankarray.get_buses())
			for name, csrs, mapaddr, rmap in self.csrbankarray.banks:
				self.add_csr_region(name, self.mem_map["csr"]+0x80000000+0x800*mapaddr, flen(rmap.bus.dat_w), csrs)
			for name, memory, mapaddr, mmap in self.csrbankarray.srams:
				self.add_csr_region(name, self.mem_map["csr"]+0x80000000+0x800*mapaddr, flen(rmap.bus.dat_w), memory)

		# Interrupts
		if hasattr(self.cpu_or_bridge, "interrupt"):
			for k, v in sorted(self.interrupt_map.items(), key=itemgetter(1)):
				if hasattr(self, k):
					self.comb += self.cpu_or_bridge.interrupt[v].eq(getattr(self, k).ev.irq)

	def ns(self, t, margin=True):
		clk_period_ns = 1000000000/self.clk_freq
		if margin:
			t += clk_period_ns/2
		return ceil(t/clk_period_ns)

	def do_exit(self, vns):
		pass

class SDRAMSoC(SoC):
	csr_map = {
		"dfii":					6,
		"lasmicon":				7,
		"wishbone2lasmi":		8,
		"memtest_w":			9,
		"memtest_r":			10
	}
	csr_map.update(SoC.csr_map)

	def __init__(self, platform, clk_freq,
			ramcon_type="lasmicon",
			with_l2=True, l2_size=8192,
			with_memtest=False,
			**kwargs):
		SoC.__init__(self, platform, clk_freq, **kwargs)
		self.ramcon_type = ramcon_type

		self.with_l2 = with_l2
		self.l2_size = l2_size

		self.with_memtest = with_memtest

		self._sdram_phy_registered = False

	def register_sdram_phy(self, phy_dfi, phy_settings, sdram_geom, sdram_timing):
		if self._sdram_phy_registered:
			raise FinalizeError
		self._sdram_phy_registered = True

		# DFI
		self.submodules.dfii = dfii.DFIInjector(sdram_geom.mux_a, sdram_geom.bank_a,
			phy_settings.dfi_d, phy_settings.nphases)
		self.submodules.dficon0 = dfi.Interconnect(self.dfii.master, phy_dfi)

		# LASMICON
		if self.ramcon_type == "lasmicon":
			self.submodules.lasmicon = lasmicon.LASMIcon(phy_settings, sdram_geom, sdram_timing)
			self.submodules.dficon1 = dfi.Interconnect(self.lasmicon.dfi, self.dfii.slave)

			self.submodules.lasmixbar = lasmibus.Crossbar([self.lasmicon.lasmic], self.lasmicon.nrowbits)

			if self.with_memtest:
				self.submodules.memtest_w = memtest.MemtestWriter(self.lasmixbar.get_master())
				self.submodules.memtest_r = memtest.MemtestReader(self.lasmixbar.get_master())

			if self.with_l2:
				self.submodules.wishbone2lasmi = wishbone2lasmi.WB2LASMI(self.l2_size//4, self.lasmixbar.get_master())
				sdram_size = 2**self.lasmicon.lasmic.aw*self.lasmicon.lasmic.dw*self.lasmicon.lasmic.nbanks//8
				self.register_mem("sdram", self.mem_map["sdram"], self.wishbone2lasmi.wishbone, sdram_size)

		# MINICON
		elif self.ramcon_type == "minicon":
			if self.with_l2:
				raise ValueError("MINICON does not implement L2 cache (Use LASMICON or disable L2 cache (with_l2=False))")

			self.submodules.minicon = sdramcon = minicon.Minicon(phy_settings, sdram_geom, sdram_timing)
			self.submodules.dficon1 = dfi.Interconnect(sdramcon.dfi, self.dfii.slave)
			sdram_width = flen(sdramcon.bus.dat_r)

			sdram_size = 2**(sdram_geom.bank_a+sdram_geom.row_a+sdram_geom.col_a)*sdram_width//8

			if sdram_width == 32:
				self.register_mem("sdram", self.mem_map["sdram"], sdramcon.bus, sdram_size)
			elif sdram_width < 32:
				self.submodules.dc = wishbone.DownConverter(32, sdram_width)
				self.submodules.intercon = wishbone.InterconnectPointToPoint(self.dc.wishbone_o, sdramcon.bus)
				self.register_mem("sdram", self.mem_map["sdram"], self.dc.wishbone_i, sdram_size)
			else:
				raise NotImplementedError("Unsupported SDRAM width of {} > 32".format(sdram_width))
		else:
			raise ValueError("Unsupported SDRAM controller type: {}".format(self.ramcon_type))

	def do_finalize(self):
		if not self._sdram_phy_registered:
			raise FinalizeError("Need to call SDRAMSoC.register_sdram_phy()")
		SoC.do_finalize(self)
