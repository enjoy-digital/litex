#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess

from migen import *

from litex import get_data_mod

from litex.gen import *

from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32
from litex.soc.integration.soc import SoCRegion, auto_int
from litex.soc.interconnect import axi

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard"]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                       /------------ Base ISA
    #                       |    /------- Hardware Multiply + Divide
    #                       |    |/----- Atomics
    #                       |    ||/---- Compressed ISA
    #                       |    |||/--- Single-Precision Floating-Point
    #                       |    ||||/-- Double-Precision Floating-Point
    #                       i    macfd
    "standard": "-march=rv32i2p0_mc   -mabi=ilp32",
}

# RTL Sources --------------------------------------------------------------------------------------

CPU_SOURCES = [
    "design/lib/beh_lib.sv",
    "design/mem.sv",
    "design/pic_ctrl.sv",
    "design/dma_ctrl.sv",
    "design/ifu/ifu_aln_ctl.sv",
    "design/ifu/ifu_compress_ctl.sv",
    "design/ifu/ifu_ifc_ctl.sv",
    "design/ifu/ifu_bp_ctl.sv",
    "design/ifu/ifu_ic_mem.sv",
    "design/ifu/ifu_mem_ctl.sv",
    "design/ifu/ifu_iccm_mem.sv",
    "design/ifu/ifu.sv",
    "design/dec/dec_decode_ctl.sv",
    "design/dec/dec_gpr_ctl.sv",
    "design/dec/dec_ib_ctl.sv",
    "design/dec/dec_tlu_ctl.sv",
    "design/dec/dec_trigger.sv",
    "design/dec/dec.sv",
    "design/exu/exu_alu_ctl.sv",
    "design/exu/exu_mul_ctl.sv",
    "design/exu/exu_div_ctl.sv",
    "design/exu/exu.sv",
    "design/lsu/lsu.sv",
    "design/lsu/lsu_bus_buffer.sv",
    "design/lsu/lsu_clkdomain.sv",
    "design/lsu/lsu_addrcheck.sv",
    "design/lsu/lsu_lsc_ctl.sv",
    "design/lsu/lsu_stbuf.sv",
    "design/lsu/lsu_bus_intf.sv",
    "design/lsu/lsu_ecc.sv",
    "design/lsu/lsu_dccm_mem.sv",
    "design/lsu/lsu_dccm_ctl.sv",
    "design/lsu/lsu_trigger.sv",
    "design/dbg/dbg.sv",
    "design/lib/mem_lib.sv",
    "design/lib/ahb_to_axi4.sv",
    "design/lib/axi4_to_ahb.sv",
    "design/veer.sv",
]

JTAG_SOURCES = [
    "design/dmi/dmi_wrapper.v",
    "design/dmi/dmi_jtag_to_core_sync.v",
    "design/dmi/rvjtag_tap.sv",
    "design/veer_wrapper.sv",
]

# VeeREH1 -----------------------------------------------------------------------------------------

class VeeREH1(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "veer_eh1"
    human_name           = "VeeREH1"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x8000_0000: 0x8000_0000} # Origin, Length.

    # Default parameters.
    dmi_enable        = 0 # 0: JTAG pins, 1: DMI register port.
    iccm_enable       = 1
    dccm_enable       = 1
    icache_enable     = 1
    ret_stack_size    = 4
    btb_size          = 32
    bht_size          = 128
    dccm_size         = 128 # KiB.
    dccm_num_banks    = 4
    iccm_size         = 128 # KiB.
    iccm_num_banks    = 4
    icache_size       = 64  # KiB.
    icache_ecc        = 0
    pic_2cycle        = 1
    pic_region        = 0xF
    pic_offset        = 0xC_0000
    pic_size          = 32 # KiB.
    pic_total_int     = 8
    fpga_optimize     = 1
    lsu_stbuf_depth   = 8
    dma_buf_depth     = 4
    lsu_num_nbload    = 8
    dec_instbuf_depth = 4

    # Command line configuration arguments.
    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group(title="CPU options")
        cpu_group.add_argument("--veer-dmi-enable",       default=VeeREH1.dmi_enable,       type=int, choices=[0, 1], help="Expose the DMI register port instead of JTAG pins.")
        cpu_group.add_argument("--veer-iccm-enable",      default=VeeREH1.iccm_enable,      type=int, choices=[0, 1], help="Enable the Instruction Closely Coupled Memory.")
        cpu_group.add_argument("--veer-dccm-enable",      default=VeeREH1.dccm_enable,      type=int, choices=[0, 1], help="Enable the Data Closely Coupled Memory.")
        cpu_group.add_argument("--veer-icache-enable",    default=VeeREH1.icache_enable,    type=int, choices=[0, 1], help="Enable the instruction cache.")
        cpu_group.add_argument("--veer-ret-stack-size",   default=VeeREH1.ret_stack_size,   type=int, choices=range(2, 9), help="Return stack size.")
        cpu_group.add_argument("--veer-btb-size",         default=VeeREH1.btb_size,         type=int, choices=[32, 48, 64, 128, 256, 512], help="Branch target buffer size.")
        cpu_group.add_argument("--veer-bht-size",         default=VeeREH1.bht_size,         type=int, choices=[32, 64, 128, 256, 512, 1024, 2048], help="Branch history table size.")
        cpu_group.add_argument("--veer-dccm-size",        default=VeeREH1.dccm_size,        type=int, choices=[4, 8, 16, 32, 48, 64, 128, 256, 512], help="DCCM size in KiB.")
        cpu_group.add_argument("--veer-dccm-num-banks",   default=VeeREH1.dccm_num_banks,   type=int, choices=[4, 8, 16], help="Number of DCCM banks.")
        cpu_group.add_argument("--veer-iccm-size",        default=VeeREH1.iccm_size,        type=int, choices=[4, 8, 16, 32, 64, 128, 256, 512], help="ICCM size in KiB.")
        cpu_group.add_argument("--veer-iccm-num-banks",   default=VeeREH1.iccm_num_banks,   type=int, choices=[4, 8, 16], help="Number of ICCM banks.")
        cpu_group.add_argument("--veer-icache-size",      default=VeeREH1.icache_size,      type=int, choices=[16, 32, 64, 128, 256], help="Instruction cache size in KiB.")
        cpu_group.add_argument("--veer-icache-ecc",       default=VeeREH1.icache_ecc,       type=int, choices=[0, 1], help="Use ECC instead of parity in the instruction cache.")
        cpu_group.add_argument("--veer-pic-2cycle",       default=VeeREH1.pic_2cycle,       type=int, choices=[0, 1], help="Enable the two-cycle PIC implementation.")
        cpu_group.add_argument("--veer-pic-region",       default=VeeREH1.pic_region,       type=auto_int, choices=range(16), help="PIC 256MiB region number.")
        cpu_group.add_argument("--veer-pic-offset",       default=VeeREH1.pic_offset,       type=auto_int, help="PIC offset within its 256MiB region.")
        cpu_group.add_argument("--veer-pic-size",         default=VeeREH1.pic_size,         type=int, choices=[32, 64, 128, 256], help="PIC size in KiB.")
        cpu_group.add_argument("--veer-pic-total-int",    default=VeeREH1.pic_total_int,    type=int, help="Number of PIC interrupt sources (1-32).")
        cpu_group.add_argument("--veer-fpga-optimize",    default=VeeREH1.fpga_optimize,    type=int, choices=[0, 1], help="Remove clock gating for FPGA implementation.")
        cpu_group.add_argument("--veer-lsu-stbuf-depth",  default=VeeREH1.lsu_stbuf_depth,  type=int, choices=[2, 4, 8], help="LSU store buffer depth.")
        cpu_group.add_argument("--veer-dma-buf-depth",    default=VeeREH1.dma_buf_depth,    type=int, choices=[2, 4], help="DMA buffer depth.")
        cpu_group.add_argument("--veer-lsu-num-nbload",   default=VeeREH1.lsu_num_nbload,   type=int, choices=[2, 4, 8], help="Number of LSU non-blocking loads.")
        cpu_group.add_argument("--veer-dec-instbuf-depth", default=VeeREH1.dec_instbuf_depth, type=int, choices=[2, 4], help="Decode instruction buffer depth.")

    @staticmethod
    def args_read(args):
        VeeREH1.dmi_enable        = args.veer_dmi_enable
        VeeREH1.iccm_enable       = args.veer_iccm_enable
        VeeREH1.dccm_enable       = args.veer_dccm_enable
        VeeREH1.icache_enable     = args.veer_icache_enable
        VeeREH1.ret_stack_size    = args.veer_ret_stack_size
        VeeREH1.btb_size          = args.veer_btb_size
        VeeREH1.bht_size          = args.veer_bht_size
        VeeREH1.dccm_size         = args.veer_dccm_size
        VeeREH1.dccm_num_banks    = args.veer_dccm_num_banks
        VeeREH1.iccm_size         = args.veer_iccm_size
        VeeREH1.iccm_num_banks    = args.veer_iccm_num_banks
        VeeREH1.icache_size       = args.veer_icache_size
        VeeREH1.icache_ecc        = args.veer_icache_ecc
        VeeREH1.pic_2cycle        = args.veer_pic_2cycle
        VeeREH1.pic_region        = args.veer_pic_region
        VeeREH1.pic_offset        = args.veer_pic_offset
        VeeREH1.pic_size          = args.veer_pic_size
        VeeREH1.pic_total_int     = args.veer_pic_total_int
        VeeREH1.fpga_optimize     = args.veer_fpga_optimize
        VeeREH1.lsu_stbuf_depth   = args.veer_lsu_stbuf_depth
        VeeREH1.dma_buf_depth     = args.veer_dma_buf_depth
        VeeREH1.lsu_num_nbload    = args.veer_lsu_num_nbload
        VeeREH1.dec_instbuf_depth = args.veer_dec_instbuf_depth

        if not (1 <= VeeREH1.pic_total_int <= 32):
            raise ValueError("VeeR EH1 supports 1-32 LiteX interrupt sources.")

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags = GCC_FLAGS[self.variant]
        flags += " -D__veer_eh1__"
        return flags

    # Memory Mapping.
    @property
    def mem_map(self):
        pic_base = (VeeREH1.pic_region << 28) | VeeREH1.pic_offset
        mem_map = {
            "rom"  : 0x1000_0000,
            "sram" : 0x2000_0000,
            "csr"  : 0x8000_0000,
            "pic"  : pic_base,
        }
        if VeeREH1.iccm_enable:
            mem_map["iccm"] = 0xEE00_0000
        if VeeREH1.dccm_enable:
            mem_map["dccm"] = 0xF004_0000
        return mem_map

    def __init__(self, platform, variant="standard"):
        if not (1 <= VeeREH1.pic_total_int <= 32):
            raise ValueError("VeeR EH1 supports 1-32 LiteX interrupt sources.")

        self.platform     = platform
        self.variant      = variant
        self.dmi_enable   = bool(VeeREH1.dmi_enable)
        self.reset        = Signal()
        self.interrupt    = Signal(VeeREH1.pic_total_int)

        # AXI Interfaces.
        self.ibus    = axi.AXIInterface(data_width=64, address_width=32, id_width=3)  # RV_IFU_BUS_TAG = 3
        self.dbus    = axi.AXIInterface(data_width=64, address_width=32, id_width=4)  # RV_LSU_BUS_TAG = 4
        self.sbus    = axi.AXIInterface(data_width=64, address_width=32, id_width=1)  # RV_SB_BUS_TAG = 1
        self.dma_axi = axi.AXIInterface(data_width=64, address_width=32, id_width=1)  # RV_DMA_BUS_TAG = 1

        self.periph_buses = [self.ibus, self.dbus, self.sbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []                               # Memory buses (Connected directly to LiteDRAM).

        # # #

        # CPU Instance.
        self.cpu_params = dict(
            # Clk / Rst.
            i_clk               = ClockSignal("sys"),
            i_rst_l             = ~ResetSignal("sys") & ~self.reset,
            i_dbg_rst_l         = ~ResetSignal("sys"),

            # Reset/NMI Vectors
            i_nmi_vec           = Constant(0x11110000 >> 1, 31),

            # Interrupts
            i_nmi_int           = 0,
            i_timer_int         = 0,
            i_extintsrc_req     = self.interrupt,

            # Bus clock enables
            i_lsu_bus_clk_en    = 1,
            i_ifu_bus_clk_en    = 1,
            i_dbg_bus_clk_en    = 1,
            i_dma_bus_clk_en    = 1,

            # IFU AXI4 Ports
            o_ifu_axi_awvalid   = self.ibus.aw.valid,
            i_ifu_axi_awready   = self.ibus.aw.ready,
            o_ifu_axi_awid      = self.ibus.aw.id,
            o_ifu_axi_awaddr    = self.ibus.aw.addr,
            o_ifu_axi_awlen     = self.ibus.aw.len,
            o_ifu_axi_awsize    = self.ibus.aw.size,
            o_ifu_axi_awburst   = self.ibus.aw.burst,
            o_ifu_axi_awlock    = self.ibus.aw.lock,
            o_ifu_axi_awcache   = self.ibus.aw.cache,
            o_ifu_axi_awprot    = self.ibus.aw.prot,
            o_ifu_axi_awqos     = self.ibus.aw.qos,
            o_ifu_axi_awregion  = Open(4),

            o_ifu_axi_wvalid    = self.ibus.w.valid,
            i_ifu_axi_wready    = self.ibus.w.ready,
            o_ifu_axi_wdata     = self.ibus.w.data,
            o_ifu_axi_wstrb     = self.ibus.w.strb,
            o_ifu_axi_wlast     = self.ibus.w.last,

            i_ifu_axi_bvalid    = self.ibus.b.valid,
            o_ifu_axi_bready    = self.ibus.b.ready,
            i_ifu_axi_bresp     = self.ibus.b.resp,
            i_ifu_axi_bid       = self.ibus.b.id,

            o_ifu_axi_arvalid   = self.ibus.ar.valid,
            i_ifu_axi_arready   = self.ibus.ar.ready,
            o_ifu_axi_arid      = self.ibus.ar.id,
            o_ifu_axi_araddr    = self.ibus.ar.addr,
            o_ifu_axi_arlen     = self.ibus.ar.len,
            o_ifu_axi_arsize    = self.ibus.ar.size,
            o_ifu_axi_arburst   = self.ibus.ar.burst,
            o_ifu_axi_arlock    = self.ibus.ar.lock,
            o_ifu_axi_arcache   = self.ibus.ar.cache,
            o_ifu_axi_arprot    = self.ibus.ar.prot,
            o_ifu_axi_arqos     = self.ibus.ar.qos,
            o_ifu_axi_arregion  = Open(4),

            i_ifu_axi_rvalid    = self.ibus.r.valid,
            o_ifu_axi_rready    = self.ibus.r.ready,
            i_ifu_axi_rid       = self.ibus.r.id,
            i_ifu_axi_rdata     = self.ibus.r.data,
            i_ifu_axi_rresp     = self.ibus.r.resp,
            i_ifu_axi_rlast     = self.ibus.r.last,

            # LSU AXI4 Ports
            o_lsu_axi_awvalid   = self.dbus.aw.valid,
            i_lsu_axi_awready   = self.dbus.aw.ready,
            o_lsu_axi_awid      = self.dbus.aw.id,
            o_lsu_axi_awaddr    = self.dbus.aw.addr,
            o_lsu_axi_awlen     = self.dbus.aw.len,
            o_lsu_axi_awsize    = self.dbus.aw.size,
            o_lsu_axi_awburst   = self.dbus.aw.burst,
            o_lsu_axi_awlock    = self.dbus.aw.lock,
            o_lsu_axi_awcache   = self.dbus.aw.cache,
            o_lsu_axi_awprot    = self.dbus.aw.prot,
            o_lsu_axi_awqos     = self.dbus.aw.qos,
            o_lsu_axi_awregion  = self.dbus.aw.region,

            o_lsu_axi_wvalid    = self.dbus.w.valid,
            i_lsu_axi_wready    = self.dbus.w.ready,
            o_lsu_axi_wdata     = self.dbus.w.data,
            o_lsu_axi_wstrb     = self.dbus.w.strb,
            o_lsu_axi_wlast     = self.dbus.w.last,

            i_lsu_axi_bvalid    = self.dbus.b.valid,
            o_lsu_axi_bready    = self.dbus.b.ready,
            i_lsu_axi_bresp     = self.dbus.b.resp,
            i_lsu_axi_bid       = self.dbus.b.id,

            o_lsu_axi_arvalid   = self.dbus.ar.valid,
            i_lsu_axi_arready   = self.dbus.ar.ready,
            o_lsu_axi_arid      = self.dbus.ar.id,
            o_lsu_axi_araddr    = self.dbus.ar.addr,
            o_lsu_axi_arlen     = self.dbus.ar.len,
            o_lsu_axi_arsize    = self.dbus.ar.size,
            o_lsu_axi_arburst   = self.dbus.ar.burst,
            o_lsu_axi_arlock    = self.dbus.ar.lock,
            o_lsu_axi_arcache   = self.dbus.ar.cache,
            o_lsu_axi_arprot    = self.dbus.ar.prot,
            o_lsu_axi_arqos     = self.dbus.ar.qos,
            o_lsu_axi_arregion  = self.dbus.ar.region,

            i_lsu_axi_rvalid    = self.dbus.r.valid,
            o_lsu_axi_rready    = self.dbus.r.ready,
            i_lsu_axi_rid       = self.dbus.r.id,
            i_lsu_axi_rdata     = self.dbus.r.data,
            i_lsu_axi_rresp     = self.dbus.r.resp,
            i_lsu_axi_rlast     = self.dbus.r.last,

            # SB AXI4 Ports
            o_sb_axi_awvalid   = self.sbus.aw.valid,
            i_sb_axi_awready   = self.sbus.aw.ready,
            o_sb_axi_awid      = self.sbus.aw.id,
            o_sb_axi_awaddr    = self.sbus.aw.addr,
            o_sb_axi_awlen     = self.sbus.aw.len,
            o_sb_axi_awsize    = self.sbus.aw.size,
            o_sb_axi_awburst   = self.sbus.aw.burst,
            o_sb_axi_awlock    = self.sbus.aw.lock,
            o_sb_axi_awcache   = self.sbus.aw.cache,
            o_sb_axi_awprot    = self.sbus.aw.prot,
            o_sb_axi_awqos     = self.sbus.aw.qos,
            o_sb_axi_awregion  = Open(4),

            o_sb_axi_wvalid    = self.sbus.w.valid,
            i_sb_axi_wready    = self.sbus.w.ready,
            o_sb_axi_wdata     = self.sbus.w.data,
            o_sb_axi_wstrb     = self.sbus.w.strb,
            o_sb_axi_wlast     = self.sbus.w.last,

            i_sb_axi_bvalid    = self.sbus.b.valid,
            o_sb_axi_bready    = self.sbus.b.ready,
            i_sb_axi_bresp     = self.sbus.b.resp,
            i_sb_axi_bid       = self.sbus.b.id,

            o_sb_axi_arvalid   = self.sbus.ar.valid,
            i_sb_axi_arready   = self.sbus.ar.ready,
            o_sb_axi_arid      = self.sbus.ar.id,
            o_sb_axi_araddr    = self.sbus.ar.addr,
            o_sb_axi_arlen     = self.sbus.ar.len,
            o_sb_axi_arsize    = self.sbus.ar.size,
            o_sb_axi_arburst   = self.sbus.ar.burst,
            o_sb_axi_arlock    = self.sbus.ar.lock,
            o_sb_axi_arcache   = self.sbus.ar.cache,
            o_sb_axi_arprot    = self.sbus.ar.prot,
            o_sb_axi_arqos     = self.sbus.ar.qos,
            o_sb_axi_arregion  = Open(4),

            i_sb_axi_rvalid    = self.sbus.r.valid,
            o_sb_axi_rready    = self.sbus.r.ready,
            i_sb_axi_rid       = self.sbus.r.id,
            i_sb_axi_rdata     = self.sbus.r.data,
            i_sb_axi_rresp     = self.sbus.r.resp,
            i_sb_axi_rlast     = self.sbus.r.last,

            # DMA AXI4 Ports (slave — CPU is target)
            i_dma_axi_awvalid   = self.dma_axi.aw.valid,
            o_dma_axi_awready   = self.dma_axi.aw.ready,
            i_dma_axi_awid      = self.dma_axi.aw.id,
            i_dma_axi_awaddr    = self.dma_axi.aw.addr,
            i_dma_axi_awsize    = self.dma_axi.aw.size,
            i_dma_axi_awlen     = self.dma_axi.aw.len,
            i_dma_axi_awburst   = self.dma_axi.aw.burst,
            i_dma_axi_awprot    = self.dma_axi.aw.prot,

            i_dma_axi_wvalid    = self.dma_axi.w.valid,
            o_dma_axi_wready    = self.dma_axi.w.ready,
            i_dma_axi_wdata     = self.dma_axi.w.data,
            i_dma_axi_wstrb     = self.dma_axi.w.strb,
            i_dma_axi_wlast     = self.dma_axi.w.last,

            o_dma_axi_bvalid    = self.dma_axi.b.valid,
            i_dma_axi_bready    = self.dma_axi.b.ready,
            o_dma_axi_bresp     = self.dma_axi.b.resp,
            o_dma_axi_bid       = self.dma_axi.b.id,

            i_dma_axi_arvalid   = self.dma_axi.ar.valid,
            o_dma_axi_arready   = self.dma_axi.ar.ready,
            i_dma_axi_arid      = self.dma_axi.ar.id,
            i_dma_axi_araddr    = self.dma_axi.ar.addr,
            i_dma_axi_arsize    = self.dma_axi.ar.size,
            i_dma_axi_arlen     = self.dma_axi.ar.len,
            i_dma_axi_arburst   = self.dma_axi.ar.burst,
            i_dma_axi_arprot    = self.dma_axi.ar.prot,

            o_dma_axi_rvalid    = self.dma_axi.r.valid,
            i_dma_axi_rready    = self.dma_axi.r.ready,
            o_dma_axi_rid       = self.dma_axi.r.id,
            o_dma_axi_rdata     = self.dma_axi.r.data,
            o_dma_axi_rresp     = self.dma_axi.r.resp,
            o_dma_axi_rlast     = self.dma_axi.r.last,

            # Debug - tie off
            i_mpc_debug_halt_req = 0,
            i_mpc_debug_run_req  = 1,
            i_mpc_reset_run_req  = 1,
            o_mpc_debug_halt_ack = Open(),
            o_mpc_debug_run_ack  = Open(),
            o_debug_brkpt_status = Open(),

            i_i_cpu_halt_req    = 0,
            o_o_cpu_halt_ack    = Open(),
            o_o_cpu_halt_status = Open(),
            o_o_debug_mode_status = Open(),
            i_i_cpu_run_req     = 0,
            o_o_cpu_run_ack     = Open(),

            i_scan_mode         = 0,
            i_mbist_mode        = 0,

            o_dec_tlu_perfcnt0  = Open(2),
            o_dec_tlu_perfcnt1  = Open(2),
            o_dec_tlu_perfcnt2  = Open(2),
            o_dec_tlu_perfcnt3  = Open(2),

            # Trace ports (unused)
            o_trace_rv_i_insn_ip      = Open(64),
            o_trace_rv_i_address_ip   = Open(64),
            o_trace_rv_i_valid_ip     = Open(3),
            o_trace_rv_i_exception_ip = Open(3),
            o_trace_rv_i_ecause_ip    = Open(5),
            o_trace_rv_i_interrupt_ip = Open(3),
            o_trace_rv_i_tval_ip      = Open(32),
        )

        if self.dmi_enable:
            self.dmi_reg_en     = Signal()
            self.dmi_reg_addr   = Signal(7)
            self.dmi_reg_wr_en  = Signal()
            self.dmi_reg_wdata  = Signal(32)
            self.dmi_reg_rdata  = Signal(32)
            self.dmi_hard_reset = Signal()
            self.cpu_params.update(
                i_dmi_reg_en     = self.dmi_reg_en,
                i_dmi_reg_addr   = self.dmi_reg_addr,
                i_dmi_reg_wr_en  = self.dmi_reg_wr_en,
                i_dmi_reg_wdata  = self.dmi_reg_wdata,
                o_dmi_reg_rdata  = self.dmi_reg_rdata,
                i_dmi_hard_reset = self.dmi_hard_reset,
            )
        else:
            self.jtag_tck    = Signal()
            self.jtag_tms    = Signal()
            self.jtag_trst_n = Signal()
            self.jtag_tdi    = Signal()
            self.jtag_tdo    = Signal()
            self.cpu_params.update(
                i_jtag_tck    = self.jtag_tck,
                i_jtag_tms    = self.jtag_tms,
                i_jtag_trst_n = self.jtag_trst_n,
                i_jtag_tdi    = self.jtag_tdi,
                o_jtag_tdo    = self.jtag_tdo,
                i_jtag_id     = Constant(0, 31),
            )

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(i_rst_vec=Constant(reset_address >> 1, 31))

    def add_jtag(self, pads):
        if self.dmi_enable:
            raise ValueError("VeeR EH1 JTAG is unavailable when the DMI register port is enabled.")

        self.comb += [
            self.jtag_tck.eq(pads.tck),
            self.jtag_tms.eq(pads.tms),
            self.jtag_tdi.eq(pads.tdi),
            pads.tdo.eq(self.jtag_tdo),
        ]
        if hasattr(pads, "ntrst"):
            self.comb += self.jtag_trst_n.eq(pads.ntrst)
        elif hasattr(pads, "trst_n"):
            self.comb += self.jtag_trst_n.eq(pads.trst_n)
        else:
            self.comb += self.jtag_trst_n.eq(1)

    def add_soc_components(self, soc):
        soc.bus.add_region("pic", SoCRegion(
            origin = self.mem_map["pic"],
            size   = VeeREH1.pic_size*1024,
            cached = False,
            linker = True,
        ))
        if VeeREH1.iccm_enable:
            # The LSU reaches ICCM through the SoC fabric and loops back through
            # the core's DMA AXI slave, since ICCM is not LSU-addressable inside
            # the core.
            soc.bus.add_slave("iccm", self.dma_axi, region=SoCRegion(
                origin = self.mem_map["iccm"],
                size   = VeeREH1.iccm_size*1024,
                cached = False,
                linker = True,
            ))
        if VeeREH1.dccm_enable:
            soc.bus.add_region("dccm", SoCRegion(
                origin = self.mem_map["dccm"],
                size   = VeeREH1.dccm_size*1024,
                cached = False,
                linker = True,
            ))

    def _generate_snapshot(self, build_dir, vdir):
        snapshot_dir = os.path.join(build_dir, "veer_snapshot")
        os.makedirs(snapshot_dir, exist_ok=True)

        config_args = [
            "-target=default",
            "-unset=assert_on",
            f"-set=iccm_enable={VeeREH1.iccm_enable}",
            f"-set=dccm_enable={VeeREH1.dccm_enable}",
            f"-set=reset_vec={self.reset_address:#x}",
            f"-set=icache_enable={VeeREH1.icache_enable}",
            f"-set=ret_stack_size={VeeREH1.ret_stack_size}",
            f"-set=btb_size={VeeREH1.btb_size}",
            f"-set=bht_size={VeeREH1.bht_size}",
            f"-set=dccm_size={VeeREH1.dccm_size}",
            f"-set=dccm_num_banks={VeeREH1.dccm_num_banks}",
            f"-set=iccm_size={VeeREH1.iccm_size}",
            f"-set=iccm_num_banks={VeeREH1.iccm_num_banks}",
            f"-set=icache_size={VeeREH1.icache_size}",
            f"-set=icache_ecc={VeeREH1.icache_ecc}",
            f"-set=pic_2cycle={VeeREH1.pic_2cycle}",
            f"-set=pic_region={VeeREH1.pic_region:#x}",
            f"-set=pic_offset={VeeREH1.pic_offset:#x}",
            f"-set=pic_size={VeeREH1.pic_size}",
            f"-set=pic_total_int={VeeREH1.pic_total_int}",
            f"-set=fpga_optimize={VeeREH1.fpga_optimize}",
            f"-set=lsu_stbuf_depth={VeeREH1.lsu_stbuf_depth}",
            f"-set=dma_buf_depth={VeeREH1.dma_buf_depth}",
            f"-set=lsu_num_nbload={VeeREH1.lsu_num_nbload}",
            f"-set=dec_instbuf_depth={VeeREH1.dec_instbuf_depth}",
        ]

        env = os.environ.copy()
        env["RV_ROOT"]    = vdir
        env["BUILD_PATH"] = snapshot_dir

        config_script = os.path.join(vdir, "configs/veer.config")
        if not os.path.exists(config_script):
            raise FileNotFoundError(f"VeeR EH1 configuration script not found: {config_script}")

        try:
            subprocess.check_call([config_script] + config_args, env=env, cwd=vdir)
        except subprocess.CalledProcessError as error:
            raise OSError("Unable to generate the VeeR EH1 configuration.") from error

        # veer.config currently defines disabled features to 0 instead of
        # undefining them (Cores-VeeR-EH1 issue #135).
        common_defines = os.path.join(snapshot_dir, "common_defines.vh")
        with open(common_defines, "r") as f:
            content = f.read()

        features = {
            "ICCM"   : VeeREH1.iccm_enable,
            "DCCM"   : VeeREH1.dccm_enable,
            "ICACHE" : VeeREH1.icache_enable,
        }
        for feature, enabled in features.items():
            if not enabled:
                content = content.replace(
                    f"`define RV_{feature}_ENABLE 0",
                    f"`undef RV_{feature}_ENABLE",
                )

        with open(common_defines, "w") as f:
            f.write(content)

        return snapshot_dir

    def add_sources(self, platform):
        vdir = get_data_mod("cpu", "veer_eh1").data_location

        # Prepare build directory.
        if getattr(platform, "output_dir", None) is not None:
            build_dir = os.path.join(platform.output_dir, "gateware")
        else:
            build_dir = os.getcwd()
        os.makedirs(build_dir, exist_ok=True)

        # Generate the selected configuration.
        snapshot_dir = self._generate_snapshot(build_dir, vdir)

        # Add include paths.
        platform.add_verilog_include_path(os.path.join(vdir, "design"))
        platform.add_verilog_include_path(os.path.join(vdir, "design", "include"))
        platform.add_verilog_include_path(os.path.join(vdir, "design", "lib"))
        platform.add_verilog_include_path(snapshot_dir)

        # The generated defines and type package must precede the RTL.
        platform.add_source(os.path.join(snapshot_dir, "common_defines.vh"))
        veer_types_orig    = os.path.join(vdir, "design", "include", "veer_types.sv")
        veer_types_patched = os.path.join(snapshot_dir, "veer_types_patched.sv")
        with open(veer_types_orig, "r") as f:
            content = f.read()
        with open(veer_types_patched, "w") as f:
            f.write('`include "common_defines.vh"\n' + content)
        platform.add_source(veer_types_patched)

        # Keep the upstream manifest order and avoid adding the unpatched
        # veer_types.sv package a second time.
        for source in CPU_SOURCES:
            platform.add_source(os.path.join(vdir, source))

        if self.dmi_enable:
            platform.add_source(os.path.join(
                os.path.dirname(__file__),
                "veer_eh1_wrapper",
                "veer_eh1_dmi_wrapper.sv",
            ))
        else:
            for source in JTAG_SOURCES:
                platform.add_source(os.path.join(vdir, source))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.add_sources(self.platform)
        if self.dmi_enable:
            self.specials += Instance("veer_wrapper_dmi", **self.cpu_params)
        else:
            self.specials += Instance("veer_wrapper", **self.cpu_params)
