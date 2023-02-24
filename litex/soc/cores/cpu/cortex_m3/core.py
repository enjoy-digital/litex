#
# This file is part of LiteX.
#
# Copyright (c) 2022 Ilia Sergachev <ilia@sergachev.ch>
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex.soc.cores.cpu import CPU
from litex.soc.interconnect import axi

# Cortex-M3 ----------------------------------------------------------------------------------------

class CortexM3(CPU):
    variants             = ["standard"]
    category             = "softcore"
    family               = "arm"
    name                 = "cortex_m3"
    human_name           = "ARM Cortex-M3"
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
        self.platform     = platform
        self.reset        = Signal()
        self.interrupt    = Signal(2)
        ibus              = axi.AXIInterface(data_width=32, address_width=32)
        dbus              = axi.AXIInterface(data_width=32, address_width=32)
        self.periph_buses = [ibus, dbus]
        self.memory_buses = []

        # CPU Instance.
        self.cpu_params = dict(
            # Clk/Rst.
            i_HCLK      = ClockSignal("sys"),
            i_SYSRESETn = ~(ResetSignal() | self.reset),

            # Control/Status.
            p_MPU_PRESENT = 0,
            p_TRACE_LVL   = 0,
            p_DEBUG_LVL   = 2,

            # Interrupts.
            p_NUM_IRQ = len(self.interrupt),
            i_IRQ     = self.interrupt,

            # Embedded ROM/SRAM.
            p_ITCM_SIZE = 0,  # Use LiteX's ROM.
            p_DTCM_SIZE = 0,  # Use LiteX's RAM.
            i_CFGITCMEN = 0,  # 1 = alias ITCM at 0x0

            # Debug.
            i_DBGRESETn = ~(ResetSignal() | self.reset),

            # Instruction Bus (AXI).
            o_AWVALIDC = ibus.aw.valid,
            i_AWREADYC = ibus.aw.ready,
            o_AWADDRC  = ibus.aw.addr,
            o_AWBURSTC = ibus.aw.burst,
            o_AWCACHEC = ibus.aw.cache,
            o_AWLENC   = ibus.aw.len,
            o_AWLOCKC  = ibus.aw.lock,
            o_AWPROTC  = ibus.aw.prot,
            o_AWSIZEC  = ibus.aw.size,

            o_WVALIDC  = ibus.w.valid,
            i_WREADYC  = ibus.w.ready,
            o_WLASTC   = ibus.w.last,
            o_WSTRBC   = ibus.w.strb,
            o_HWDATAC  = ibus.w.data,

            i_BVALIDC  = ibus.b.valid,
            o_BREADYC  = ibus.b.ready,
            i_BRESPC   = ibus.b.resp,

            o_ARVALIDC = ibus.ar.valid,
            i_ARREADYC = ibus.ar.ready,
            o_ARADDRC  = ibus.ar.addr,
            o_ARBURSTC = ibus.ar.burst,
            o_ARCACHEC = ibus.ar.cache,
            o_ARLENC   = ibus.ar.len,
            o_ARLOCKC  = ibus.ar.lock,
            o_ARPROTC  = ibus.ar.prot,
            o_ARSIZEC  = ibus.ar.size,

            i_RVALIDC  = ibus.r.valid,
            o_RREADYC  = ibus.r.ready,
            i_RLASTC   = ibus.r.last,
            i_RRESPC   = ibus.r.resp,
            i_HRDATAC  = ibus.r.data,

            # Data Bus (AXI).
            o_AWVALIDS = dbus.aw.valid,
            i_AWREADYS = dbus.aw.ready,
            o_AWADDRS  = dbus.aw.addr,
            o_AWBURSTS = dbus.aw.burst,
            o_AWCACHES = dbus.aw.cache,
            o_AWLENS   = dbus.aw.len,
            o_AWLOCKS  = dbus.aw.lock,
            o_AWPROTS  = dbus.aw.prot,
            o_AWSIZES  = dbus.aw.size,

            o_WVALIDS  = dbus.w.valid,
            i_WREADYS  = dbus.w.ready,
            o_WLASTS   = dbus.w.last,
            o_WSTRBS   = dbus.w.strb,
            o_HWDATAS  = dbus.w.data,

            i_BVALIDS  = dbus.b.valid,
            o_BREADYS  = dbus.b.ready,
            i_BRESPS   = dbus.b.resp,

            o_ARVALIDS = dbus.ar.valid,
            i_ARREADYS = dbus.ar.ready,
            o_ARADDRS  = dbus.ar.addr,
            o_ARBURSTS = dbus.ar.burst,
            o_ARCACHES = dbus.ar.cache,
            o_ARLENS   = dbus.ar.len,
            o_ARLOCKS  = dbus.ar.lock,
            o_ARPROTS  = dbus.ar.prot,
            o_ARSIZES  = dbus.ar.size,

            i_RVALIDS  = dbus.r.valid,
            o_RREADYS  = dbus.r.ready,
            i_RLASTS   = dbus.r.last,
            i_RRESPS   = dbus.r.resp,
            i_HRDATAS  = dbus.r.data,
        )
        platform.add_source_dir("AT426-BU-98000-r0p1-00rel0/vivado/Arm_ipi_repository/CM3DbgAXI/rtl")

    def add_jtag(self, pads):
        self.cpu_params.update(
            p_JTAG_PRESENT = 1,
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
        self.specials += Instance("CortexM3DbgAXI", **self.cpu_params)
