#
# This file is part of LiteX.
#
# Copyright (c) 2021 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# Copyright (c) 2024 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.cores.cpu import CPU
from litex.soc.interconnect import wishbone, ahb

# Gowin EMCU ---------------------------------------------------------------------------------------

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
        self.interrupt     = Signal(5)
        self.pbus          = wishbone.Interface(data_width=32, adr_width=30, addressing="word")
        self.periph_buses  = [self.pbus]
        self.memory_buses  = []

        # CPU Instance.
        # -------------

        bus_reset_n = Signal()
        self.cpu_params = dict(
            # Clk/Rst.
            i_FCLK           = ClockSignal("sys"),
            i_PORESETN       = ~ (ResetSignal("sys") | self.reset),
            i_SYSRESETN      = ~ (ResetSignal("sys") | self.reset),
            i_MTXREMAP       = Signal(4, reset=0b1111),
            o_MTXHRESETN     = bus_reset_n,

            # RTC.
            i_RTCSRCCLK      = Signal(),  # TODO: RTC Clk In.

            # GPIOs.
            i_IOEXPINPUTI    = Signal(), # TODO: GPIO Input  (16-bit).
            o_IOEXPOUTPUTO   = Signal(), # TODO: GPIO Output (16-bit).
            o_IOEXPOUTPUTENO = Signal(), # TODO: GPIO Output Enable (16-bit).

            # Interrupts.
            i_GPINT          = self.interrupt,
            o_INTMONITOR     = Signal(),

            # Flash.
            i_FLASHERR       = Signal(),
            i_FLASHINT       = Signal(),
        )

        # SRAM (32-bit RAM split between 8 SRAMs x 4-bit each).
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
        for i in range(8):
            self.specials += Instance("SDPB",
                p_READ_MODE   = 0,
                p_BIT_WIDTH_0 = 4,
                p_BIT_WIDTH_1 = 4,
                p_RESET_MODE  = "SYNC",
                o_DO      = sram0_rdata[4*i:4*(i + 1)],
                i_DI      = sram0_wdata[4*i:4*(i + 1)],
                i_ADA     = Cat(Signal(2), sram0_addr),
                i_ADB     = Cat(Signal(2), sram0_addr),
                i_CEA     = sram0_cs &  sram0_wren[i//2],
                i_CEB     = sram0_cs & ~sram0_wren[i//2],
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

        ahb_flash = ahb.Interface()
        for s, _ in ahb_flash.master_signals:
            if s in ["wdata", "write", "mastlock", "prot"]:
                continue
            self.cpu_params[f"o_TARGFLASH0H{s.upper()}"] = getattr(ahb_flash, s)
        for s, _ in ahb_flash.slave_signals:
            self.cpu_params[f"i_TARGFLASH0H{s.upper()}"] = getattr(ahb_flash, s)
        flash = ResetInserter()(AHBFlash(ahb_flash))
        self.comb += flash.reset.eq(~bus_reset_n)
        self.submodules += flash


        # Peripheral Bus (AHB -> Wishbone).
        # ---------------------------------
        ahb_targexp0 = ahb.Interface()
        for s, _ in ahb_targexp0.master_signals:
            self.cpu_params[f"o_TARGEXP0H{s.upper()}"] = getattr(ahb_targexp0, s)
        for s, _ in ahb_targexp0.slave_signals:
            self.cpu_params[f"i_TARGEXP0H{s.upper()}"] = getattr(ahb_targexp0, s)
        self.submodules += ahb.AHB2Wishbone(ahb_targexp0, self.pbus)

    def connect_uart(self, pads, n=0):
        assert n in (0, 1), "this CPU has 2 built-in UARTs, 0 and 1"
        self.cpu_params.update({
            f"i_UART{n}RXDI"     : pads.rx,
            f"o_UART{n}TXDO"     : pads.tx,
            f"o_UART{n}BAUDTICK" : Signal()
        })

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
