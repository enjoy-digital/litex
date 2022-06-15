#
# This file is part of LiteX.
#
# Copyright (c) 2021 Hensoldt Cyber GmbH <www.hensoldt-cyber.com>
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re

from migen import *

from litex import get_data_mod
from litex.soc.interconnect import axi
from litex.soc.interconnect import wishbone
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
    "standard": "-march=rv64imac -mabi=lp64 ",
    "full":     "-march=rv64gc   -mabi=lp64 ",
}

# Helpers ------------------------------------------------------------------------------------------

def add_manifest_sources(platform, manifest):
    basedir = get_data_mod("cpu", "cva6").data_location
    with open(os.path.join(basedir, manifest), 'r') as f:
        for l in f:
            res = re.search('\$\{CVA6_REPO_DIR\}/(.+)', l)
            if res and not re.match('//', l):
                if re.match('\+incdir\+', l):
                    platform.add_verilog_include_path(os.path.join(basedir, res.group(1)))
                else:
                    platform.add_source(os.path.join(basedir, res.group(1)))

# CVA6 ---------------------------------------------------------------------------------------------

class CVA6(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "cva6"
    human_name           = "CVA6"
    variants             = CPU_VARIANTS
    data_width           = 64
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV64
    linker_output_format = "elf64-littleriscv"
    nop                  = "nop"
    io_regions           = {0x8000_0000: 0x8000_0000} # Origin, Length.

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags = GCC_FLAGS[self.variant]
        flags += "-D__cva6__ "
        flags += f" -DUART_POLLING"
        return flags

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "rom"  : 0x1000_0000,
            "sram" : 0x2000_0000,
            "csr"  : 0x8000_0000,
        }

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.interrupt    = Signal(32)
        self.axi_if       = axi.AXIInterface(data_width=64, address_width=32, id_width=4)
        self.periph_buses = [self.axi_if] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []            # Memory buses (Connected directly to LiteDRAM).

        # # #

        # CPU Instance.
        self.cpu_params = dict(
            # Clk / Rst.
            i_clk_i       = ClockSignal("sys"),
            i_rst_n       = ~ResetSignal("sys") | self.reset,

            # AXI interface.
            o_AWVALID_o   = self.axi_if.aw.valid,
            i_AWREADY_i   = self.axi_if.aw.ready,
            o_AWID_o      = self.axi_if.aw.id,
            o_AWADDR_o    = self.axi_if.aw.addr,
            o_AWLEN_o     = self.axi_if.aw.len,
            o_AWSIZE_o    = self.axi_if.aw.size,
            o_AWBURST_o   = self.axi_if.aw.burst,
            o_AWLOCK_o    = self.axi_if.aw.lock,
            o_AWCACHE_o   = self.axi_if.aw.cache,
            o_AWPROT_o    = self.axi_if.aw.prot,
            o_AWQOS_o     = self.axi_if.aw.qos,
            o_AWREGION_o  = Open(),
            o_AWUSER_o    = Open(),

            o_WVALID_o    = self.axi_if.w.valid,
            i_WREADY_i    = self.axi_if.w.ready,
            o_WDATA_o     = self.axi_if.w.data,
            o_WSTRB_o     = self.axi_if.w.strb,
            o_WLAST_o     = self.axi_if.w.last,
            o_WUSER_o     = Open(),

            i_BVALID_i    = self.axi_if.b.valid,
            o_BREADY_o    = self.axi_if.b.ready,
            i_BID_i       = self.axi_if.b.id,
            i_BRESP_i     = self.axi_if.b.resp,
            i_BUSER_i     = 0,

            o_ARVALID_o   = self.axi_if.ar.valid,
            i_ARREADY_i   = self.axi_if.ar.ready,
            o_ARID_o      = self.axi_if.ar.id,
            o_ARADDR_o    = self.axi_if.ar.addr,
            o_ARLEN_o     = self.axi_if.ar.len,
            o_ARSIZE_o    = self.axi_if.ar.size,
            o_ARBURST_o   = self.axi_if.ar.burst,
            o_ARLOCK_o    = self.axi_if.ar.lock,
            o_ARCACHE_o   = self.axi_if.ar.cache,
            o_ARPROT_o    = self.axi_if.ar.prot,
            o_ARQOS_o     = self.axi_if.ar.qos,
            o_ARUSER_o    = Open(),
            o_ARREGION_o  = Open(),

            i_RVALID_i    = self.axi_if.r.valid,
            o_RREADY_o    = self.axi_if.r.ready,
            i_RID_i       = self.axi_if.r.id,
            i_RDATA_i     = self.axi_if.r.data,
            i_RRESP_i     = self.axi_if.r.resp,
            i_RLAST_i     = self.axi_if.r.last,
            i_RUSER_i     = 0,
        )

        # Add Verilog sources.
        # TODO: use Flist.cv64a6_imafdc_sv39 and Flist.cv32a6_imac_sv0 instead
        add_manifest_sources(platform, "Flist.cv64a6_imafdc_sv39")
        add_manifest_sources(platform, "Flist.cva6_wrapper")

    def add_jtag(pads):
        from migen.fhdl.specials import Tristate
        self.jtag_tck  = Signal()
        self.jtag_tms  = Signal()
        self.jtag_trst = Signal()
        self.jtag_tdi  = Signal()
        self.jtag_tdo  = Signal()

        tdo_o  = Signal()
        tdo_oe = Signal()
        self.specials += Tristate(self.jtag_tdo, tdo_o, tdo_oe)

        self.cpu_params.update(
            i_trst_n = self.jtag_trst,
            i_tck    = self.jtag_tck,
            i_tms    = self.jtag_tms,
            i_tdi    = self.jtag_tdi,
            o_tdo    = tdo_o,
            o_tdo_oe = tdo_oe,
        )

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        assert reset_address == 0x1000_0000, "cpu_reset_addr hardcoded in during elaboration!"

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("cva6_wrapper", **self.cpu_params)
