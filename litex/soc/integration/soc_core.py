from operator import itemgetter

from litex.gen import *

from litex.soc.cores import identifier, timer, uart
from litex.soc.cores.cpu import lm32, mor1kx, picorv32
from litex.soc.interconnect import wishbone, csr_bus, wishbone2csr


__all__ = ["mem_decoder", "SoCCore", "soc_core_args", "soc_core_argdict"]


def version(with_time=True):
    import datetime
    import time
    if with_time:
        return datetime.datetime.fromtimestamp(
                time.time()).strftime("%Y-%m-%d %H:%M:%S")
    else:
        return datetime.datetime.fromtimestamp(
                time.time()).strftime("%Y-%m-%d")


def mem_decoder(address, start=26, end=29):
    return lambda a: a[start:end] == ((address >> (start+2)) & (2**(end-start))-1)


class ReadOnlyDict(dict):
    def __readonly__(self, *args, **kwargs):
        raise RuntimeError("Cannot modify ReadOnlyDict")
    __setitem__ = __readonly__
    __delitem__ = __readonly__
    pop = __readonly__
    popitem = __readonly__
    clear = __readonly__
    update = __readonly__
    setdefault = __readonly__
    del __readonly__


class SoCCore(Module):
    csr_map = {
        "crg":            0,  # user
        "uart_phy":       1,  # provided by default (optional)
        "uart":           2,  # provided by default (optional)
        "identifier_mem": 3,  # provided by default (optional)
        "timer0":         4,  # provided by default (optional)
        "buttons":        5,  # user
        "leds":           6,  # user
    }
    interrupt_map = {}
    soc_interrupt_map = {
        "timer0": 1, # LiteX Timer
        "uart":   2, # LiteX UART (IRQ 2 for UART matches mor1k standard config).
    }
    mem_map = {
        "rom":      0x00000000,  # (default shadow @0x80000000)
        "sram":     0x10000000,  # (default shadow @0x90000000)
        "main_ram": 0x40000000,  # (default shadow @0xc0000000)
        "csr":      0x60000000,  # (default shadow @0xe0000000)
    }
    def __init__(self, platform, clk_freq,
                cpu_type="lm32", cpu_reset_address=0x00000000, cpu_variant=None,
                integrated_rom_size=0, integrated_rom_init=[],
                integrated_sram_size=4096,
                integrated_main_ram_size=0, integrated_main_ram_init=[],
                shadow_base=0x80000000,
                csr_data_width=8, csr_address_width=14,
                with_uart=True, uart_name="serial", uart_baudrate=115200, uart_stub=False,
                ident="", ident_version=False,
                reserve_nmi_interrupt=True,
                with_timer=True):
        self.config = dict()

        self.platform = platform
        self.clk_freq = clk_freq

        self.cpu_type = cpu_type
        self.cpu_variant = cpu_variant
        if integrated_rom_size:
            cpu_reset_address = self.mem_map["rom"]
        self.cpu_reset_address = cpu_reset_address
        self.config["CPU_RESET_ADDR"] = self.cpu_reset_address

        self.integrated_rom_size = integrated_rom_size
        self.integrated_rom_initialized = integrated_rom_init != []
        self.integrated_sram_size = integrated_sram_size
        self.integrated_main_ram_size = integrated_main_ram_size

        self.with_uart = with_uart
        self.uart_baudrate = uart_baudrate

        self.shadow_base = shadow_base

        self.csr_data_width = csr_data_width
        self.csr_address_width = csr_address_width

        self._memory_regions = []  # list of (name, origin, length)
        self._csr_regions = []  # list of (name, origin, busword, csr_list/Memory)
        self._constants = []  # list of (name, value)

        self._wb_masters = []
        self._wb_slaves = []

        if cpu_type is not None:
            if cpu_type == "lm32":
                self.add_cpu_or_bridge(lm32.LM32(platform, self.cpu_reset_address, self.cpu_variant))
            elif cpu_type == "or1k":
                self.add_cpu_or_bridge(mor1kx.MOR1KX(platform, self.cpu_reset_address, self.cpu_variant))
            elif cpu_type == "riscv32":
                self.add_cpu_or_bridge(picorv32.PicoRV32(platform, self.cpu_reset_address, self.cpu_variant))
            else:
                raise ValueError("Unsupported CPU type: {}".format(cpu_type))
            self.add_wb_master(self.cpu_or_bridge.ibus)
            self.add_wb_master(self.cpu_or_bridge.dbus)
        self.config["CPU_TYPE"] = str(cpu_type).upper()
        if self.cpu_variant:
            self.config["CPU_VARIANT"] = str(cpu_type).upper()

        if integrated_rom_size:
            self.submodules.rom = wishbone.SRAM(integrated_rom_size, read_only=True, init=integrated_rom_init)
            self.register_rom(self.rom.bus, integrated_rom_size)

        if integrated_sram_size:
            self.submodules.sram = wishbone.SRAM(integrated_sram_size)
            self.register_mem("sram", self.mem_map["sram"], self.sram.bus, integrated_sram_size)

        # Note: Main Ram can be used when no external SDRAM is available and use SDRAM mapping.
        if integrated_main_ram_size:
            self.submodules.main_ram = wishbone.SRAM(integrated_main_ram_size, init=integrated_main_ram_init)
            self.register_mem("main_ram", self.mem_map["main_ram"], self.main_ram.bus, integrated_main_ram_size)

        self.submodules.wishbone2csr = wishbone2csr.WB2CSR(
            bus_csr=csr_bus.Interface(csr_data_width, csr_address_width))
        self.config["CSR_DATA_WIDTH"] = csr_data_width
        self.add_constant("CSR_DATA_WIDTH", csr_data_width)
        self.register_mem("csr", self.mem_map["csr"], self.wishbone2csr.wishbone)

        if reserve_nmi_interrupt:
            self.soc_interrupt_map["nmi"] = 0 # Reserve zero for "non-maskable interrupt"

        if with_uart:
            if uart_stub:
                self.submodules.uart  = uart.UARTStub()
            else:
                self.submodules.uart_phy = uart.RS232PHY(platform.request(uart_name), clk_freq, uart_baudrate)
                self.submodules.uart = uart.UART(self.uart_phy)
        #else:
        #    del self.soc_interrupt_map["uart"]

        if ident:
            if ident_version:
                ident = ident + " " + version()
            self.submodules.identifier = identifier.Identifier(ident)
        self.config["CLOCK_FREQUENCY"] = int(clk_freq)
        self.add_constant("SYSTEM_CLOCK_FREQUENCY", int(clk_freq))

        if with_timer:
            self.submodules.timer0 = timer.Timer()
        else:
            del self.soc_interrupt_map["timer0"]

        # Invert the interrupt map.
        interrupt_rmap = {}
        for mod_name, interrupt in self.interrupt_map.items():
            assert interrupt not in interrupt_rmap, (
                "Interrupt vector conflict for IRQ %s, user defined %s conflicts with user defined %s" % (
                    interrupt, mod_name, interrupt_rmap[interrupt]))

            interrupt_rmap[interrupt] = mod_name

        # Add the base SoC's interrupt map
        for mod_name, interrupt in self.soc_interrupt_map.items():
            assert interrupt not in interrupt_rmap or mod_name == interrupt_rmap[interrupt], (
                "Interrupt vector conflict for IRQ %s, user defined %s conflicts with SoC inbuilt %s" % (
                    interrupt, mod_name, interrupt_rmap[interrupt]))

            self.interrupt_map[mod_name] = interrupt
            interrupt_rmap[interrupt] = mod_name

        # Make sure other functions are not using this value.
        self.soc_interrupt_map = None

        # Make the interrupt vector read only
        self.interrupt_map = ReadOnlyDict(self.interrupt_map)

        # Save the interrupt reverse map
        self.interrupt_rmap = ReadOnlyDict(interrupt_rmap)


    def add_cpu_or_bridge(self, cpu_or_bridge):
        if self.finalized:
            raise FinalizeError
        if hasattr(self, "cpu_or_bridge"):
            raise NotImplementedError("More than one CPU is not supported")
        self.submodules.cpu_or_bridge = cpu_or_bridge

    def initialize_rom(self, data):
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
        for n, o, l in self._memory_regions:
            if n == name or in_this_region(o) or in_this_region(o+l-1):
                raise ValueError("Memory region conflict between {} and {}".format(n, name))

        self._memory_regions.append((name, origin, length))

    def register_mem(self, name, address, interface, size=None):
        self.add_wb_slave(mem_decoder(address), interface)
        if size is not None:
            self.add_memory_region(name, address, size)

    def register_rom(self, interface, rom_size=0xa000):
        self.add_wb_slave(mem_decoder(self.mem_map["rom"]), interface)
        self.add_memory_region("rom", self.cpu_reset_address, rom_size)

    def get_memory_regions(self):
        return self._memory_regions

    def check_csr_region(self, name, origin):
        for n, o, l, obj in self._csr_regions:
            if n == name or o == origin:
                raise ValueError("CSR region conflict between {} and {}".format(n, name))

    def add_csr_region(self, name, origin, busword, obj):
        self.check_csr_region(name, origin)
        self._csr_regions.append((name, origin, busword, obj))

    def get_csr_regions(self):
        return self._csr_regions

    def add_constant(self, name, value=None):
        self._constants.append((name, value))

    def get_constants(self):
        r = []
        for interrupt, name in sorted(self.interrupt_rmap.items()):
            r.append((name.upper() + "_INTERRUPT", interrupt))
        r += self._constants
        return r

    def get_csr_dev_address(self, name, memory):
        if memory is not None:
            name = name + "_" + memory.name_override
        try:
            return self.csr_map[name]
        except ValueError:
            return None

    def do_finalize(self):
        registered_mems = {regions[0] for regions in self._memory_regions}
        if self.cpu_type is not None:
            for mem in "rom", "sram":
                if mem not in registered_mems:
                    raise FinalizeError("CPU needs a {} to be registered with SoC.register_mem()".format(mem))

        if len(self._wb_masters):
            # Wishbone
            self.submodules.wishbonecon = wishbone.InterconnectShared(self._wb_masters,
                self._wb_slaves, register=True)

            # CSR
            self.submodules.csrbankarray = csr_bus.CSRBankArray(self,
                self.get_csr_dev_address,
                data_width=self.csr_data_width, address_width=self.csr_address_width)
            self.submodules.csrcon = csr_bus.Interconnect(
                self.wishbone2csr.csr, self.csrbankarray.get_buses())
            for name, csrs, mapaddr, rmap in self.csrbankarray.banks:
                self.add_csr_region(name, (self.mem_map["csr"] + 0x800*mapaddr) | self.shadow_base, self.csr_data_width, csrs)
            for name, memory, mapaddr, mmap in self.csrbankarray.srams:
                self.add_csr_region(name + "_" + memory.name_override, (self.mem_map["csr"] + 0x800*mapaddr) | self.shadow_base, self.csr_data_width, memory)
            for name, constant in self.csrbankarray.constants:
                self._constants.append(((name + "_" + constant.name).upper(), constant.value.value))
            for name, value in sorted(self.config.items(), key=itemgetter(0)):
                self._constants.append(("CONFIG_" + name.upper(), value))

            # Interrupts
            if hasattr(self.cpu_or_bridge, "interrupt"):
                for interrupt, mod_name in sorted(self.interrupt_rmap.items()):
                    if mod_name == "nmi":
                        continue
                    assert hasattr(self, mod_name), "Missing module for interrupt %s" % mod_name
                    mod_impl = getattr(self, mod_name)
                    assert hasattr(mod_impl, 'ev'), "Submodule %s does not have EventManager (xx.ev) module" % mod_name
                    self.comb += self.cpu_or_bridge.interrupt[interrupt].eq(mod_impl.ev.irq)

    def build(self, *args, **kwargs):
        return self.platform.build(self, *args, **kwargs)


def soc_core_args(parser):
    parser.add_argument("--cpu-type", default=None,
                        help="select CPU: lm32, or1k, riscv32")
    parser.add_argument("--integrated-rom-size", default=None, type=int,
                        help="size/enable the integrated (BIOS) ROM")
    parser.add_argument("--integrated-main-ram-size", default=None, type=int,
                        help="size/enable the integrated main RAM")


def soc_core_argdict(args):
    r = dict()
    for a in "cpu_type", "integrated_rom_size", "integrated_main_ram_size":
        arg = getattr(args, a)
        if arg is not None:
            r[a] = arg
    return r
