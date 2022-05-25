#
# This file is part of LiteX.
#
# Copyright (c) 2021 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.interconnect import wishbone, ahb
from litex.soc.cores.cpu import CPU

# AHB Flash ----------------------------------------------------------------------------------------

class AHBFlash(Module):
    def __init__(self, bus):
        addr = Signal(13)
        read = Signal()
        self.comb += bus.resp.eq(0)

        self.submodules.fsm = fsm = FSM()
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

# Gowin EMCU ---------------------------------------------------------------------------------------

class GowinEMCU(CPU):
    variants             = ["standard"]
    category             = "hardcore"
    family               = "arm"
    name                 = "gowin_emcu"
    human_name           = "Gowin EMCU"
    data_width           = 32
    endianness           = "little"
    gcc_triple           = "arm-none-eabi"
    gcc_flags            = "-mcpu=cortex-m3 -mthumb"
    linker_output_format = "elf32-littlearm"
    nop                  = "nop"
    io_regions           = {
        # Origin, Length.
        0x4000_0000: 0x2000_0000,
        0xA000_0000: 0x6000_0000
    }

    @property
    def mem_map(self):
        return {
            "rom"         : 0x0000_0000,
            "sram"        : 0x2000_0000,
            "peripherals" : 0x4000_0000,
            "csr"         : 0xa000_0000,
        }

    def __init__(self, platform, variant, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.reset     = Signal()
        self.bus_reset = Signal()
        bus_reset_n = Signal()
        self.comb += self.bus_reset.eq(~bus_reset_n)
        self.interrupt     = Signal(5)
        self.reset_address = self.mem_map["rom"] + 0

        self.gpio_in     = Signal(16)
        self.gpio_out    = Signal(16)
        self.gpio_out_en = Signal(16)

        self.cpu_params = dict()
        self.cpu_params.update(
            i_MTXREMAP       = Signal(4, reset=0b1111),
            o_MTXHRESETN     = bus_reset_n,

            i_FLASHERR       = Signal(),
            i_FLASHINT       = Signal(),

            i_FCLK           = ClockSignal("sys"),
            i_PORESETN       = ~self.reset,
            i_SYSRESETN      = ~self.reset,
            i_RTCSRCCLK      = Signal(),  # TODO - RTC clk in

            i_IOEXPINPUTI    = self.gpio_in,
            o_IOEXPOUTPUTO   = self.gpio_out,
            o_IOEXPOUTPUTENO = self.gpio_out_en,

            i_GPINT          = self.interrupt,
            o_INTMONITOR     = Signal(),
        )

        # 32b CPU SRAM split between 8 SRAMs x 4 bit each

        sram_dw        = 32
        single_sram_dw = 4
        n_srams = sram_dw // single_sram_dw

        sram0_addr  = Signal(13)
        sram0_rdata = Signal(sram_dw)
        sram0_wdata = Signal(sram_dw)
        sram0_cs    = Signal()
        sram0_wren  = Signal(4)
        self.cpu_params.update(
            i_SRAM0RDATA = sram0_rdata,
            o_SRAM0ADDR  = sram0_addr,
            o_SRAM0WREN  = sram0_wren,
            o_SRAM0WDATA = sram0_wdata,
            o_SRAM0CS    = sram0_cs,
        )

        for i in range(n_srams):
            self.specials += Instance("SDPB",
                p_READ_MODE   = 0,
                p_BIT_WIDTH_0 = single_sram_dw,
                p_BIT_WIDTH_1 = single_sram_dw,
                p_RESET_MODE  = "SYNC",
                p_BLK_SEL_0   = 0b111,
                p_BLK_SEL_1   = 0b111,
                o_DO      = Cat(sram0_rdata[i * single_sram_dw: (i + 1) * single_sram_dw], Signal(sram_dw - single_sram_dw)),
                i_DI      = Cat(sram0_wdata[i * single_sram_dw: (i + 1) * single_sram_dw], Signal(sram_dw - single_sram_dw)),
                i_ADA     = Cat(Signal(2), sram0_addr[:-1]),
                i_ADB     = Cat(Signal(2), sram0_addr[:-1]),
                i_CEA     = sram0_wren[i // 2],
                i_CEB     = ~sram0_wren[i // 2],
                i_CLKA    = ClockSignal(),
                i_CLKB    = ClockSignal(),
                i_RESETA  = 0,
                i_RESETB  = self.bus_reset,
                i_OCE     = 1,
                i_BLKSELA = Cat(sram0_cs, sram0_cs, sram0_cs),
                i_BLKSELB = Cat(sram0_cs, sram0_cs, sram0_cs),
            )

        # Boot Flash memory connected via AHB

        ahb_flash = ahb.Interface()
        for s, _ in ahb_flash.master_signals:
            if s in ["wdata", "write", "mastlock", "prot"]:
                continue
            self.cpu_params[f"o_TARGFLASH0H{s.upper()}"] = getattr(ahb_flash, s)
        for s, _ in ahb_flash.slave_signals:
            self.cpu_params[f"i_TARGFLASH0H{s.upper()}"] = getattr(ahb_flash, s)
        flash = ResetInserter()(AHBFlash(ahb_flash))
        self.comb += flash.reset.eq(self.bus_reset)
        self.submodules += flash

        # Extension AHB -> Wishbone CSR via bridge

        self.pbus = wishbone.Interface(data_width=32, adr_width=30)
        self.periph_buses = [self.pbus]
        ahb_targexp0 = ahb.Interface()
        for s, _ in ahb_targexp0.master_signals:
            self.cpu_params[f"o_TARGEXP0H{s.upper()}"] = getattr(ahb_targexp0, s)
        for s, _ in ahb_targexp0.slave_signals:
            self.cpu_params[f"i_TARGEXP0H{s.upper()}"] = getattr(ahb_targexp0, s)
        self.submodules += ahb.AHB2Wishbone(ahb_targexp0, self.pbus)

    def connect_uart(self, pads, n=0):
        assert n in (0, 1), "this CPU has 2 built-in UARTs, 0 and 1"
        self.cpu_params.update({
            f"i_UART{n}RXDI": pads.rx,
            f"o_UART{n}TXDO": pads.tx,
            f"o_UART{n}BAUDTICK": Signal()
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
