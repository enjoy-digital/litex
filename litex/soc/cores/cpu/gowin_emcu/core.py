#
# This file is part of LiteX.
#
# Copyright (c) 2021 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# Copyright (c) 2024 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.cores.cpu import CPU
from litex.soc.interconnect import wishbone
from litex.soc.interconnect import ahb

# Gowin EMCU (Enhanced MCU / Cortex M3) ------------------------------------------------------------

class GowinEMCU(CPU):
    variants             = ["standard"]
    category             = "hardcore"
    family               = "arm"
    name                 = "gowin_emcu"
    human_name           = "Gowin EMCU"
    data_width           = 32
    endianness           = "little"
    reset_address        = 0x0000_0000
    gcc_triple           = "arm-none-eabi"
    linker_output_format = "elf32-littlearm"
    nop                  = "nop"
    io_regions           = {
        # Origin, Length.
        0x4000_0000 : 0x2000_0000,
        0xa000_0000 : 0x6000_0000,
    }

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "rom"      : 0x0000_0000,
            "sram"     : 0x2000_0000,
            "main_ram" : 0x1000_0000,
            "csr"      : 0xa000_0000,
        }

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  f" -march=armv7-m -mthumb"
        flags += f" -D__CortexM3__"
        flags += f" -DUART_POLLING"
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform      = platform
        self.reset         = Signal()
        self.pbus          = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
        self.periph_buses  = [self.pbus]
        self.memory_buses  = []

        # CPU Instance.
        # -------------

        bus_reset_n  = Signal()
        ahb_flash    = ahb.AHBInterface(data_width=32, address_width=32)
        ahb_targexp0 = ahb.AHBInterface(data_width=32, address_width=32)

        self.cpu_params = dict(
            # Clk/Rst.
            i_FCLK           = ClockSignal("sys"),
            i_PORESETN       = ~ (ResetSignal("sys") | self.reset),
            i_SYSRESETN      = ~ (ResetSignal("sys") | self.reset),
            i_MTXREMAP       = Signal(4, reset=0b1111),
            o_MTXHRESETN     = bus_reset_n,

            # RTC.
            i_RTCSRCCLK      = 0b0, # RTC Clk In.

            # GPIOs.
            i_IOEXPINPUTI    = 0x0000,   # GPIO Input  (16-bit).
            o_IOEXPOUTPUTO   = Open(16), # GPIO Output (16-bit).
            o_IOEXPOUTPUTENO = Open(16), # GPIO Output Enable (16-bit).

            # UART0.
            i_UART0RXDI     = 0b0,
            o_UART0TXDO     = Open(),
            o_UART0BAUDTICK = Open(),

            # UART1.
            i_UART1RXDI     = 0b0,
            o_UART1TXDO     = Open(),
            o_UART1BAUDTICK = Open(),

            # Interrupts.
            i_GPINT          = 0,
            o_INTMONITOR     = Open(),

            # Flash.
            i_FLASHERR       = Signal(),
            i_FLASHINT       = Signal(),

            # Debug/JTAG.
            o_DAPTDO      = Open(),
            o_DAPJTAGNSW  = Open(),
            o_DAPNTDOEN   = Open(),
            i_DAPSWDITMS  = 0,
            i_DAPTDI      = 0,
            i_DAPNTRST    = 0,
            i_DAPSWCLKTCK = 0,

            # TARGFLASH0 / AHBLite Master.
            o_TARGFLASH0HSEL      = ahb_flash.sel,
            o_TARGFLASH0HADDR     = ahb_flash.addr,
            o_TARGFLASH0HTRANS    = ahb_flash.trans,
            o_TARGFLASH0HSIZE     = ahb_flash.size,
            o_TARGFLASH0HBURST    = ahb_flash.burst,
            o_TARGFLASH0HREADYMUX = Open(),
            i_TARGFLASH0HRDATA    = ahb_flash.rdata,
            i_TARGFLASH0HRUSER    = 0b000,
            i_TARGFLASH0HRESP     = ahb_flash.resp,
            i_TARGFLASH0EXRESP    = 0b0,
            i_TARGFLASH0HREADYOUT = ahb_flash.readyout,

            # TARGEXP0 / AHBLite Master.
            o_TARGEXP0HSEL        = ahb_targexp0.sel,
            o_TARGEXP0HADDR       = ahb_targexp0.addr,
            o_TARGEXP0HTRANS      = ahb_targexp0.trans,
            o_TARGEXP0HWRITE      = ahb_targexp0.write,
            o_TARGEXP0HSIZE       = ahb_targexp0.size,
            o_TARGEXP0HBURST      = ahb_targexp0.burst,
            o_TARGEXP0HPROT       = ahb_targexp0.prot,
            o_TARGEXP0MEMATTR     = Open(2),
            o_TARGEXP0EXREQ       = Open(),
            o_TARGEXP0HMASTER     = Open(4),
            o_TARGEXP0HWDATA      = ahb_targexp0.wdata,
            o_TARGEXP0HMASTLOCK   = ahb_targexp0.mastlock,
            o_TARGEXP0HREADYMUX   = Open(),
            o_TARGEXP0HAUSER      = Open(),
            o_TARGEXP0HWUSER      = Open(4),
            i_TARGEXP0HRDATA      = ahb_targexp0.rdata,
            i_TARGEXP0HREADYOUT   = ahb_targexp0.readyout,
            i_TARGEXP0HRESP       = ahb_targexp0.resp,
            i_TARGEXP0EXRESP      = 0b0,
            i_TARGEXP0HRUSER      = 0b000,

            # INITEXP0 / AHBLite Slave.
            o_INITEXP0HRDATA    = Open(32),
            o_INITEXP0HREADY    = Open(),
            o_INITEXP0HRESP     = Open(),
            o_INITEXP0EXRESP    = Open(),
            o_INITEXP0HRUSER    = Open(3),
            i_INITEXP0HSEL      = 0b0,
            i_INITEXP0HADDR     = 0x00000000,
            i_INITEXP0HTRANS    = 0b00,
            i_INITEXP0HWRITE    = 0b0,
            i_INITEXP0HSIZE     = 0b000,
            i_INITEXP0HBURST    = 0b000,
            i_INITEXP0HPROT     = 0b0000,
            i_INITEXP0MEMATTR   = 0b00,
            i_INITEXP0EXREQ     = 0b0,
            i_INITEXP0HMASTER   = 0b0000,
            i_INITEXP0HWDATA    = 0x00000000,
            i_INITEXP0HMASTLOCK = 0b0,
            i_INITEXP0HAUSER    = 0b0,
            i_INITEXP0HWUSER    = 0b0000,
        )

        # SRAM (32-bit RAM split between 4 SRAMs x 8-bit each).
        # -----------------------------------------------------

        # CPU SRAM Interface.
        sram0_addr  = Signal(13)
        sram0_rdata = Signal(32)
        sram0_wdata = Signal(32)
        sram0_cs    = Signal()
        sram0_wren  = Signal(4)
        self.cpu_params.update(
            i_SRAM0RDATA = sram0_rdata,
            o_SRAM0ADDR  = sram0_addr,
            o_SRAM0WREN  = sram0_wren,
            o_SRAM0WDATA = sram0_wdata,
            o_SRAM0CS    = sram0_cs,
        )

        # SRAMS Instances.
        for i in range(4):
            self.specials += Instance("SDPB",
                p_READ_MODE   = 0,
                p_BIT_WIDTH_0 = 8,
                p_BIT_WIDTH_1 = 8,
                p_RESET_MODE  = "SYNC",
                p_BLK_SEL_0   = Constant(0, 3),
                p_BLK_SEL_1   = Constant(0, 3),
                i_BLKSELA = 0b000,
                i_BLKSELB = 0b000,
                o_DO      = sram0_rdata[8*i:8*(i + 1)],
                i_DI      = sram0_wdata[8*i:8*(i + 1)],
                i_ADA     = Cat(Signal(3), sram0_addr),
                i_ADB     = Cat(Signal(3), sram0_addr),
                i_CEA     = sram0_cs &  sram0_wren[i],
                i_CEB     = sram0_cs,
                i_CLKA    = ClockSignal("sys"),
                i_CLKB    = ClockSignal("sys"),
                i_RESETA  = ~bus_reset_n,
                i_RESETB  = ~bus_reset_n,
                i_OCE     = 1,
            )

        # Flash (Boot Flash memory connected via AHB).
        # --------------------------------------------

        class AHBFlash(LiteXModule):
            def __init__(self, bus):
                addr = Signal(13)
                read = Signal()
                self.comb += bus.resp.eq(0)

                self.fsm = fsm = FSM()
                fsm.act("IDLE",
                    bus.readyout.eq(1),
                    If(bus.sel & bus.trans[1],
                       NextValue(addr, bus.addr[2:]),
                       NextState("READ"),
                    )
                )
                fsm.act("READ",
                    read.eq(1),
                    NextState("WAIT"),
                )
                fsm.act("WAIT",
                    NextState("IDLE")
                )
                self.specials += Instance("FLASH256K",
                    o_DOUT  = bus.rdata,
                    i_DIN   = Signal(32),
                    i_XADR  = addr[6:],
                    i_YADR  = addr[:6],
                    i_XE    = ~ResetSignal("sys"),
                    i_YE    = ~ResetSignal("sys"),
                    i_SE    = read,
                    i_PROG  = 0,
                    i_ERASE = 0,
                    i_NVSTR = 0
                )

        flash = ResetInserter()(AHBFlash(ahb_flash))
        self.comb += flash.reset.eq(~bus_reset_n)
        self.submodules += flash

        # Peripheral Bus (AHB -> Wishbone).
        # ---------------------------------
        self.submodules += ahb.AHB2Wishbone(ahb_targexp0, self.pbus)

    def connect_jtag(self, pads):
        self.cpu_params.update(
            i_DAPSWDITMS  = pads.tms,
            i_DAPTDI      = pads.tdi,
            o_DAPTDO      = pads.tdo,
            o_DAPNTDOEN   = Signal(),
            i_DAPNTRST    = ~self.reset,
            i_DAPSWCLKTCK = pads.tck,
            o_DAPJTAGNSW  = Signal(),  # Indicates debug mode, JTAG or SWD
        )

    def do_finalize(self):
        self.specials += Instance("EMCU", **self.cpu_params)
