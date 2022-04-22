#
# This file is part of LiteX.
#
# Copyright (c) 2022 Ilia Sergachev <ilia@sergachev.ch>
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.soc.cores.cpu import CPU
from litex.soc.interconnect import axi

class Open(Signal): pass

# Cortex-M1 ----------------------------------------------------------------------------------------

class CortexM1(CPU):
    variants             = ["standard"]
    category             = "softcore"
    family               = "arm"
    name                 = "cortex_m1"
    human_name           = "ARM Cortex-M1"
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
        flags =  f" -march=armv6-m -mthumb -mfloat-abi=soft"
        flags += f" -D__CortexM1__"
        flags += f" -DUART_POLLING"
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.reset        = Signal()
        self.interrupt    = Signal(2)
        pbus              = axi.AXILiteInterface(data_width=32, address_width=32)
        self.periph_buses = [pbus]
        self.memory_buses = []

        # Peripheral Bus AXI <-> AXILite conversion.
        pbus_axi = axi.AXIInterface(data_width=self.data_width, address_width=32)
        self.submodules += axi.AXI2AXILite(pbus_axi, pbus)

        # CPU Instance.
        self.cpu_params = dict(
            # Clk/Rst.
            i_HCLK      = ClockSignal("sys"),
            i_SYSRESETn = ~(ResetSignal() | self.reset),

            # Control/Status.
            o_LOCKUP      = Open(),
            o_HALTED      = Open(),
            o_SYSRESETREQ = Open(),
            i_NMI         = 0,
            i_EDBGRQ      = 0,

            # Embedded ROM/SRAM.
            p_ITCM_SIZE = 0,  # Use LiteX's ROM.
            p_DTCM_SIZE = 0,  # Use LiteX's SRAM.
            i_CFGITCMEN = 0,  # 1 = alias ITCM at 0x0

            # Interrupts.
            p_NUM_IRQ = len(self.interrupt),
            i_IRQ     = self.interrupt,

            # Debug.
            p_SMALL_DEBUG  = True,
            i_DBGRESTART   = 0,
            i_DBGRESETn    = ~(ResetSignal() | self.reset),
            p_DEBUG_SEL    = 1, # JTAG
            o_DBGRESTARTED = Open(),

            # Peripheral Bus (AXI).
            o_AWVALID = pbus_axi.aw.valid,
            i_AWREADY = pbus_axi.aw.ready,
            o_AWADDR  = pbus_axi.aw.addr,
            o_AWBURST = pbus_axi.aw.burst,
            o_AWCACHE = pbus_axi.aw.cache,
            o_AWLEN   = pbus_axi.aw.len,
            o_AWLOCK  = pbus_axi.aw.lock,
            o_AWPROT  = pbus_axi.aw.prot,
            o_AWSIZE  = pbus_axi.aw.size,

            o_WVALID  = pbus_axi.w.valid,
            i_WREADY  = pbus_axi.w.ready,
            o_WLAST   = pbus_axi.w.last,
            o_WSTRB   = pbus_axi.w.strb,
            o_HWDATA  = pbus_axi.w.data,

            i_BVALID  = pbus_axi.b.valid,
            o_BREADY  = pbus_axi.b.ready,
            i_BRESP   = pbus_axi.b.resp,

            o_ARVALID = pbus_axi.ar.valid,
            i_ARREADY = pbus_axi.ar.ready,
            o_ARADDR  = pbus_axi.ar.addr,
            o_ARBURST = pbus_axi.ar.burst,
            o_ARCACHE = pbus_axi.ar.cache,
            o_ARLEN   = pbus_axi.ar.len,
            o_ARLOCK  = pbus_axi.ar.lock,
            o_ARPROT  = pbus_axi.ar.prot,
            o_ARSIZE  = pbus_axi.ar.size,

            i_RVALID  = pbus_axi.r.valid,
            o_RREADY  = pbus_axi.r.ready,
            i_RLAST   = pbus_axi.r.last,
            i_RRESP   = pbus_axi.r.resp,
            i_HRDATA  = pbus_axi.r.data,
        )
        platform.add_source_dir("AT472-BU-98000-r0p1-00rel0/vivado/Arm_ipi_repository/CM1DbgAXI/logical/rtl")

    def add_jtag(self, pads):
        self.cpu_params.update(
            i_SWDITMS  = pads.tms,
            i_TDI      = pads.tdi,
            o_TDO      = pads.tdo,
            o_nTDOEN   = Open(),
            i_nTRST    = pads.ntrst,
            i_SWCLKTCK = pads.tck,
            o_JTAGNSW  = Open(),  # Indicates debug mode, JTAG or SWD
            o_JTAGTOP  = Open(),  # ?
            o_SWDO     = Open(),  # TODO
            o_SWDOEN   = Open(),  # TODO
        )

    def do_finalize(self):
        self.specials += Instance("CortexM1DbgAXI", **self.cpu_params)
