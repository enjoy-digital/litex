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
        ibus              = axi.AXILiteInterface(data_width=32, address_width=32)
        dbus              = axi.AXILiteInterface(data_width=32, address_width=32)
        self.periph_buses = [ibus, dbus]
        self.memory_buses = []

        # Peripheral Bus AXI <-> AXILite conversion.
        ibus_axi = axi.AXIInterface(data_width=self.data_width, address_width=32)
        self.submodules += axi.AXI2AXILite(ibus_axi, ibus)
        dbus_axi = axi.AXIInterface(data_width=self.data_width, address_width=32)
        self.submodules += axi.AXI2AXILite(dbus_axi, dbus)

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
            o_AWVALIDC = ibus_axi.aw.valid,
            i_AWREADYC = ibus_axi.aw.ready,
            o_AWADDRC  = ibus_axi.aw.addr,
            o_AWBURSTC = ibus_axi.aw.burst,
            o_AWCACHEC = ibus_axi.aw.cache,
            o_AWLENC   = ibus_axi.aw.len,
            o_AWLOCKC  = ibus_axi.aw.lock,
            o_AWPROTC  = ibus_axi.aw.prot,
            o_AWSIZEC  = ibus_axi.aw.size,

            o_WVALIDC  = ibus_axi.w.valid,
            i_WREADYC  = ibus_axi.w.ready,
            o_WLASTC   = ibus_axi.w.last,
            o_WSTRBC   = ibus_axi.w.strb,
            o_HWDATAC  = ibus_axi.w.data,

            i_BVALIDC  = ibus_axi.b.valid,
            o_BREADYC  = ibus_axi.b.ready,
            i_BRESPC   = ibus_axi.b.resp,

            o_ARVALIDC = ibus_axi.ar.valid,
            i_ARREADYC = ibus_axi.ar.ready,
            o_ARADDRC  = ibus_axi.ar.addr,
            o_ARBURSTC = ibus_axi.ar.burst,
            o_ARCACHEC = ibus_axi.ar.cache,
            o_ARLENC   = ibus_axi.ar.len,
            o_ARLOCKC  = ibus_axi.ar.lock,
            o_ARPROTC  = ibus_axi.ar.prot,
            o_ARSIZEC  = ibus_axi.ar.size,

            i_RVALIDC  = ibus_axi.r.valid,
            o_RREADYC  = ibus_axi.r.ready,
            i_RLASTC   = ibus_axi.r.last,
            i_RRESPC   = ibus_axi.r.resp,
            i_HRDATAC  = ibus_axi.r.data,

            # Data Bus (AXI).
            o_AWVALIDS = dbus_axi.aw.valid,
            i_AWREADYS = dbus_axi.aw.ready,
            o_AWADDRS  = dbus_axi.aw.addr,
            o_AWBURSTS = dbus_axi.aw.burst,
            o_AWCACHES = dbus_axi.aw.cache,
            o_AWLENS   = dbus_axi.aw.len,
            o_AWLOCKS  = dbus_axi.aw.lock,
            o_AWPROTS  = dbus_axi.aw.prot,
            o_AWSIZES  = dbus_axi.aw.size,

            o_WVALIDS  = dbus_axi.w.valid,
            i_WREADYS  = dbus_axi.w.ready,
            o_WLASTS   = dbus_axi.w.last,
            o_WSTRBS   = dbus_axi.w.strb,
            o_HWDATAS  = dbus_axi.w.data,

            i_BVALIDS  = dbus_axi.b.valid,
            o_BREADYS  = dbus_axi.b.ready,
            i_BRESPS   = dbus_axi.b.resp,

            o_ARVALIDS = dbus_axi.ar.valid,
            i_ARREADYS = dbus_axi.ar.ready,
            o_ARADDRS  = dbus_axi.ar.addr,
            o_ARBURSTS = dbus_axi.ar.burst,
            o_ARCACHES = dbus_axi.ar.cache,
            o_ARLENS   = dbus_axi.ar.len,
            o_ARLOCKS  = dbus_axi.ar.lock,
            o_ARPROTS  = dbus_axi.ar.prot,
            o_ARSIZES  = dbus_axi.ar.size,

            i_RVALIDS  = dbus_axi.r.valid,
            o_RREADYS  = dbus_axi.r.ready,
            i_RLASTS   = dbus_axi.r.last,
            i_RRESPS   = dbus_axi.r.resp,
            i_HRDATAS  = dbus_axi.r.data,
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
