#
# This file is part of LiteX.
#
# Copyright (c) 2022 Icenowy Zheng <uwu@icenowy.me>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re

from migen import *

from litex import get_data_mod
from litex.soc.interconnect import axi
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV64

# Helpers ------------------------------------------------------------------------------------------

def add_manifest_sources(platform, manifest):
    basedir = os.path.join(os.environ["OPENC906_DIR"], "C906_RTL_FACTORY")
    with open(os.path.join(basedir, manifest), 'r') as f:
        for l in f:
            res = re.search('\$\{CODE_BASE_PATH\}/(.+)', l)
            if res and not re.match('//', l):
                if re.match('\+incdir\+', l):
                    platform.add_verilog_include_path(os.path.join(basedir, res.group(1)))
                else:
                    platform.add_source(os.path.join(basedir, res.group(1)))

# OpenC906 -----------------------------------------------------------------------------------------

class OpenC906(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "openc906"
    human_name           = "OpenC906"
    variants             = ["standard"]
    data_width           = 64
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV64
    linker_output_format = "elf64-littleriscv"
    nop                  = "nop"
    io_regions           = {0xa000_0000: 0x2000_0000} # Origin, Length.

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  "-mno-save-restore "
        flags += "-march=rv64gc -mabi=lp64d "
        flags += "-D__openc906__ "
        flags += "-mcmodel=medany"
        return flags

    # Memory Mapping.
    @property
    def mem_map(self):
        # Based on vanilla sysmap.h
        return {
            "main_ram":       0x0000_0000, # Region 0, Cacheable, Bufferable
            "rom":            0x8000_0000, # Region 0 too
            "sram":           0x8800_0000, # Region 0 too
            # "internal_apb":   0x9000_0000, Region 1, Strong Order, Non-cacheable, Non-bufferable
            "csr":            0xa000_0000, # Region 1 too
        }

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.interrupt    = Signal(240)
        self.axi_if       = axi.AXIInterface(data_width=64, address_width=40)
        self.periph_buses = [self.axi_lite_if] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []                 # Memory buses (Connected directly to LiteDRAM).

        # # #

        # Cycle count
        cycle_count = Signal(64)
        self.sync += cycle_count.eq(cycle_count + 1)

        # CPU Instance.
        self.cpu_params = dict(
            # Clk / Rst.
            i_pll_core_cpuclk  = ClockSignal("sys"),
            i_pad_cpu_rst_b    = ~ResetSignal("sys") | self.reset,
            i_axim_clk_en      = 1,

            # Debug (ignored).
            i_sys_apb_clk      = 0,
            i_sys_apb_rst_b    = 0,

            # Interrupts.
            i_pad_cpu_apb_base = Signal(40, reset=0x9000_0000),
            i_pad_plic_int_cfg = 0,
            i_pad_plic_int_vld = self.interrupt,

            # Integrated timer.
            i_pad_cpu_sys_cnt  = cycle_count,

            # AXI.
            o_biu_pad_awvalid  = self.axi_if.aw.valid,
            i_pad_biu_awready  = self.axi_if.aw.ready,
            o_biu_pad_awid     = self.axi_if.aw.id,
            o_biu_pad_awaddr   = self.axi_if.aw.addr,
            o_biu_pad_awlen    = self.axi_if.aw.len,
            o_biu_pad_awsize   = self.axi_if.aw.size,
            o_biu_pad_awburst  = self.axi_if.aw.burst,
            o_biu_pad_awlock   = self.axi_if.aw.lock,
            o_biu_pad_awcache  = self.axi_if.aw.cache,
            o_biu_pad_awprot   = self.axi_if.aw.prot,

            o_biu_pad_wvalid   = self.axi_if.w.valid,
            i_pad_biu_wready   = self.axi_if.w.ready,
            o_biu_pad_wdata    = self.axi_if.w.data,
            o_biu_pad_wstrb    = self.axi_if.w.strb,
            o_biu_pad_wlast    = self.axi_if.w.last,

            i_pad_biu_bvalid   = self.axi_if.b.valid,
            o_biu_pad_bready   = self.axi_if.b.ready,
            i_pad_biu_bid      = self.axi_if.b.id,
            i_pad_biu_bresp    = self.axi_if.b.resp,

            o_biu_pad_arvalid  = self.axi_if.ar.valid,
            i_pad_biu_arready  = self.axi_if.ar.ready,
            o_biu_pad_arid     = self.axi_if.ar.id,
            o_biu_pad_araddr   = self.axi_if.ar.addr,
            o_biu_pad_arlen    = self.axi_if.ar.len,
            o_biu_pad_arsize   = self.axi_if.ar.size,
            o_biu_pad_arburst  = self.axi_if.ar.burst,
            o_biu_pad_arlock   = self.axi_if.ar.lock,
            o_biu_pad_arcache  = self.axi_if.ar.cache,
            o_biu_pad_arprot   = self.axi_if.ar.prot,

            i_pad_biu_rvalid   = self.axi_if.r.valid,
            o_biu_pad_rready   = self.axi_if.r.ready,
            i_pad_biu_rid      = self.axi_if.r.id,
            i_pad_biu_rdata    = self.axi_if.r.data,
            i_pad_biu_rresp    = self.axi_if.r.resp,
            i_pad_biu_rlast    = self.axi_if.r.last,
        )

        # Add Verilog sources.
        add_manifest_sources(platform, "gen_rtl/filelists/C906_asic_rtl.fl")
        from litex.build.xilinx import XilinxPlatform
        if isinstance(platform, XilinxPlatform):
            # Import a filelist for Xilinx FPGAs
            add_manifest_sources(platform, "gen_rtl/filelists/xilinx_fpga.fl")
        else:
            # Import a filelist for generic platforms
            add_manifest_sources(platform, "gen_rtl/filelists/generic_fpga.fl")

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(i_pad_cpu_rvba=Signal(40, reset=reset_address))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("openC906", **self.cpu_params)
