from operator import itemgetter

from migen.fhdl.std import *
from migen.bank import csrgen
from migen.bus import wishbone, csr, wishbone2csr

from misoclib.com.uart.phy import UARTPHY
from misoclib.com import uart
from misoclib.cpu import CPU, lm32, mor1kx
from misoclib.cpu.peripherals import identifier, timer

def mem_decoder(address, start=26, end=29):
	return lambda a: a[start:end] == ((address >> (start+2)) & (2**(end-start))-1)

class SoC(Module):
	csr_map = {
		"crg":					0, # user
		"uart_phy":				1, # provided by default (optional)
		"uart":					2, # provided by default (optional)
		"identifier":			3, # provided by default (optional)
		"timer0":				4, # provided by default (optional)
		"buttons":				5, # user
		"leds":					6, # user
	}
	interrupt_map = {
		"uart":			0,
		"timer0":		1,
	}
	mem_map = {
		"rom":		0x00000000, # (shadow @0x80000000)
		"sram":		0x10000000, # (shadow @0x90000000)
		"main_ram":	0x40000000, # (shadow @0xc0000000)
		"csr":		0x60000000, # (shadow @0xe0000000)
	}
	def __init__(self, platform, clk_freq, cpu_or_bridge=None,
				with_cpu=True, cpu_type="lm32", cpu_reset_address=0x00000000,
							   cpu_boot_file="software/bios/bios.bin",
				with_integrated_rom=False, rom_size=0x8000,
				with_integrated_sram=True, sram_size=4096,
				with_integrated_main_ram=False, main_ram_size=64*1024,
				with_csr=True, csr_data_width=8, csr_address_width=14,
				with_uart=True, uart_baudrate=115200,
				with_identifier=True,
				with_timer=True):
		self.platform = platform
		self.clk_freq = clk_freq
		self.cpu_or_bridge = cpu_or_bridge

		self.with_cpu = with_cpu
		self.cpu_type = cpu_type
		if with_integrated_rom:
			self.cpu_reset_address = 0
		else:
			self.cpu_reset_address = cpu_reset_address
		self.cpu_boot_file = cpu_boot_file

		self.with_integrated_rom = with_integrated_rom
		self.rom_size = rom_size

		self.with_integrated_sram = with_integrated_sram
		self.sram_size = sram_size

		self.with_integrated_main_ram = with_integrated_main_ram
		self.main_ram_size = main_ram_size

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
				self.submodules.cpu = lm32.LM32(platform, self.cpu_reset_address)
			elif cpu_type == "or1k":
				self.submodules.cpu = mor1kx.MOR1KX(platform, self.cpu_reset_address)
			else:
				raise ValueError("Unsupported CPU type: "+cpu_type)
			self.cpu_or_bridge = self.cpu
			self._wb_masters += [self.cpu.ibus, self.cpu.dbus]

			if with_integrated_rom:
				self.submodules.rom = wishbone.SRAM(rom_size, read_only=True)
				self.register_rom(self.rom.bus, rom_size)

			if with_integrated_sram:
				self.submodules.sram = wishbone.SRAM(sram_size)
				self.register_mem("sram", self.mem_map["sram"], self.sram.bus, sram_size)

			# Note: Main Ram can be used when no external SDRAM is available and use SDRAM mapping.
			if with_integrated_main_ram:
				self.submodules.main_ram = wishbone.SRAM(main_ram_size)
				self.register_mem("main_ram", self.mem_map["main_ram"], self.main_ram.bus, main_ram_size)

		elif cpu_or_bridge is not None and not isinstance(cpu_or_bridge, CPU):
			self._wb_masters += [cpu_or_bridge.wishbone]

		if with_csr:
			self.submodules.wishbone2csr = wishbone2csr.WB2CSR(bus_csr=csr.Interface(csr_data_width, csr_address_width))
			self.register_mem("csr", self.mem_map["csr"], self.wishbone2csr.wishbone)

			if with_uart:
				self.submodules.uart_phy = UARTPHY(platform.request("serial"), clk_freq, uart_baudrate)
				self.submodules.uart = uart.UART(self.uart_phy)

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

	def add_memory_region(self, name, origin, length):
		def in_this_region(addr):
			return addr >= origin and addr < origin + length
		for n, o, l in self.memory_regions:
			if n == name or in_this_region(o) or in_this_region(o+l-1):
				raise ValueError("Memory region conflict between {} and {}".format(n, name))

		self.memory_regions.append((name, origin, length))

	def register_mem(self, name, address, interface, size=None):
		self.add_wb_slave(mem_decoder(address), interface)
		if size is not None:
			self.add_memory_region(name, address, size)

	def register_rom(self, interface, rom_size=0xa000):
		self.add_wb_slave(mem_decoder(self.mem_map["rom"]), interface)
		self.add_memory_region("rom", self.cpu_reset_address, rom_size)

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
				self.add_csr_region(name, self.mem_map["csr"]+0x80000000+0x800*mapaddr, self.csr_data_width, csrs)
			for name, memory, mapaddr, mmap in self.csrbankarray.srams:
				self.add_csr_region(name, self.mem_map["csr"]+0x80000000+0x800*mapaddr, self.csr_data_width, memory)

		# Interrupts
		if hasattr(self.cpu_or_bridge, "interrupt"):
			for k, v in sorted(self.interrupt_map.items(), key=itemgetter(1)):
				if hasattr(self, k):
					self.comb += self.cpu_or_bridge.interrupt[v].eq(getattr(self, k).ev.irq)
