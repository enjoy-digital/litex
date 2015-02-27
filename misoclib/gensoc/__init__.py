from operator import itemgetter
from math import ceil

from migen.fhdl.std import *
from migen.bank import csrgen
from migen.bus import wishbone, csr, lasmibus, dfi
from migen.bus import wishbone2lasmi, wishbone2csr

from misoclib import uart, identifier, timer
from misoclib.cpu import lm32, mor1kx
from misoclib.sdram import lasmicon
from misoclib.sdram import dfii
from misoclib.sdram import memtest
from misoclib.sdram.minicon import Minicon

def mem_decoder(address, start=26, end=29):
	return lambda a: a[start:end] == ((address >> (start+2)) & (2**(end-start))-1)

class GenSoC(Module):
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
	mem_map = {
		"rom":		0x00000000, # (shadow @0x80000000)
		"sram":		0x10000000, # (shadow @0x90000000)
		"csr":		0x60000000, # (shadow @0xe0000000)
	}
	def __init__(self, platform, clk_freq, cpu_reset_address, sram_size=4096, with_uart=True, cpu_type="lm32",
				csr_data_width=8, csr_address_width=14):
		self.clk_freq = clk_freq
		self.cpu_reset_address = cpu_reset_address
		self.sram_size = sram_size
		self.cpu_type = cpu_type
		self.csr_data_width = csr_data_width
		self.csr_address_width = csr_address_width
		self.cpu_memory_regions = []
		self.cpu_csr_regions = [] # list of (name, origin, busword, csr_list/Memory)
		self._rom_registered = False

		# Wishbone
		if cpu_type == "lm32":
			self.submodules.cpu = lm32.LM32(platform, cpu_reset_address)
		elif cpu_type == "or1k":
			self.submodules.cpu = mor1kx.MOR1KX(platform, cpu_reset_address)
		else:
			raise ValueError("Unsupported CPU type: "+cpu_type)
		self.submodules.sram = wishbone.SRAM(sram_size)
		self.submodules.wishbone2csr = wishbone2csr.WB2CSR(bus_csr=csr.Interface(csr_data_width, csr_address_width))

		# rom          0x00000000 (shadow @0x80000000) from register_rom
		# SRAM/debug   0x10000000 (shadow @0x90000000) provided
		# CSR bridge   0x60000000 (shadow @0xe0000000) provided
		self._wb_masters = [self.cpu.ibus, self.cpu.dbus]
		self._wb_slaves = [
			(mem_decoder(self.mem_map["sram"]), self.sram.bus),
			(mem_decoder(self.mem_map["csr"]), self.wishbone2csr.wishbone)
		]
		self.add_cpu_memory_region("sram", self.mem_map["sram"], sram_size)

		# CSR
		if with_uart:
			self.submodules.uart = uart.UART(platform.request("serial"), clk_freq, baud=115200)
		platform_id = 0x554E if not hasattr(platform, "identifier") else platform.identifier
		self.submodules.identifier = identifier.Identifier(platform_id, int(clk_freq))
		self.submodules.timer0 = timer.Timer()

	def register_rom(self, rom_wb_if, bios_size=0xa000):
		if self._rom_registered:
			raise FinalizeError
		self._rom_registered = True

		self.add_wb_slave(mem_decoder(self.mem_map["rom"]), rom_wb_if)
		self.add_cpu_memory_region("rom", self.cpu_reset_address, bios_size)

	def add_wb_master(self, wbm):
		if self.finalized:
			raise FinalizeError
		self._wb_masters.append(wbm)

	def add_wb_slave(self, address_decoder, interface):
		if self.finalized:
			raise FinalizeError
		self._wb_slaves.append((address_decoder, interface))

	def check_cpu_memory_region(self, name, origin):
		for n, o, l in self.cpu_memory_regions:
			if n == name or o == origin:
				raise ValueError("Memory region conflict between {} and {}".format(n, name))

	def add_cpu_memory_region(self, name, origin, length):
		self.check_cpu_memory_region(name, origin)
		self.cpu_memory_regions.append((name, origin, length))

	def check_cpu_csr_region(self, name, origin):
		for n, o, l, obj in self.cpu_csr_regions:
			if n == name or o == origin:
				raise ValueError("CSR region conflict between {} and {}".format(n, name))

	def add_cpu_csr_region(self, name, origin, busword, obj):
		self.check_cpu_csr_region(name, origin)
		self.cpu_csr_regions.append((name, origin, busword, obj))

	def do_finalize(self):
		if not self._rom_registered:
			raise FinalizeError("Need to call GenSoC.register_rom()")

		# Wishbone
		self.submodules.wishbonecon = wishbone.InterconnectShared(self._wb_masters,
			self._wb_slaves, register=True)

		# CSR
		self.submodules.csrbankarray = csrgen.BankArray(self,
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override],
			data_width=self.csr_data_width, address_width=self.csr_address_width)
		self.submodules.csrcon = csr.Interconnect(self.wishbone2csr.csr, self.csrbankarray.get_buses())
		for name, csrs, mapaddr, rmap in self.csrbankarray.banks:
			self.add_cpu_csr_region(name, self.mem_map["csr"]+0x80000000+0x800*mapaddr, flen(rmap.bus.dat_w), csrs)
		for name, memory, mapaddr, mmap in self.csrbankarray.srams:
			self.add_cpu_csr_region(name, self.mem_map["csr"]+0x80000000+0x800*mapaddr, flen(rmap.bus.dat_w), memory)

		# Interrupts
		for k, v in sorted(self.interrupt_map.items(), key=itemgetter(1)):
			if hasattr(self, k):
				self.comb += self.cpu.interrupt[v].eq(getattr(self, k).ev.irq)

	def ns(self, t, margin=True):
		clk_period_ns = 1000000000/self.clk_freq
		if margin:
			t += clk_period_ns/2
		return ceil(t/clk_period_ns)

	def do_exit(self, vns):
		pass

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
		"wishbone2lasmi":		8,
		"memtest_w":			9,
		"memtest_r":			10
	}
	csr_map.update(GenSoC.csr_map)

	mem_map = {
		"sdram":	0x40000000, # (shadow @0xc0000000)
	}
	mem_map.update(GenSoC.mem_map)

	def __init__(self, platform, clk_freq, cpu_reset_address, with_memtest=False, sram_size=4096, l2_size=8192, with_uart=True, ramcon_type="lasmicon", **kwargs):
		GenSoC.__init__(self, platform, clk_freq, cpu_reset_address, sram_size, with_uart, **kwargs)
		self.l2_size = l2_size
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

		# LASMICON
		if self.ramcon_type == "lasmicon":
			self.submodules.lasmicon = lasmicon.LASMIcon(phy_settings, sdram_geom, sdram_timing)
			self.submodules.dficon1 = dfi.Interconnect(self.lasmicon.dfi, self.dfii.slave)

			self.submodules.lasmixbar = lasmibus.Crossbar([self.lasmicon.lasmic], self.lasmicon.nrowbits)

			if self.with_memtest:
				self.submodules.memtest_w = memtest.MemtestWriter(self.lasmixbar.get_master())
				self.submodules.memtest_r = memtest.MemtestReader(self.lasmixbar.get_master())

			# Wishbone bridge
			self.submodules.wishbone2lasmi = wishbone2lasmi.WB2LASMI(self.l2_size//4, self.lasmixbar.get_master())
			self.add_wb_slave(mem_decoder(self.mem_map["sdram"]), self.wishbone2lasmi.wishbone)
			self.add_cpu_memory_region("sdram", self.mem_map["sdram"],
				2**self.lasmicon.lasmic.aw*self.lasmicon.lasmic.dw*self.lasmicon.lasmic.nbanks//8)
		# MINICON
		elif self.ramcon_type == "minicon":
			self.submodules.minicon = sdramcon = Minicon(phy_settings, sdram_geom, sdram_timing)
			self.submodules.dficon1 = dfi.Interconnect(sdramcon.dfi, self.dfii.slave)
			sdram_width = flen(sdramcon.bus.dat_r)

			if (sdram_width == 32):
				self.add_wb_slave(mem_decoder(self.mem_map["sdram"]), sdramcon.bus)
			elif (sdram_width < 32):
				self.submodules.dc = wishbone.DownConverter(32, sdram_width)
				self.submodules.intercon = wishbone.InterconnectPointToPoint(self.dc.wishbone_o, sdramcon.bus)
				self.add_wb_slave(mem_decoder(self.mem_map["sdram"]), self.dc.wishbone_i)
			else:
				raise NotImplementedError("Unsupported SDRAM width of {} > 32".format(sdram_width))

			# Wishbone bridge
			self.add_cpu_memory_region("sdram", self.mem_map["sdram"],
				2**(sdram_geom.bank_a+sdram_geom.row_a+sdram_geom.col_a)*sdram_width//8)
		else:
			raise ValueError("Unsupported SDRAM controller type: {}".format(self.ramcon_type))

	def do_finalize(self):
		if not self._sdram_phy_registered:
			raise FinalizeError("Need to call SDRAMSoC.register_sdram_phy()")
		GenSoC.do_finalize(self)
