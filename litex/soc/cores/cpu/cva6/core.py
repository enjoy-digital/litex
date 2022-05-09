#
# This file is part of LiteX.
#
# Copyright (c) 2021 Hensoldt Cyber GmbH <www.hensoldt-cyber.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re

from migen import *
from migen.fhdl.specials import Tristate

from litex import get_data_mod
from litex.soc.interconnect import axi
from litex.soc.interconnect import wishbone, stream
from litex.soc.interconnect.csr import *
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV64

class Open(Signal): pass

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard", "full"]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                       /-------- Base ISA
    #                       |/------- Hardware Multiply + Divide
    #                       ||/----- Atomics
    #                       |||/---- Compressed ISA
    #                       ||||/--- Single-Precision Floating-Point
    #                       |||||/-- Double-Precision Floating-Point
    #                       imacfd
    "standard": "-march=rv64imac    -mabi=lp64 ",
    "full":     "-march=rv64gc   -mabi=lp64 ",
}

# Helpers ------------------------------------------------------------------------------------------

def add_manifest_sources(platform, manifest):
    # TODO: create a pythondata-cpu-cva6 package to be installed with litex, then use this generic comment
    basedir = get_data_mod("cpu", "cva6").data_location
    with open(os.path.join(basedir, manifest), 'r') as f:
        for l in f:
            res = re.search('\$\{CVA6_REPO_DIR\}/(.+)', l)
            if res and not re.match('//', l):
                if re.match('\+incdir\+', l):
                    platform.add_verilog_include_path(os.path.join(basedir, res.group(1)))
                else:
                    platform.add_source(os.path.join(basedir, res.group(1)))

# CVA6 -----------------------------------------------------------------------------------------

class CVA6(CPU):
    family               = "riscv"
    name                 = "cva6"
    human_name           = "CVA6"
    variants             = CPU_VARIANTS
    data_width           = 64
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV64
    linker_output_format = "elf64-littleriscv"
    nop                  = "nop"
    io_regions           = {0x80000000: 0x80000000} # Origin, Length.

    has_fpu              = ["full"]

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags = GCC_FLAGS[self.variant]
        flags += "-D__cva6__ "
        return flags

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "rom"      : 0x10000000,
            "sram"     : 0x20000000,
            "csr"      : 0x80000000
        }

    jtag_layout = [
        ("tck",  1),
        ("tms",  1),
        ("trst", 1),
        ("tdi",  1),
        ("tdo",  1),
    ]

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant

        data_width = 64
        self.axi_if = axi_if = axi.AXIInterface(data_width=data_width,  address_width=data_width, id_width=4)
        
        wb_if = wishbone.Interface(data_width=data_width, adr_width=data_width-log2_int(data_width//8))
        a2w = axi.AXI2Wishbone(axi_if, wb_if, base_address=0x00000000)
        self.submodules += a2w

        self.memory_buses = [] 
        self.periph_buses = [wb_if]

        self.interrupt    = Signal(32)
        self.reset        = Signal()

        tdo_i  = Signal()
        tdo_o  = Signal()
        tdo_oe = Signal()

        pads = Record(self.jtag_layout)
        self.pads = pads
        self.specials += Tristate(pads.tdo, tdo_o, tdo_oe, tdo_i)

        self.cpu_params = dict(
            # Clk / Rst.
            i_clk_i              = ClockSignal("sys"),
            i_rst_n             = ~ResetSignal("sys"),

            # Interrupts
            i_irq_sources = self.interrupt,

            # AXI interface
            o_AWID_o     = axi_if.aw.id,
            o_AWADDR_o   = axi_if.aw.addr,          
            o_AWLEN_o    = axi_if.aw.len, 
            o_AWSIZE_o   = axi_if.aw.size,
            o_AWBURST_o  = axi_if.aw.burst,
            o_AWLOCK_o   = axi_if.aw.lock,
            o_AWCACHE_o  = axi_if.aw.cache,
            o_AWPROT_o   = axi_if.aw.prot,
            o_AWQOS_o    = axi_if.aw.qos,
            o_AWREGION_o = Open(),
            o_AWUSER_o   = Open(),
            o_AWVALID_o  = axi_if.aw.valid,
            o_WDATA_o    = axi_if.w.data, 
            o_WSTRB_o    = axi_if.w.strb, 
            o_WLAST_o    = axi_if.w.last, 
            o_WUSER_o    = Open(), 
            o_WVALID_o   = axi_if.w.valid,
            o_BREADY_o   = axi_if.b.ready,
            o_ARID_o     = axi_if.ar.id,
            o_ARADDR_o   = axi_if.ar.addr,
            o_ARLEN_o    = axi_if.ar.len,
            o_ARSIZE_o   = axi_if.ar.size,
            o_ARBURST_o  = axi_if.ar.burst,
            o_ARLOCK_o   = axi_if.ar.lock,
            o_ARCACHE_o  = axi_if.ar.cache,
            o_ARPROT_o   = axi_if.ar.prot,
            o_ARQOS_o    = axi_if.ar.qos, 
            o_ARUSER_o   = Open(),
            o_ARREGION_o = Open(),
            o_ARVALID_o  = axi_if.ar.valid,
            o_RREADY_o   = axi_if.r.ready,

            i_AWREADY_i  = axi_if.aw.ready,
            i_ARREADY_i  = axi_if.ar.ready,
            i_WREADY_i   = axi_if.w.ready,
            i_BVALID_i   = axi_if.b.valid,
            i_BID_i      = axi_if.b.id,
            i_BRESP_i    = axi_if.b.resp,
            i_BUSER_i    = 0,
            i_RVALID_i   = axi_if.r.valid,
            i_RID_i      = axi_if.r.id,
            i_RDATA_i    = axi_if.r.data,
            i_RRESP_i    = axi_if.r.resp,
            i_RLAST_i    = axi_if.r.last,
            i_RUSER_i    = 0,

            # JTAG.
            i_trst_n    = pads.trst,
            i_tck       = pads.tck,
            i_tms       = pads.tms,
            i_tdi       = pads.tdi,
            o_tdo       = tdo_o,
            o_tdo_oe    = tdo_oe,

            # TODO: add trace interface
        )

        # Add Verilog sources.
        # TODO: use Flist.cv64a6_imafdc_sv39 and Flist.cv32a6_imac_sv0 instead
        add_manifest_sources(platform, 'Flist.cv64a6_imafdc_sv39')
        add_manifest_sources(platform, 'Flist.cva6_wrapper')

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        assert reset_address == 0x10000000, "cpu_reset_addr hardcoded in during elaboration!"

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("cva6_wrapper", **self.cpu_params)
