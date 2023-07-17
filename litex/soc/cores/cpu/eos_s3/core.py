#
# This file is part of LiteX.
#
# Copyright (c) 2021 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *

from litex.soc.interconnect import wishbone

from litex.soc.cores.cpu import CPU

# EOS-S3 -------------------------------------------------------------------------------------------

class EOS_S3(CPU):
    variants             = ["standard"]
    category             = "hardcore"
    family               = "arm"
    name                 = "eos_s3"
    human_name           = "EOS S3"
    data_width           = 32
    endianness           = "little"
    reset_address        = 0x0000_0000
    gcc_triple           = "arm-none-eabi"
    gcc_flags            = "-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16"
    linker_output_format = "elf32-littlearm"
    nop                  = "nop"
    io_regions           = {0x4000_0000: 0xc000_0000}  # Origin, Length.
    csr_decode           = False # Wishbone address is decoded before fabric.

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "rom":  0x0000_0000,
            "sram": 0x2000_0000,
            "csr":  0x4002_0000
        }

    def __init__(self, platform, variant, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.platform       = platform
        self.reset          = Signal()
        self.interrupt      = Signal(4)
        self.pbus           = wishbone.Interface(data_width=32, adr_width=15)
        self.periph_buses   = [self.pbus]
        self.memory_buses   = []

        # # #

        # EOS-S3 Clocking --------------------------------------------------------------------------
        pbus_rst     = Signal()
        eos_s3_0_clk = Signal()
        eos_s3_0_rst = Signal()
        eos_s3_1_clk = Signal()
        eos_s3_1_rst = Signal()
        self.cd_eos_s3_0 = ClockDomain()
        self.cd_eos_s3_1 = ClockDomain()
        self.specials += Instance("gclkbuff",
            i_A = eos_s3_0_clk,
            o_Z = ClockSignal("eos_s3_0")
        )
        self.specials += Instance("gclkbuff",
            i_A = eos_s3_0_rst | pbus_rst,
            o_Z = ResetSignal("eos_s3_0")
        )
        self.specials += Instance("gclkbuff",
            i_A = eos_s3_1_clk,
            o_Z = ClockSignal("eos_s3_1")
        )
        self.specials += Instance("gclkbuff",
            i_A = eos_s3_1_rst | pbus_rst,
            o_Z = ResetSignal("eos_s3_1")
        )

        # EOS-S3 Instance --------------------------------------------------------------------------
        self.cpu_params = dict(
            # Wishbone Master.
            # -----------
            i_WB_CLK       = ClockSignal("eos_s3_0"),
            o_WB_RST       = pbus_rst,
            o_WBs_ADR      = Cat(Signal(2), self.pbus.adr),
            o_WBs_CYC      = self.pbus.cyc,
            o_WBs_BYTE_STB = self.pbus.sel,
            o_WBs_WE       = self.pbus.we,
            o_WBs_STB      = self.pbus.stb,
            o_WBs_RD       = Open(), # Read Enable.
            o_WBs_WR_DAT   = self.pbus.dat_w,
            i_WBs_RD_DAT   = self.pbus.dat_r,
            i_WBs_ACK      = self.pbus.ack,

            # SDMA.
            # -----
            i_SDMA_Req    = Signal(4),
            i_SDMA_Sreq   = Signal(4),
            o_SDMA_Done   = Open(),
            o_SDMA_Active = Open(),

            # Interrupts.
            # -----------
            i_FB_msg_out = self.interrupt,
            i_FB_Int_Clr = Signal(8),
            o_FB_Start   = Open(),
            i_FB_Busy    = 0,

            # Clocking.
            # ---------
            o_Sys_Clk0     = eos_s3_0_clk,
            o_Sys_Clk0_Rst = eos_s3_0_rst,
            o_Sys_Clk1     = eos_s3_1_clk,
            o_Sys_Clk1_Rst = eos_s3_1_rst,

            # Packet FIFO.
            # ------------
            i_Sys_PKfb_Clk    = 0,
            o_Sys_PKfb_Rst    = Open(),
            i_FB_PKfbData     = Signal(32),
            i_FB_PKfbPush     = Signal(4),
            i_FB_PKfbSOF      = 0,
            i_FB_PKfbEOF      = 0,
            o_FB_PKfbOverflow = Open(),

            # Sensor.
            # -------
            o_Sensor_Int = Open(),
            o_TimeStamp  = Open(),

            # SPI Master (APB).
            # -----------------
            o_Sys_Pclk     = Open(),
            o_Sys_Pclk_Rst = Open(),
            i_Sys_PSel     = 0,
            i_SPIm_Paddr   = Signal(16),
            i_SPIm_PEnable = 0,
            i_SPIm_PWrite  = 0,
            i_SPIm_PWdata  = Signal(32),
            o_SPIm_Prdata  = Open(),
            o_SPIm_PReady  = Open(),
            o_SPIm_PSlvErr = Open(),

            # Misc.
            # -----
            i_Device_ID = 0xCAFE,
            # FBIO Signals
            o_FBIO_In         = Open(),
            o_FBIO_In_En      = Open(),
            o_FBIO_Out        = Open(),
            o_FBIO_Out_En     = Open(),
            # ???
            io_SFBIO          = Signal(14),
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
            i_WB_CLKS         = 0
        )

    def do_finalize(self):
        self.specials += Instance("qlal4s3b_cell_macro", **self.cpu_params)
