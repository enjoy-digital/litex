# litex/soc/cores/cpu/rocket/core.py
# Rocket Chip core support for the LiteX SoC.
#
# Author: Gabriel L. Somlo <somlo@cmu.edu>
# Copyright (c) 2019, Carnegie Mellon University
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os

from migen import *

from litex import get_data_mod
from litex.soc.interconnect import axi
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV64


CPU_VARIANTS = {
    "standard": "freechips.rocketchip.system.LitexConfig",
    "linux":    "freechips.rocketchip.system.LitexLinuxConfig",
    "linuxd":   "freechips.rocketchip.system.LitexLinuxDConfig",
    "linuxq":   "freechips.rocketchip.system.LitexLinuxQConfig",
    "full":     "freechips.rocketchip.system.LitexFullConfig",
}

GCC_FLAGS = {
    "standard": "-march=rv64imac   -mabi=lp64 ",
    "linux":    "-march=rv64imac   -mabi=lp64 ",
    "linuxd":   "-march=rv64imac   -mabi=lp64 ",
    "linuxq":   "-march=rv64imac   -mabi=lp64 ",
    "full":     "-march=rv64imafdc -mabi=lp64 ",
}

AXI_DATA_WIDTHS = {
    # variant : (mem, mmio)
    "standard": ( 64,  64),
    "linux":    ( 64,  64),
    "linuxd":   (128,  64),
    "linuxq":   (256,  64),
    "full":     ( 64,  64),
}

class RocketRV64(CPU):
    name                 = "rocket"
    human_name           = "RocketRV64[imac]"
    variants             = CPU_VARIANTS
    data_width           = 64
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV64
    linker_output_format = "elf64-littleriscv"
    nop                  = "nop"
    io_regions           = {0x10000000: 0x70000000} # origin, length

    @property
    def mem_map(self):
        # Rocket reserves the first 256Mbytes for internal use, so we must change default mem_map.
        return {
            "rom"      : 0x10000000,
            "sram"     : 0x11000000,
            "csr"      : 0x12000000,
            "ethmac"   : 0x30000000,
            "main_ram" : 0x80000000,
        }

    @property
    def gcc_flags(self):
        flags =  "-mno-save-restore "
        flags += GCC_FLAGS[self.variant]
        flags += "-D__rocket__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform  = platform
        self.variant   = variant

        self.reset     = Signal()
        self.interrupt = Signal(4)

        mem_dw, mmio_dw = AXI_DATA_WIDTHS[self.variant]

        self.mem_axi   =  mem_axi = axi.AXIInterface(data_width=mem_dw,  address_width=32, id_width=4)
        self.mmio_axi  = mmio_axi = axi.AXIInterface(data_width=mmio_dw, address_width=32, id_width=4)
        self.l2fb_axi  = l2fb_axi = axi.AXIInterface(data_width=mmio_dw, address_width=32, id_width=4)

        self.mmio_wb   = mmio_wb = wishbone.Interface(data_width=mmio_dw, adr_width=32-log2_int(mmio_dw//8))
        self.l2fb_wb   = l2fb_wb = wishbone.Interface(data_width=mmio_dw, adr_width=32-log2_int(mmio_dw//8))

        self.memory_buses = [mem_axi]
        self.periph_buses = [mmio_wb]
        self.dma_bus      =  l2fb_wb

        # # #

        self.cpu_params = dict(
            # clock, reset
            i_clock=ClockSignal(),
            i_reset=ResetSignal() | self.reset,

            # debug (ignored)
            #i_resetctrl_hartIsInReset_0           = 0,
            i_debug_clock                          = 0,
            i_debug_reset                          = 0,
            #o_debug_clockeddmi_dmi_req_ready      = ,
            i_debug_clockeddmi_dmi_req_valid       = 0,
            i_debug_clockeddmi_dmi_req_bits_addr   = 0,
            i_debug_clockeddmi_dmi_req_bits_data   = 0,
            i_debug_clockeddmi_dmi_req_bits_op     = 0,
            i_debug_clockeddmi_dmi_resp_ready      = 0,
            #o_debug_clockeddmi_dmi_resp_valid     = ,
            #o_debug_clockeddmi_dmi_resp_bits_data = ,
            #o_debug_clockeddmi_dmi_resp_bits_resp = ,
            i_debug_clockeddmi_dmiClock            = 0,
            i_debug_clockeddmi_dmiReset            = 0,
            #o_debug_ndreset                       = ,
            #o_debug_dmactive                      = ,
            i_debug_dmactiveAck                    = 0,

            # irq
            i_interrupts=self.interrupt,

            # axi memory (L1-cached)
            i_mem_axi4_0_aw_ready      = mem_axi.aw.ready,
            o_mem_axi4_0_aw_valid      = mem_axi.aw.valid,
            o_mem_axi4_0_aw_bits_id    = mem_axi.aw.id,
            o_mem_axi4_0_aw_bits_addr  = mem_axi.aw.addr,
            o_mem_axi4_0_aw_bits_len   = mem_axi.aw.len,
            o_mem_axi4_0_aw_bits_size  = mem_axi.aw.size,
            o_mem_axi4_0_aw_bits_burst = mem_axi.aw.burst,
            o_mem_axi4_0_aw_bits_lock  = mem_axi.aw.lock,
            o_mem_axi4_0_aw_bits_cache = mem_axi.aw.cache,
            o_mem_axi4_0_aw_bits_prot  = mem_axi.aw.prot,
            o_mem_axi4_0_aw_bits_qos   = mem_axi.aw.qos,

            i_mem_axi4_0_w_ready       = mem_axi.w.ready,
            o_mem_axi4_0_w_valid       = mem_axi.w.valid,
            o_mem_axi4_0_w_bits_data   = mem_axi.w.data,
            o_mem_axi4_0_w_bits_strb   = mem_axi.w.strb,
            o_mem_axi4_0_w_bits_last   = mem_axi.w.last,

            o_mem_axi4_0_b_ready       = mem_axi.b.ready,
            i_mem_axi4_0_b_valid       = mem_axi.b.valid,
            i_mem_axi4_0_b_bits_id     = mem_axi.b.id,
            i_mem_axi4_0_b_bits_resp   = mem_axi.b.resp,

            i_mem_axi4_0_ar_ready      = mem_axi.ar.ready,
            o_mem_axi4_0_ar_valid      = mem_axi.ar.valid,
            o_mem_axi4_0_ar_bits_id    = mem_axi.ar.id,
            o_mem_axi4_0_ar_bits_addr  = mem_axi.ar.addr,
            o_mem_axi4_0_ar_bits_len   = mem_axi.ar.len,
            o_mem_axi4_0_ar_bits_size  = mem_axi.ar.size,
            o_mem_axi4_0_ar_bits_burst = mem_axi.ar.burst,
            o_mem_axi4_0_ar_bits_lock  = mem_axi.ar.lock,
            o_mem_axi4_0_ar_bits_cache = mem_axi.ar.cache,
            o_mem_axi4_0_ar_bits_prot  = mem_axi.ar.prot,
            o_mem_axi4_0_ar_bits_qos   = mem_axi.ar.qos,

            o_mem_axi4_0_r_ready       = mem_axi.r.ready,
            i_mem_axi4_0_r_valid       = mem_axi.r.valid,
            i_mem_axi4_0_r_bits_id     = mem_axi.r.id,
            i_mem_axi4_0_r_bits_data   = mem_axi.r.data,
            i_mem_axi4_0_r_bits_resp   = mem_axi.r.resp,
            i_mem_axi4_0_r_bits_last   = mem_axi.r.last,

            # axi mmio (not cached)
            i_mmio_axi4_0_aw_ready      = mmio_axi.aw.ready,
            o_mmio_axi4_0_aw_valid      = mmio_axi.aw.valid,
            o_mmio_axi4_0_aw_bits_id    = mmio_axi.aw.id,
            o_mmio_axi4_0_aw_bits_addr  = mmio_axi.aw.addr,
            o_mmio_axi4_0_aw_bits_len   = mmio_axi.aw.len,
            o_mmio_axi4_0_aw_bits_size  = mmio_axi.aw.size,
            o_mmio_axi4_0_aw_bits_burst = mmio_axi.aw.burst,
            o_mmio_axi4_0_aw_bits_lock  = mmio_axi.aw.lock,
            o_mmio_axi4_0_aw_bits_cache = mmio_axi.aw.cache,
            o_mmio_axi4_0_aw_bits_prot  = mmio_axi.aw.prot,
            o_mmio_axi4_0_aw_bits_qos   = mmio_axi.aw.qos,

            i_mmio_axi4_0_w_ready       = mmio_axi.w.ready,
            o_mmio_axi4_0_w_valid       = mmio_axi.w.valid,
            o_mmio_axi4_0_w_bits_data   = mmio_axi.w.data,
            o_mmio_axi4_0_w_bits_strb   = mmio_axi.w.strb,
            o_mmio_axi4_0_w_bits_last   = mmio_axi.w.last,

            o_mmio_axi4_0_b_ready       = mmio_axi.b.ready,
            i_mmio_axi4_0_b_valid       = mmio_axi.b.valid,
            i_mmio_axi4_0_b_bits_id     = mmio_axi.b.id,
            i_mmio_axi4_0_b_bits_resp   = mmio_axi.b.resp,

            i_mmio_axi4_0_ar_ready      = mmio_axi.ar.ready,
            o_mmio_axi4_0_ar_valid      = mmio_axi.ar.valid,
            o_mmio_axi4_0_ar_bits_id    = mmio_axi.ar.id,
            o_mmio_axi4_0_ar_bits_addr  = mmio_axi.ar.addr,
            o_mmio_axi4_0_ar_bits_len   = mmio_axi.ar.len,
            o_mmio_axi4_0_ar_bits_size  = mmio_axi.ar.size,
            o_mmio_axi4_0_ar_bits_burst = mmio_axi.ar.burst,
            o_mmio_axi4_0_ar_bits_lock  = mmio_axi.ar.lock,
            o_mmio_axi4_0_ar_bits_cache = mmio_axi.ar.cache,
            o_mmio_axi4_0_ar_bits_prot  = mmio_axi.ar.prot,
            o_mmio_axi4_0_ar_bits_qos   = mmio_axi.ar.qos,

            o_mmio_axi4_0_r_ready       = mmio_axi.r.ready,
            i_mmio_axi4_0_r_valid       = mmio_axi.r.valid,
            i_mmio_axi4_0_r_bits_id     = mmio_axi.r.id,
            i_mmio_axi4_0_r_bits_data   = mmio_axi.r.data,
            i_mmio_axi4_0_r_bits_resp   = mmio_axi.r.resp,
            i_mmio_axi4_0_r_bits_last   = mmio_axi.r.last,

            # axi l2fb (slave, for e.g., DMA)
            o_l2_frontend_bus_axi4_0_aw_ready      = l2fb_axi.aw.ready,
            i_l2_frontend_bus_axi4_0_aw_valid      = l2fb_axi.aw.valid,
            i_l2_frontend_bus_axi4_0_aw_bits_id    = l2fb_axi.aw.id,
            i_l2_frontend_bus_axi4_0_aw_bits_addr  = l2fb_axi.aw.addr,
            i_l2_frontend_bus_axi4_0_aw_bits_len   = l2fb_axi.aw.len,
            i_l2_frontend_bus_axi4_0_aw_bits_size  = l2fb_axi.aw.size,
            i_l2_frontend_bus_axi4_0_aw_bits_burst = l2fb_axi.aw.burst,
            i_l2_frontend_bus_axi4_0_aw_bits_lock  = l2fb_axi.aw.lock,
            i_l2_frontend_bus_axi4_0_aw_bits_cache = l2fb_axi.aw.cache,
            i_l2_frontend_bus_axi4_0_aw_bits_prot  = l2fb_axi.aw.prot,
            i_l2_frontend_bus_axi4_0_aw_bits_qos   = l2fb_axi.aw.qos,

            o_l2_frontend_bus_axi4_0_w_ready       = l2fb_axi.w.ready,
            i_l2_frontend_bus_axi4_0_w_valid       = l2fb_axi.w.valid,
            i_l2_frontend_bus_axi4_0_w_bits_data   = l2fb_axi.w.data,
            i_l2_frontend_bus_axi4_0_w_bits_strb   = l2fb_axi.w.strb,
            i_l2_frontend_bus_axi4_0_w_bits_last   = l2fb_axi.w.last,

            i_l2_frontend_bus_axi4_0_b_ready       = l2fb_axi.b.ready,
            o_l2_frontend_bus_axi4_0_b_valid       = l2fb_axi.b.valid,
            o_l2_frontend_bus_axi4_0_b_bits_id     = l2fb_axi.b.id,
            o_l2_frontend_bus_axi4_0_b_bits_resp   = l2fb_axi.b.resp,

            o_l2_frontend_bus_axi4_0_ar_ready      = l2fb_axi.ar.ready,
            i_l2_frontend_bus_axi4_0_ar_valid      = l2fb_axi.ar.valid,
            i_l2_frontend_bus_axi4_0_ar_bits_id    = l2fb_axi.ar.id,
            i_l2_frontend_bus_axi4_0_ar_bits_addr  = l2fb_axi.ar.addr,
            i_l2_frontend_bus_axi4_0_ar_bits_len   = l2fb_axi.ar.len,
            i_l2_frontend_bus_axi4_0_ar_bits_size  = l2fb_axi.ar.size,
            i_l2_frontend_bus_axi4_0_ar_bits_burst = l2fb_axi.ar.burst,
            i_l2_frontend_bus_axi4_0_ar_bits_lock  = l2fb_axi.ar.lock,
            i_l2_frontend_bus_axi4_0_ar_bits_cache = l2fb_axi.ar.cache,
            i_l2_frontend_bus_axi4_0_ar_bits_prot  = l2fb_axi.ar.prot,
            i_l2_frontend_bus_axi4_0_ar_bits_qos   = l2fb_axi.ar.qos,

            i_l2_frontend_bus_axi4_0_r_ready       = l2fb_axi.r.ready,
            o_l2_frontend_bus_axi4_0_r_valid       = l2fb_axi.r.valid,
            o_l2_frontend_bus_axi4_0_r_bits_id     = l2fb_axi.r.id,
            o_l2_frontend_bus_axi4_0_r_bits_data   = l2fb_axi.r.data,
            o_l2_frontend_bus_axi4_0_r_bits_resp   = l2fb_axi.r.resp,
            o_l2_frontend_bus_axi4_0_r_bits_last   = l2fb_axi.r.last,
        )

        # adapt axi interfaces to wishbone
        # NOTE: AXI2Wishbone FSMs must be reset with the CPU!
        mmio_a2w = ResetInserter()(axi.AXI2Wishbone(mmio_axi, mmio_wb, base_address=0))
        self.comb += mmio_a2w.reset.eq(ResetSignal() | self.reset)
        self.submodules += mmio_a2w

        l2fb_a2w = ResetInserter()(axi.Wishbone2AXI(l2fb_wb, l2fb_axi, base_address=0))
        self.comb += l2fb_a2w.reset.eq(ResetSignal() | self.reset)
        self.submodules += l2fb_a2w

        # add verilog sources
        self.add_sources(platform, variant)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        assert reset_address == 0x10000000, "cpu_reset_addr hardcoded in during elaboration!"

    @staticmethod
    def add_sources(platform, variant="standard"):
        vdir = get_data_mod("cpu", "rocket").data_location
        platform.add_sources(
            os.path.join(vdir, "generated-src"),
            CPU_VARIANTS[variant] + ".v",
            CPU_VARIANTS[variant] + ".behav_srams.v",
        )
        platform.add_sources(
            os.path.join(vdir, "vsrc"),
            "plusarg_reader.v",
            "AsyncResetReg.v",
            "EICG_wrapper.v",
        )

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("ExampleRocketSystem", **self.cpu_params)
