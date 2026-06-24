#
# This file is part of LiteX.
#
# Copyright (c) 2024 Gwenhael Goavec-Merou <gwenhael@enjoy-digital.fr>
# Copyright (c) 2024 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex.soc.interconnect import wishbone, ahb
from litex.soc.interconnect.csr import *
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

# Gowin AE350 --------------------------------------------------------------------------------------

class GowinAE350(CPU):
    variants             = ["standard"]
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
        0xe800_0000: 0x6000_0000
    }

    @property
    def mem_map(self):
        return {
            "rom"         : 0x80000000,
            "sram"        : 0x00000000,
            "peripherals" : 0xf0000000,
            "csr"         : 0xe8000000,
        }

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  f" -mabi=ilp32 -march=rv32imafdc"
        flags += f" -D__AE350__"
        return flags

    def __init__(self, platform, variant, *args, **kwargs):
        self.platform     = platform
        self.reset        = Signal()
        self.ibus         = ibus = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
        self.dbus         = dbus = wishbone.Interface(data_width=64, address_width=32, addressing="word")
        self.pbus         = pbus = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
        self.periph_buses = [ibus, dbus, pbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []                 # Memory buses (Connected directly to LiteDRAM).


        # AHBLite Buses.
        # --------------
        self.ahb_rom   = ahb_rom  = ahb.AHBInterface(data_width=32, address_width=32)
        self.ahb_ram   = ahb_ram  = ahb.AHBInterface(data_width=64, address_width=32)
        self.ahb_exts  = ahb_exts = ahb.AHBInterface(data_width=32, address_width=32)
        self.comb += [
            # Set AHBLite ROM static signals.
            ahb_rom.sel.eq(1),
            ahb_rom.size.eq(0b010),
            ahb_rom.burst.eq(0),
            # Set AHBLite RAM static signals.
            ahb_ram.sel.eq(1),
        ]

        # CPU Instance.
        # -------------
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

            # AHBLite ROM interface.
            i_ROM_HRDATA     = ahb_rom.rdata,
            i_ROM_HREADY     = ahb_rom.readyout,
            i_ROM_HRESP      = ahb_rom.resp,
            o_ROM_HADDR      = ahb_rom.addr,
            o_ROM_HTRANS     = ahb_rom.trans,
            o_ROM_HWRITE     = ahb_rom.write,

            # APBLite Fabric interface (Slave).
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

            # AHBLite Peripheral interface (Master).
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

            # AHBLite Peripheral interface (Slave).
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

            # AHBLite RAM interface (Slave).
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

            # Integrated JTAG.
            i_INTEG_TCK      = 1,
            i_INTEG_TDI      = 1,
            i_INTEG_TMS      = 1,
            i_INTEG_TRST     = 1,
            o_INTEG_TDO      = Open(),

            # SRAM (FIXME    : Cleanup).
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

        # AHBLite ROM Interface.
        # ----------------------
        self.submodules += ahb.AHB2Wishbone(ahb_rom, self.ibus)

        # AHBLite RAM Interface.
        # ----------------------
        self.submodules += ahb.AHB2Wishbone(ahb_ram, self.dbus)

        # AHBLite Peripheral Interface.
        # -----------------------------
        self.submodules += ahb.AHB2Wishbone(ahb_exts, self.pbus)

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
        self.specials += Instance("AE350_SOC", **self.cpu_params)
