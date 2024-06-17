#
# This file is part of LiteX.
#
# Copyright (c) 2024 Jiaxun Yang <jiaxun.yang@flygoat.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *
from litex.gen import *

from litex.soc.interconnect import axi
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_MIPS

class CDIM(CPU):
    category             = "softcore"
    family               = "mips"
    name                 = "cdim"
    human_name           = "CQU CDIM"
    variants             = ["standard"]
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_MIPS
    linker_output_format = "elf32-tradlittlemips"
    nop                  = "nop"
    io_regions           = {0x1000_0000: 0x0c00_0000} # Origin, Length.

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags = "-march=mips32 -mabi=32 -EL -msoft-float"
        flags += " -D__cdim__ "
        flags += " -DUART_POLLING"
        return flags

    # Memory Mapping.
    @property
    def mem_map(self):
        # Based on vanilla sysmap.h
        return {
            "main_ram" : 0x0000_0000,
            "csr"      : 0x1800_0000,
            "sram"     : 0x1c00_0000,
            "rom"      : 0x1fc0_0000,
        }

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.interrupt    = Signal(6)
        # Peripheral bus (Connected to main SoC's bus).
        axi_if = axi.AXIInterface(data_width=32, address_width=32, id_width=4)
        self.periph_buses = [axi_if]
        # Memory buses (Connected directly to LiteDRAM).
        self.memory_buses = []

        # CPU Instance.
        self.cpu_params = dict(
            # Clk / Rst
            i_aclk       = ClockSignal("sys"),
            i_aresetn       = ~ResetSignal("sys") & ~self.reset,

            # Interrupts
            i_ext_int= self.interrupt,

            # AXI interface
            o_arid          = axi_if.ar.id,
            o_araddr        = axi_if.ar.addr,
            o_arlen         = axi_if.ar.len,
            o_arsize        = axi_if.ar.size,
            o_arburst       = axi_if.ar.burst,
            o_arlock        = axi_if.ar.lock,
            o_arcache       = axi_if.ar.cache,
            o_arprot        = axi_if.ar.prot,
            o_arvalid       = axi_if.ar.valid,
            i_arready       = axi_if.ar.ready,

            i_rid           = axi_if.r.id,
            i_rdata         = axi_if.r.data,
            i_rresp         = axi_if.r.resp,
            i_rlast         = axi_if.r.last,
            i_rvalid        = axi_if.r.valid,
            o_rready        = axi_if.r.ready,

            o_awid          = axi_if.aw.id,
            o_awaddr        = axi_if.aw.addr,
            o_awlen         = axi_if.aw.len,
            o_awsize        = axi_if.aw.size,
            o_awburst       = axi_if.aw.burst,
            o_awlock        = axi_if.aw.lock,
            o_awcache       = axi_if.aw.cache,
            o_awprot        = axi_if.aw.prot,
            o_awvalid       = axi_if.aw.valid,
            i_awready       = axi_if.aw.ready,

            o_wid           = axi_if.w.id,
            o_wdata         = axi_if.w.data,
            o_wstrb         = axi_if.w.strb,
            o_wlast         = axi_if.w.last,
            o_wvalid        = axi_if.w.valid,
            i_wready        = axi_if.w.ready,

            i_bid           = axi_if.b.id,
            i_bresp         = axi_if.b.resp,
            i_bvalid        = axi_if.b.valid,
            o_bready        = axi_if.b.ready,
        )

        # Add sources
        basedir = os.path.join("CDIM", "mycpu")
        self.platform.add_source_dir(basedir)
        platform.add_verilog_include_path(basedir)

    def set_reset_address(self, reset_address):
        # Hardcoded reset address.
        assert reset_address == 0x1fc0_0000
        self.reset_address = reset_address

    def bios_map(self, addr, cached):
        # We can't access beyond KSEG0/1 in BIOS
        assert addr < 0x2000_0000
        if cached:
            return addr + 0x8000_0000
        else:
            return addr + 0xa000_0000

    def do_finalize(self):
        self.specials += Instance("mycpu_top", **self.cpu_params)
