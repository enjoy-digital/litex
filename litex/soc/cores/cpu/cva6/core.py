#
# This file is part of LiteX.
#
# Copyright (c) 2021 Hensoldt Cyber GmbH <www.hensoldt-cyber.com>
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re

from migen import *

from litex.gen import *

from litex import get_data_mod
from litex.soc.interconnect import axi
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV64
from litex.build.xilinx import XilinxPlatform

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard", "standard32", "full"]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                       /-------- Base ISA
    #                       |/------- Hardware Multiply + Divide
    #                       ||/----- Atomics
    #                       |||/---- Compressed ISA
    #                       ||||/--- Single-Precision Floating-Point
    #                       |||||/-- Double-Precision Floating-Point
    #                       imacfd
    "standard"   : "-march=rv64i2p0_mac -mabi=lp64 ",
    "standard32" : "-march=rv32imac -mabi=ilp32 ",
    "full"       : "-march=rv64gc   -mabi=lp64 ",
}

# Helpers ------------------------------------------------------------------------------------------

def add_manifest_sources(platform, manifest):
    cva6_dir = get_data_mod("cpu", "cva6").data_location
    lx_core_dir = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(manifest), 'r') as f:
        for l in f:
            res = re.search('\$\{(CVA6_REPO_DIR|LX_CVA6_CORE_DIR)\}/(.+)', l)
            if res and not re.match('//', l):
                if res.group(1) == "LX_CVA6_CORE_DIR":
                    basedir = lx_core_dir
                else:
                    basedir = cva6_dir
                if re.match('\+incdir\+', l):
                    platform.add_verilog_include_path(os.path.join(basedir, res.group(2)))
                else:
                    filename = res.group(2)
                    if True: # TODO: other FPGAs
                        if filename.endswith("tc_sram_wrapper.sv"):
                            filename = filename.replace("tc_sram_wrapper.sv", "tc_sram_fpga_wrapper.sv")
                            platform.add_source(os.path.join(basedir, "common/local/techlib/fpga/rtl/SyncSpRamBeNx64.sv"))
                    platform.add_source(os.path.join(basedir, filename))

# CVA6 ---------------------------------------------------------------------------------------------

class CVA6(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "cva6"
    human_name           = "CVA6"
    variants             = CPU_VARIANTS
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV64
    nop                  = "nop"
    io_regions           = {0x8000_0000: 0x8000_0000} # Origin, Length.

    @property
    def linker_output_format(self):
        return f"elf{self.data_width}-littleriscv"

    @property
    def data_width(self):
        if self.variant == "standard32":
            return 32
        else:
            return 64


    # GCC Flags.
    @property
    def gcc_flags(self):
        flags = GCC_FLAGS[self.variant]
        flags += "-D__cva6__ "
        #flags += f" -DUART_POLLING"
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
        # Peripheral bus (Connected to main SoC's bus).
        axi_if = axi.AXIInterface(data_width=64, address_width=32, id_width=4)
        self.periph_buses = [axi_if]
        # Memory buses (Connected directly to LiteDRAM).
        self.memory_buses = []

        # # #

        # CPU Instance.
        self.cpu_params = dict(
            # Clk / Rst.
            i_clk_i       = ClockSignal("sys"),
            i_rst_n       = ~ResetSignal("sys") & ~self.reset,

            # Interrupts
            i_irq_sources = self.interrupt,

            # AXI interface.
            o_AWVALID_o   = axi_if.aw.valid,
            i_AWREADY_i   = axi_if.aw.ready,
            o_AWID_o      = axi_if.aw.id,
            o_AWADDR_o    = axi_if.aw.addr,
            o_AWLEN_o     = axi_if.aw.len,
            o_AWSIZE_o    = axi_if.aw.size,
            o_AWBURST_o   = axi_if.aw.burst,
            o_AWLOCK_o    = axi_if.aw.lock,
            o_AWCACHE_o   = axi_if.aw.cache,
            o_AWPROT_o    = axi_if.aw.prot,
            o_AWQOS_o     = axi_if.aw.qos,
            o_AWREGION_o  = Open(),
            o_AWUSER_o    = Open(),

            o_WVALID_o    = axi_if.w.valid,
            i_WREADY_i    = axi_if.w.ready,
            o_WDATA_o     = axi_if.w.data,
            o_WSTRB_o     = axi_if.w.strb,
            o_WLAST_o     = axi_if.w.last,
            o_WUSER_o     = Open(),

            i_BVALID_i    = axi_if.b.valid,
            o_BREADY_o    = axi_if.b.ready,
            i_BID_i       = axi_if.b.id,
            i_BRESP_i     = axi_if.b.resp,
            i_BUSER_i     = 0,

            o_ARVALID_o   = axi_if.ar.valid,
            i_ARREADY_i   = axi_if.ar.ready,
            o_ARID_o      = axi_if.ar.id,
            o_ARADDR_o    = axi_if.ar.addr,
            o_ARLEN_o     = axi_if.ar.len,
            o_ARSIZE_o    = axi_if.ar.size,
            o_ARBURST_o   = axi_if.ar.burst,
            o_ARLOCK_o    = axi_if.ar.lock,
            o_ARCACHE_o   = axi_if.ar.cache,
            o_ARPROT_o    = axi_if.ar.prot,
            o_ARQOS_o     = axi_if.ar.qos,
            o_ARUSER_o    = Open(),
            o_ARREGION_o  = Open(),

            i_RVALID_i    = axi_if.r.valid,
            o_RREADY_o    = axi_if.r.ready,
            i_RID_i       = axi_if.r.id,
            i_RDATA_i     = axi_if.r.data,
            i_RRESP_i     = axi_if.r.resp,
            i_RLAST_i     = axi_if.r.last,
            i_RUSER_i     = 0,
        )

        # Add Verilog sources.
        # Defines must come first
        wrapper_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), "cva6_wrapper")
        platform.add_source(os.path.join(wrapper_root, "cva6_defines.sv"))
        # TODO: use Flist.cv64a6_imafdc_sv39 and Flist.cv32a6_imac_sv0 instead
        if self.variant == "standard32":
            manifest = "Flist.cv32a6_imac_sv32"
        else:
            manifest = "Flist.cv64a6_imafdc_sv39"
        add_manifest_sources(platform, os.path.join(get_data_mod("cpu", "cva6").data_location,
            "core", manifest))
        # Add wrapper sources
        add_manifest_sources(platform, os.path.join(wrapper_root, "Flist.cva6_wrapper"))

    def add_jtag(self, pads):
        self.jtag_tck  = Signal()
        self.jtag_tms  = Signal()
        self.jtag_trst = Signal()
        self.jtag_tdi  = Signal()
        self.jtag_tdo  = Signal()

        tdo_oe = Signal()

        self.cpu_params.update(
            i_trst_n = self.jtag_trst,
            i_tck    = self.jtag_tck,
            i_tms    = self.jtag_tms,
            i_tdi    = self.jtag_tdi,
            o_tdo    = self.jtag_tdo,
        )

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        assert reset_address == 0x1000_0000, "cpu_reset_addr hardcoded in during elaboration!"

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        if "i_trst_n" not in self.cpu_params:
            self.cpu_params["i_trst_n"] = 1
        self.specials += Instance("cva6_wrapper", **self.cpu_params)
