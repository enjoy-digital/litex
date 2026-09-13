#
# This file is part of LiteX.
#
# Copyright (c) 2024 Gwenhael Goavec-Merou <gwenhael@enjoy-digital.fr>
# Copyright (c) 2024-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.interconnect import ahb, wishbone
from litex.soc.integration.soc import SoCRegion

from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Gowin AE350 Constants ----------------------------------------------------------------------------

APB_CE_APB   = (1 << 0)
APB_CE_UART1 = (1 << 1)
APB_CE_UART2 = (1 << 2)
APB_CE_SPI   = (1 << 3)
APB_CE_GPIO  = (1 << 4)
APB_CE_PIT   = (1 << 5)
APB_CE_I2C   = (1 << 6)
APB_CE_WDT   = (1 << 7)

# AE350 RAM Bridge ---------------------------------------------------------------------------------

class AE350RAMBridge(LiteXModule):
    def __init__(self, ahb_ram, dbus, port, origin, size):
        from litedram.frontend.wishbone import LiteDRAMWishbone2Native

        # The hard CPU uses the RAM AHB port for both DDR and fabric SRAM. Decode address phases,
        # but select responses with the registered data-phase target while either slave stalls.
        fabric_ahb      = ahb.AHBInterface(data_width=ahb_ram.data_width, address_width=ahb_ram.address_width)
        memory_ahb      = ahb.AHBInterface(data_width=ahb_ram.data_width, address_width=ahb_ram.address_width)
        memory_hit      = Signal()
        memory_selected = Signal()
        self.comb += memory_hit.eq((ahb_ram.addr >= origin) & (ahb_ram.addr < origin + size))
        self.sync += If(ahb_ram.readyout & ahb_ram.sel & ahb_ram.trans[1],
            memory_selected.eq(memory_hit),
        )
        for index, slave in enumerate((fabric_ahb, memory_ahb)):
            for name in ("addr", "trans", "size", "burst", "write", "wdata", "prot", "mastlock"):
                self.comb += getattr(slave, name).eq(getattr(ahb_ram, name))
            # An inactive slave must not accept the following address before global HREADY.
            self.comb += slave.sel.eq(ahb_ram.sel & ahb_ram.readyout & (memory_hit == index))
        for name in ("rdata", "readyout", "resp"):
            self.comb += getattr(ahb_ram, name).eq(Mux(memory_selected,
                getattr(memory_ahb, name), getattr(fabric_ahb, name)))

        # This private Wishbone link bypasses the SoC interconnect and L2. Keep CTI/BTE so the
        # existing LiteDRAM frontend can pack complete cache-line writes without a read allocation.
        memory_bus = wishbone.Interface(
            data_width=ahb_ram.data_width, address_width=ahb_ram.address_width, addressing="word")
        self.memory_bridge   = ahb.AHB2Wishbone(memory_ahb, memory_bus, with_bursting=True)
        self.memory_frontend = LiteDRAMWishbone2Native(memory_bus, port, base_address=origin)
        self.fabric_bridge   = ahb.AHB2Wishbone(fabric_ahb, dbus)

# Gowin AE350 --------------------------------------------------------------------------------------

class GowinAE350(CPU):
    """AE350 hard CPU with ROM, RAM and peripheral AHB-Lite ports connected to LiteX.

    The target supplies the dedicated ``cpu`` clock. All fabric buses use ``sys``.
    Interrupts are not connected; LiteX peripherals use polling.
    """
    variants             = ["standard", "linux"]
    category             = "hardcore"
    family               = "riscv"
    name                 = "gowin_ae350"
    human_name           = "Gowin AE350"
    data_width           = 32
    endianness           = "little"
    reset_address        = 0x8000_0000
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {
        # Origin, Length.
        # Extended AHB slave window (Gowin MUG1029, Table 3-1). The hard CPU is the
        # master on this port; its internal peripherals and APB extension are not on the LiteX bus.
        0xe800_0000 : 0x0800_0000,
    }

    native_memory = False

    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group(title="AE350 CPU options")
        cpu_group.add_argument("--with-native-memory", action="store_true",
            help="Connect DDR directly to LiteDRAM (requires --l2-size=0).")

    @staticmethod
    def args_read(args):
        GowinAE350.native_memory = args.with_native_memory

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "rom"         : 0x8000_0000,
            "sram"        : 0x0000_0000,
            "peripherals" : 0xf000_0000,
            "csr"         : 0xe800_0000,
            "ethmac"      : 0xe801_0000,
            "plic"        : 0xe400_0000,
            "plmt"        : 0xe600_0000,
        }

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags  = " -mabi=ilp32 -march=rv32imafdc"
        flags += " -D__AE350__"
        return flags

    def __init__(self, platform, variant="standard", *args, **kwargs):
        self.native_memory = bool(self.native_memory)

        self.platform     = platform
        self.variant      = variant
        self.io_regions   = dict(self.io_regions)
        if variant == "linux":
            self.io_regions[0xe400_0000] = 0x0400_0000
        self.reset        = Signal()
        self.ibus         = wishbone.Interface(data_width=32, address_width=32, addressing="word")
        self.dbus         = wishbone.Interface(data_width=64, address_width=32, addressing="word")
        self.pbus         = wishbone.Interface(data_width=32, address_width=32, addressing="word")
        self.periph_buses = [self.ibus, self.dbus, self.pbus] # Connected to the main SoC bus.
        self.memory_buses = []                             # Connected directly to LiteDRAM.

        self.ahb_rom  = ahb_rom  = ahb.AHBInterface(data_width=32, address_width=32)
        self.ahb_ram  = ahb_ram  = ahb.AHBInterface(data_width=64, address_width=32)
        self.ahb_exts = ahb_exts = ahb.AHBInterface(data_width=32, address_width=32)

        # # #

        # AHB-Lite Bridges -------------------------------------------------------------------------
        self.comb += [
            # The ROM port only exposes word transfers, without HSEL, HSIZE or HBURST.
            ahb_rom.sel.eq(1),
            ahb_rom.size.eq(0b010),
            ahb_rom.burst.eq(0),
            # The RAM port has no HSEL; HTRANS identifies valid transfers.
            ahb_ram.sel.eq(1),
        ]
        self.rom_bridge    = ahb.AHB2Wishbone(ahb_rom,  self.ibus)
        self.periph_bridge = ahb.AHB2Wishbone(ahb_exts, self.pbus)

        # CPU Instance -----------------------------------------------------------------------------
        self.cpu_params = dict(
            # Clk/Rst.
            i_CORE_CLK       = ClockSignal("cpu"),
            i_DDR_CLK        = ClockSignal("sys"),
            i_AHB_CLK        = ClockSignal("sys"),
            i_APB_CLK        = ClockSignal("sys"),
            i_POR_N          = 1,
            i_HW_RSTN        = ~(ResetSignal("sys") | self.reset),
            o_PRESETN        = Open(),
            o_HRESETN        = Open(),
            o_DDR_RSTN       = Open(),

            # Features/Peripherals Enable.
            i_CORE_CE        = 1,
            i_AXI_CE         = 1,
            i_DDR_CE         = 1,
            i_AHB_CE         = 1,
            i_APB_CE         = Constant(APB_CE_APB, 8),
            i_APB2AHB_CE     = 1,

            # WFI.
            o_CORE0_WFI_MODE = Open(),
            i_WAKEUP_IN      = 0,

            # RTC.
            i_RTC_CLK        = ClockSignal("sys"),
            o_RTC_WAKEUP     = Open(),

            # Interrupts.
            i_GP_INT         = Constant(0, 16),

            # DMA.
            i_DMA_REQ        = Constant(0, 8),
            o_DMA_ACK        = Open(8),

            # AHB-Lite ROM Interface (CPU Master).
            i_ROM_HRDATA     = ahb_rom.rdata,
            i_ROM_HREADY     = ahb_rom.readyout,
            i_ROM_HRESP      = ahb_rom.resp,
            o_ROM_HADDR      = ahb_rom.addr,
            o_ROM_HTRANS     = ahb_rom.trans,
            o_ROM_HWRITE     = ahb_rom.write,

            # APB Fabric Interface (CPU Master, Unused).
            o_APB_PADDR      = Open(32),
            o_APB_PENABLE    = Open(),
            i_APB_PRDATA     = Constant(0, 32),
            i_APB_PREADY     = 0,
            o_APB_PSEL       = Open(),
            o_APB_PWDATA     = Open(32),
            o_APB_PWRITE     = Open(),
            i_APB_PSLVERR    = 0,
            o_APB_PPROT      = Open(3),
            o_APB_PSTRB      = Open(4),

            # AHB-Lite Peripheral Interface (CPU Master).
            i_EXTS_HRDATA    = ahb_exts.rdata,
            i_EXTS_HREADYIN  = ahb_exts.readyout,
            i_EXTS_HRESP     = ahb_exts.resp,
            o_EXTS_HADDR     = ahb_exts.addr,
            o_EXTS_HBURST    = ahb_exts.burst,
            o_EXTS_HPROT     = ahb_exts.prot,
            o_EXTS_HSEL      = ahb_exts.sel,
            o_EXTS_HSIZE     = ahb_exts.size,
            o_EXTS_HTRANS    = ahb_exts.trans,
            o_EXTS_HWDATA    = ahb_exts.wdata,
            o_EXTS_HWRITE    = ahb_exts.write,

            # AHB-Lite Local Memory Interface (CPU Slave, Unused).
            i_EXTM_HADDR     = Constant(0, 32),
            i_EXTM_HBURST    = Constant(0, 3),
            i_EXTM_HPROT     = Constant(0, 4),
            o_EXTM_HRDATA    = Open(64),
            i_EXTM_HREADY    = 0,
            o_EXTM_HREADYOUT = Open(),
            o_EXTM_HRESP     = Open(),
            i_EXTM_HSEL      = 0,
            i_EXTM_HSIZE     = Constant(0, 3),
            i_EXTM_HTRANS    = Constant(0, 2),
            i_EXTM_HWDATA    = Constant(0, 64),
            i_EXTM_HWRITE    = 0,

            # AHB-Lite RAM Interface (CPU Master).
            i_DDR_HRDATA     = ahb_ram.rdata,
            i_DDR_HREADY     = ahb_ram.readyout,
            i_DDR_HRESP      = ahb_ram.resp,
            o_DDR_HADDR      = ahb_ram.addr,
            o_DDR_HBURST     = ahb_ram.burst,
            o_DDR_HPROT      = ahb_ram.prot,
            o_DDR_HSIZE      = ahb_ram.size,
            o_DDR_HTRANS     = ahb_ram.trans,
            o_DDR_HWDATA     = ahb_ram.wdata,
            o_DDR_HWRITE     = ahb_ram.write,

            # GPIOs.
            i_GPIO_IN        = Constant(0, 32),
            o_GPIO_OUT       = Open(32),
            o_GPIO_OE        = Open(32),

            # SCAN.
            i_SCAN_EN        = 0,
            i_SCAN_TEST      = 0,
            i_SCAN_IN        = Constant(0xfffff, 20),
            o_SCAN_OUT       = Open(20),

            # Memory Self-Test JTAG (held in reset).
            i_INTEG_TCK      = 1,
            i_INTEG_TDI      = 1,
            i_INTEG_TMS      = 1,
            i_INTEG_TRST     = 0,
            o_INTEG_TDO      = Open(),

            # SRAM Power, Retention and Timing Controls.
            i_PGEN_CHAIN_I   = 1,
            o_PRDYN_CHAIN_O  = Open(),
            i_EMA            = Constant(0b011, 3),
            i_EMAW           = Constant(0b01, 2),
            i_EMAS           = 0,
            i_RET1N          = 1,
            i_RET2N          = 1,

            # SPI.
            i_SPI2_HOLDN_IN  = 0,
            i_SPI2_WPN_IN    = 0,
            i_SPI2_CLK_IN    = 0,
            i_SPI2_CSN_IN    = 0,
            i_SPI2_MISO_IN   = 0,
            i_SPI2_MOSI_IN   = 0,
            o_SPI2_HOLDN_OUT = Open(),
            o_SPI2_HOLDN_OE  = Open(),
            o_SPI2_WPN_OUT   = Open(),
            o_SPI2_WPN_OE    = Open(),
            o_SPI2_CLK_OUT   = Open(),
            o_SPI2_CLK_OE    = Open(),
            o_SPI2_CSN_OUT   = Open(),
            o_SPI2_CSN_OE    = Open(),
            o_SPI2_MISO_OUT  = Open(),
            o_SPI2_MISO_OE   = Open(),
            o_SPI2_MOSI_OUT  = Open(),
            o_SPI2_MOSI_OE   = Open(),

            # I2C.
            i_I2C_SCL_IN     = 0,
            i_I2C_SDA_IN     = 0,
            o_I2C_SCL        = Open(),
            o_I2C_SDA        = Open(),

            # PIT/PWM.
            o_CH0_PWM        = Open(),
            o_CH0_PWMOE      = Open(),
            o_CH1_PWM        = Open(),
            o_CH1_PWMOE      = Open(),
            o_CH2_PWM        = Open(),
            o_CH2_PWMOE      = Open(),
            o_CH3_PWM        = Open(),
            o_CH3_PWMOE      = Open(),

            # UART1.
            o_UART1_TXD      = Open(),
            o_UART1_RTSN     = Open(),
            i_UART1_RXD      = 0,
            i_UART1_CTSN     = 0,
            i_UART1_DSRN     = 0,
            i_UART1_DCDN     = 0,
            i_UART1_RIN      = 0,
            o_UART1_DTRN     = Open(),
            o_UART1_OUT1N    = Open(),
            o_UART1_OUT2N    = Open(),

            # UART2.
            o_UART2_TXD      = Open(),
            o_UART2_RTSN     = Open(),
            i_UART2_RXD      = 0,
            i_UART2_CTSN     = 1,
            i_UART2_DCDN     = 1,
            i_UART2_DSRN     = 1,
            i_UART2_RIN      = 1,
            o_UART2_DTRN     = Open(),
            o_UART2_OUT1N    = Open(),
            o_UART2_OUT2N    = Open(),

            # JTAG.
            i_DBG_TCK        = 1,
            i_TMS_IN         = 1,
            i_TRST_IN        = 1,
            i_TDI_IN         = 0,
            o_TDO_OUT        = Open(),
            o_TDO_OE         = Open(),

            # Test.
            i_TEST_CLK       = 0,
            i_TEST_MODE      = 0,
            i_TEST_RSTN      = 1,
        )

    def add_soc_components(self, soc):
        # SDRAM is added after CPU setup; retain the dictionaries to use its final region and L2 size.
        self.soc_regions   = soc.bus.regions
        self.soc_constants = soc.constants

        soc.add_config("CPU_COUNT", 1)
        soc.add_config("CPU_ISA",   "rv32imafdc")
        soc.add_config("CPU_MMU",   "sv32")
        # The machine timer inside the macro counts on the AHB clock, which LiteX drives from sys_clk.
        soc.add_config("CPU_SYSTEM_CLOCK_NODE_REF", "clk_sys")

        if self.variant == "linux":
            # These peripherals are internal to the hard CPU, outside the fabric bus.
            soc.bus.add_region("plic", SoCRegion(
                origin=self.mem_map["plic"], size=0x40_0000, cached=False, linker=True))
            soc.bus.add_region("plmt", SoCRegion(
                origin=self.mem_map["plmt"], size=0x1000, cached=False, linker=True))
            soc.bus.add_region("opensbi", SoCRegion(
                origin=soc.mem_map["main_ram"] + 0x00f0_0000, size=0x8_0000, cached=True, linker=True))
            soc.add_config("CPU_PLIC_NDEV", 27)
            soc.add_config("CPU_TIMEBASE_FREQUENCY", int(soc.clk_freq))

    def check_sdram(self, phy, data_width):
        if self.native_memory and not getattr(phy.settings, "with_dm", True):
            raise ValueError("AE350 native memory requires SDRAM byte write masks.")

    def add_memory_buses(self, address_width, data_width):
        if not self.native_memory:
            return
        from litedram.common import LiteDRAMNativePort

        region = self.soc_regions["main_ram"]
        port = LiteDRAMNativePort(
            mode          = "both",
            address_width = address_width - log2_int(data_width//8),
            data_width    = data_width,
        )
        self.ram_bridge = AE350RAMBridge(self.ahb_ram, self.dbus, port, region.origin, region.size)
        self.memory_buses.append(port)

    def set_reset_address(self, reset_address):
        if reset_address != self.reset_address:
            raise ValueError("Gowin AE350 reset address is fixed at 0x80000000.")

    def connect_jtag(self, pads):
        self.cpu_params.update(
            i_DBG_TCK = pads.tck,
            i_TMS_IN  = pads.tms,
            i_TRST_IN = pads.trst,
            i_TDI_IN  = pads.tdi,
            o_TDO_OUT = pads.tdo,
            o_TDO_OE  = Open(),
        )

    def do_finalize(self):
        if self.memory_buses and self.soc_constants.get("CONFIG_L2_SIZE", 0):
            raise ValueError(
                "AE350 native memory bypasses the fabric L2; use --l2-size=0 to keep "
                "CPU and other fabric masters consistent.")
        if not hasattr(self, "ram_bridge"):
            self.ram_bridge = ahb.AHB2Wishbone(self.ahb_ram, self.dbus)
        self.specials += Instance("AE350_SOC", **self.cpu_params)
