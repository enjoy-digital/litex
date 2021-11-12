#
# This file is part of LiteX.
#
# Copyright (c) 2021 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.soc.interconnect import wishbone

from litex.soc.cores.cpu import CPU

# EOS-S3 -------------------------------------------------------------------------------------------

class EOS_S3(CPU):
    variants             = ["standard"]
    family               = "arm"
    name                 = "eos-s3"
    human_name           = "eos-s3"
    data_width           = 32
    endianness           = "little"
    reset_address        = 0x00000000
    gcc_triple           = "gcc-arm-none-eabi"
    linker_output_format = "elf32-littlearm"
    nop                  = "nop"
    io_regions           = {0x00000000: 0x100000000} # Origin, Length.

    # Memory Mapping.
    @property
    def mem_map(self):
        return {"csr": 0x00000000}

    def __init__(self, platform, variant):
        self.platform       = platform
        self.reset          = Signal()
        self.interrupt      = Signal(4)
        self.periph_buses   = [] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses   = [] # Memory buses (Connected directly to LiteDRAM).

        self.wishbone_master = [] # General Purpose Wishbone Masters.

        # # #
        self.wb             = wishbone.Interface(data_width=32, adr_width=17)

        # EOS-S3 Clocking.
        self.clock_domains.cd_Sys_Clk0 = ClockDomain()
        self.clock_domains.cd_Sys_Clk1 = ClockDomain()

        # EOS-S3 (Minimal) -------------------------------------------------------------------------
        Sys_Clk0_Rst       = Signal()
        Sys_Clk1_Rst       = Signal()
        WB_RST             = Signal()

        self.cpu_params = dict(
            # AHB-To-FPGA Bridge
            i_WB_CLK       = ClockSignal("Sys_Clk0"),
            o_WB_RST       = WB_RST,
            o_WBs_ADR      = self.wb.adr,
            o_WBs_CYC      = self.wb.cyc,
            o_WBs_BYTE_STB = self.wb.sel,
            o_WBs_WE       = self.wb.we,
            o_WBs_STB      = self.wb.stb,
            #o_WBs_RD"(),   =           // output        | Read  Enable               to   FPGA
            o_WBs_WR_DAT   = self.wb.dat_w,
            i_WBs_RD_DAT   = self.wb.dat_r,
            i_WBs_ACK      = self.wb.ack,
            # SDMA Signals
            #SDMA_Req(4'b0000),
            #SDMA_Sreq(4'b0000),
            #SDMA_Done(),
            #SDMA_Active(),
            # FB Interrupts
            i_FB_msg_out     = self.interrupt,
            #FB_Int_Clr(8'h0),
            #FB_Start(),
            #FB_Busy= 0,
            # FB Clocks
            o_Sys_Clk0     = ClockSignal("Sys_Clk0"),
            o_Sys_Clk0_Rst = Sys_Clk0_Rst,
            o_Sys_Clk1     = ClockSignal("Sys_Clk1"),
            o_Sys_Clk1_Rst = Sys_Clk1_Rst,
            # Packet FIFO
            #Sys_PKfb_Clk = 0,
            #Sys_PKfb_Rst(),
            #FB_PKfbData(32'h0),
            #FB_PKfbPush(4'h0),
            #FB_PKfbSOF = 0,
            #FB_PKfbEOF = 0,
            #FB_PKfbOverflow(),
            # Sensor Interface
            #Sensor_Int(),
            #TimeStamp(),
            # SPI Master APB Bus
            #Sys_Pclk(),
            #Sys_Pclk_Rst(),
            #Sys_PSel = 0,
            #SPIm_Paddr(16'h0),
            #SPIm_PEnable = 0,
            #SPIm_PWrite = 0,
            #SPIm_PWdata(32'h0),
            #SPIm_Prdata(),
            #SPIm_PReady(),
            #SPIm_PSlvErr(),
            # Misc
            i_Device_ID = 0xCAFE,
            # FBIO Signals
            #FBIO_In(),
            #FBIO_In_En(),
            #FBIO_Out(),
            #FBIO_Out_En(),
            # ???
            #SFBIO           =  ,
            i_Device_ID_6S    = 0,
            i_Device_ID_4S    = 0,
            i_SPIm_PWdata_26S = 0,
            i_SPIm_PWdata_24S = 0,
            i_SPIm_PWdata_14S = 0,
            i_SPIm_PWdata_11S = 0,
            i_SPIm_PWdata_0S  = 0,
            i_SPIm_Paddr_8S   = 0,
            i_SPIm_Paddr_6S   = 0,
            i_FB_PKfbPush_1S  = 0,
            i_FB_PKfbData_31S = 0,
            i_FB_PKfbData_21S = 0,
            i_FB_PKfbData_19S = 0,
            i_FB_PKfbData_9S  = 0,
            i_FB_PKfbData_6S  = 0,
            i_Sys_PKfb_ClkS   = 0,
            i_FB_BusyS        = 0,
            i_WB_CLKS         = 0,

        )

        self.specials += Instance("gclkbuff",
            i_A = Sys_Clk0_Rst | WB_RST,
            o_Z = self.cd_Sys_Clk0.rst)

    def do_finalize(self):
        self.specials += Instance("qlal4s3b_cell_macro", **self.cpu_params)
