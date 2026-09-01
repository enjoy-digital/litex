# This file is part of LiteX.
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess

from migen import *
from litex.gen import *
from litex import get_data_mod
from litex.soc.interconnect import axi
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32
from litex.soc.integration.soc import SoCRegion

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard"]

# VeeREH1 ---------------------------------------------------------------------------------------------

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
    io_regions           = {
        0x8000_0000: 0x8000_0000,   # existing: CSR/PIC space
    } # Origin, Length.

    dmi_enable           = 0          # Default=0             # Options: 0=JTAG pins, 1=DMI register port

    # Enable/disable ------------------------------------------------------------------------------
    iccm_enable          = 1          # Default=0             # Options: 0, 1
    dccm_enable          = 1          # Default=1             # Options: 0, 1
    icache_enable        = 1          # Default=1             # Options: 0, 1
    reset_vec            = 0x10000000 # Default=0x80000000 (veer.config default; LiteX targets often use 0x10000000)

    # Core parameters -------------------------------------------------------------------------------
    ret_stack_size       = 4          # Default=4    # Minimum: 2    # Options: 2-8
    btb_size             = 32         # Default=32   # Minimum: 32   # Options: 32,48,64,128,256,512
    bht_size             = 128        # Default=128  # Minimum: 32   # Options: 32,64,128,256,512,1024,2048

    # DCCM (Data Closely Coupled Memory) -------------------------------------------------------------
    dccm_size            = 128          # Default=64   # Minimum: 4 KB   # Options: 4,8,16,32,48,64,128,256,512
    dccm_num_banks       = 4          # Default=8    # Minimum: 4      # Options: 4,8,16 (16 only if size!=4)

    # ICCM (Instruction Closely Coupled Memory) ------------------------------------------------------
    iccm_size            = 128         # Default=512  # Minimum: 4 KB   # Options: 4,8,16,32,64,128,256,512
    iccm_num_banks       = 4          # Default=8    # Minimum: 4      # Options: 4,8,16 (16 only if size!=4)

    # ICache ------------------------------------------------------------------------------------------
    icache_size          = 64         # Default=16   # Minimum: 16 KB  # Options: 16,32,64,128,256
    icache_ecc           = 0          # Default=0 (parity)  # Options: 0=parity, 1=ECC (ECC = ~30% bigger)

    # PIC (Platform Interrupt Controller) ---------------------------------------------------------------
    # PIC Base Address = (pic_region << 28) + pic_offset = (0xf << 28) + 0xc0000 = 0xf00c0000 
    # Any software reading or writing to the PIC to manage interrupts will target memory addresses starting at 0xF00C_0000 up to the limit defined by your pic_size
    pic_2cycle           = 1          # Default=0    # Options: 0, 1 (2-cycle PIC may lower cycle time)
    pic_region           = "0xf"      # Default="0xf"
    pic_offset           = "0xc0000"  # Default="0xc0000"
    pic_size             = 32         # Default=32   # Minimum: 32 KB  # Options: 32,64,128,256
    pic_total_int        = 8          # Default=8    # Minimum: 1      # Options: 1-255

    # FPGA optimization -----------------------------------------------------------------------------
    fpga_optimize        = 1          # Default=1 (removes clock gating; keep 1 for FPGA builds)

    # Buffer sizes ----------------------------------------------------------------------------------
    lsu_stbuf_depth      = 8          # Default=8    # Minimum: 2   # Options: 2,4,8
    dma_buf_depth        = 4          # Default=4    # Minimum: 2   # Options: 2,4
    lsu_num_nbload       = 8          # Default=8    # Minimum: 2   # Options: 2,4,8
    dec_instbuf_depth    = 4          # Default=4    # Minimum: 2   # Options: 2,4

    # Command line configuration arguments
    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group(title="VeeR EH1 CPU options")
        cpu_group.add_argument("--veer-dmi-enable",     default=VeeREH1.dmi_enable,     help=f"Expose DMI register port (1) instead of JTAG pins (0). Default={VeeREH1.dmi_enable}", type=int)
        # Enable/disable options
        cpu_group.add_argument("--veer-iccm-enable",    default=VeeREH1.iccm_enable,    help=f"Enable ICCM (Instruction Tightly Coupled Memory). Default={VeeREH1.iccm_enable}", type=int)
        cpu_group.add_argument("--veer-dccm-enable",    default=VeeREH1.dccm_enable,    help=f"Enable DCCM (Data Tightly Coupled Memory). Default={VeeREH1.dccm_enable}", type=int)
        cpu_group.add_argument("--veer-icache-enable",  default=VeeREH1.icache_enable,  help=f"Enable ICache (Instruction Cache). Default={VeeREH1.icache_enable}", type=int)
        cpu_group.add_argument("--veer-reset-vec",      default=hex(VeeREH1.reset_vec), help=f"Reset vector address. Default={hex(VeeREH1.reset_vec)}")

        # Core parameters
        cpu_group.add_argument("--veer-ret-stack-size", default=VeeREH1.ret_stack_size, help=f"Return stack size (2-8). Default={VeeREH1.ret_stack_size}, Min=2", type=int)
        cpu_group.add_argument("--veer-btb-size",       default=VeeREH1.btb_size,       help=f"BTB size (32,48,64,128,256,512). Default={VeeREH1.btb_size}, Min=32", type=int)
        cpu_group.add_argument("--veer-bht-size",       default=VeeREH1.bht_size,       help=f"BHT size (32,64,128,256,512,1024,2048). Default={VeeREH1.bht_size}, Min=32", type=int)

        # DCCM parameters
        cpu_group.add_argument("--veer-dccm-size",      default=VeeREH1.dccm_size,      help=f"DCCM size in KB (4,8,16,32,48,64,128,256,512). Default={VeeREH1.dccm_size}, Min=4", type=int)
        cpu_group.add_argument("--veer-dccm-num-banks", default=VeeREH1.dccm_num_banks, help=f"Number of DCCM banks (4,8,16). Default={VeeREH1.dccm_num_banks}, Min=4", type=int)

        # ICCM parameters
        cpu_group.add_argument("--veer-iccm-size",      default=VeeREH1.iccm_size,      help=f"ICCM size in KB (4,8,16,32,64,128,256,512). Default={VeeREH1.iccm_size}, Min=4", type=int)
        cpu_group.add_argument("--veer-iccm-num-banks", default=VeeREH1.iccm_num_banks, help=f"Number of ICCM banks (4,8,16). Default={VeeREH1.iccm_num_banks}, Min=4", type=int)

        # ICache parameters
        cpu_group.add_argument("--veer-icache-size",    default=VeeREH1.icache_size, help=f"ICache size in KB (16,32,64,128,256). Default={VeeREH1.icache_size}, Min=16", type=int)
        cpu_group.add_argument("--veer-icache-ecc",     default=VeeREH1.icache_ecc,  help=f"Enable ICache ECC (0=parity, 1=ECC). Default={VeeREH1.icache_ecc}", type=int)

        # PIC parameters
        cpu_group.add_argument("--veer-pic-2cycle",     default=VeeREH1.pic_2cycle,    help=f"Enable 2-cycle PIC. Default={VeeREH1.pic_2cycle}", type=int)
        cpu_group.add_argument("--veer-pic-region",     default=VeeREH1.pic_region,    help=f"PIC 256MB region number (0x0-0xf). Default={VeeREH1.pic_region}")
        cpu_group.add_argument("--veer-pic-offset",     default=VeeREH1.pic_offset,    help=f"PIC offset within region. Default={VeeREH1.pic_offset}")
        cpu_group.add_argument("--veer-pic-size",       default=VeeREH1.pic_size,      help=f"PIC size in KB (32,64,128,256). Default={VeeREH1.pic_size}, Min=32", type=int)
        cpu_group.add_argument("--veer-pic-total-int",  default=VeeREH1.pic_total_int, help=f"Number of PIC interrupts (1-255). Default={VeeREH1.pic_total_int}, Min=1", type=int)

        # FPGA optimization
        cpu_group.add_argument("--veer-fpga-optimize",  default=VeeREH1.fpga_optimize, help=f"Enable FPGA optimization (remove clock gating). Default={VeeREH1.fpga_optimize}", type=int)

        # Buffer sizes
        cpu_group.add_argument("--veer-lsu-stbuf-depth",   default=VeeREH1.lsu_stbuf_depth,   help=f"LSU store buffer depth (2,4,8). Default={VeeREH1.lsu_stbuf_depth}, Min=2", type=int)
        cpu_group.add_argument("--veer-dma-buf-depth",     default=VeeREH1.dma_buf_depth,     help=f"DMA buffer depth (2,4). Default={VeeREH1.dma_buf_depth}, Min=2", type=int)
        cpu_group.add_argument("--veer-lsu-num-nbload",    default=VeeREH1.lsu_num_nbload,    help=f"LSU non-blocking load count (2,4,8). Default={VeeREH1.lsu_num_nbload}, Min=2", type=int)
        cpu_group.add_argument("--veer-dec-instbuf-depth", default=VeeREH1.dec_instbuf_depth, help=f"Decode instruction buffer depth (2,4). Default={VeeREH1.dec_instbuf_depth}, Min=2", type=int)

    @staticmethod
    def args_read(args):
        VeeREH1.dmi_enable        = args.veer_dmi_enable
        # Enable/disable
        VeeREH1.iccm_enable       = args.veer_iccm_enable
        VeeREH1.dccm_enable       = args.veer_dccm_enable
        VeeREH1.icache_enable     = args.veer_icache_enable
        VeeREH1.reset_vec         = int(args.veer_reset_vec, 16)

        # Core
        VeeREH1.ret_stack_size    = args.veer_ret_stack_size
        VeeREH1.btb_size          = args.veer_btb_size
        VeeREH1.bht_size          = args.veer_bht_size

        # DCCM
        VeeREH1.dccm_size         = args.veer_dccm_size
        VeeREH1.dccm_num_banks    = args.veer_dccm_num_banks

        # ICCM
        VeeREH1.iccm_size         = args.veer_iccm_size
        VeeREH1.iccm_num_banks    = args.veer_iccm_num_banks

        # ICache
        VeeREH1.icache_size       = args.veer_icache_size
        VeeREH1.icache_ecc        = args.veer_icache_ecc

        # PIC
        VeeREH1.pic_2cycle        = args.veer_pic_2cycle
        VeeREH1.pic_region        = args.veer_pic_region
        VeeREH1.pic_offset        = args.veer_pic_offset
        VeeREH1.pic_size          = args.veer_pic_size
        VeeREH1.pic_total_int     = args.veer_pic_total_int

        # FPGA
        VeeREH1.fpga_optimize     = args.veer_fpga_optimize

        # Buffers
        VeeREH1.lsu_stbuf_depth   = args.veer_lsu_stbuf_depth
        VeeREH1.dma_buf_depth     = args.veer_dma_buf_depth
        VeeREH1.lsu_num_nbload    = args.veer_lsu_num_nbload
        VeeREH1.dec_instbuf_depth = args.veer_dec_instbuf_depth

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags = "-march=rv32imc -mabi=ilp32"
        flags += " -D__veer_eh1__ "
        return flags

    # Memory Mapping.
    @property
    def mem_map(self):
        # PIC base = (pic_region << 28) | pic_offset
        pic_base = (int(VeeREH1.pic_region, 16) << 28) | int(VeeREH1.pic_offset, 16)
        
        # Start with required regions
        mem_map = {
            "rom"  : 0x1000_0000,
            "sram" : 0x2000_0000,
            "csr"  : 0x8000_0000,
            "pic"  : pic_base,
        }    
        # Add optional regions only if enabled
        if VeeREH1.iccm_enable:
            mem_map["iccm"] = 0xee000000
        if VeeREH1.dccm_enable:
            mem_map["dccm"] = 0xf0040000
        return mem_map

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.dmi_enable   = VeeREH1.dmi_enable
        self.reset        = Signal()

        n_ext_int = VeeREH1.pic_total_int   # RV_PIC_TOTAL_INT = Default 8
        self.interrupt      = Signal(n_ext_int)  

        # Create individual interrupt signals
        self.extintsrc_req = Signal(n_ext_int)  

        # Connect interrupt signals bit by bit 
        self.comb += self.extintsrc_req.eq(self.interrupt)

        # AXI Interfaces
        self.ibus    = axi.AXIInterface(data_width=64, address_width=32, id_width=3)  # RV_IFU_BUS_TAG = 3
        self.dbus    = axi.AXIInterface(data_width=64, address_width=32, id_width=4)  # RV_LSU_BUS_TAG = 4
        self.sbus    = axi.AXIInterface(data_width=64, address_width=32, id_width=1)  # RV_SB_BUS_TAG = 1
        self.dma_axi = axi.AXIInterface(data_width=64, address_width=32, id_width=1)  # RV_DMA_BUS_TAG = 1

        self.periph_buses = [self.ibus, self.dbus, self.sbus]
        self.memory_buses = []

        # CPU Instance parameters
        self.cpu_params = dict(
            # Clk / Rst.
            i_clk               = ClockSignal("sys"),
            i_rst_l             = ~ResetSignal("sys") & ~self.reset,
            i_dbg_rst_l         = ~ResetSignal("sys"),

            # Reset/NMI Vectors
            i_nmi_vec           = 0x11110000 >> 1,

            # Interrupts
            i_nmi_int           = 0,
            i_timer_int         = 0,
            i_extintsrc_req     = self.extintsrc_req,

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
            o_ifu_axi_awregion  = Open(),

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
            o_ifu_axi_arregion  = Open(),

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
            o_sb_axi_awregion  = Open(),

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
            o_sb_axi_arregion  = Open(),

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

            o_dec_tlu_perfcnt0  = Open(),
            o_dec_tlu_perfcnt1  = Open(),
            o_dec_tlu_perfcnt2  = Open(),
            o_dec_tlu_perfcnt3  = Open(),

            # Trace ports (unused)
            o_trace_rv_i_insn_ip      = Open(),
            o_trace_rv_i_address_ip   = Open(),
            o_trace_rv_i_valid_ip     = Open(),
            o_trace_rv_i_exception_ip = Open(),
            o_trace_rv_i_ecause_ip    = Open(),
            o_trace_rv_i_interrupt_ip = Open(),
            o_trace_rv_i_tval_ip      = Open(),
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
            self.jtag_tck  = Signal()
            self.jtag_tms  = Signal()
            self.jtag_trst = Signal()
            self.jtag_tdi  = Signal()
            self.jtag_tdo  = Signal()
            self.cpu_params.update(
                i_jtag_tck    = self.jtag_tck,
                i_jtag_tms    = self.jtag_tms,
                i_jtag_trst_n = self.jtag_trst,
                i_jtag_tdi    = self.jtag_tdi,
                o_jtag_tdo    = self.jtag_tdo,
            )

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(i_rst_vec=reset_address >> 1)

    def add_jtag(self, pads):
        """Add JTAG interface to the CPU."""
        self.comb += [
            self.jtag_tck.eq(pads.tck),
            self.jtag_tms.eq(pads.tms),
            self.jtag_tdi.eq(pads.tdi),
            pads.tdo.eq(self.jtag_tdo),
        ]
        if hasattr(pads, 'trst_n'):
            self.comb += self.jtag_trst.eq(pads.trst_n)
        else:
            self.comb += self.jtag_trst.eq(1)

    def add_soc_components(self, soc):
        soc.bus.add_region("pic", SoCRegion(
            origin = soc.mem_map.get("pic"),
            size   = VeeREH1.pic_size * 1024,  # pic_size is in KB, SoCRegion wants bytes
            cached = False,
            linker = True,
        ))
        if VeeREH1.iccm_enable:
            soc.bus.add_slave("iccm", self.dma_axi, region=SoCRegion(
                origin = soc.mem_map.get("iccm"),
                size   = VeeREH1.iccm_size * 1024,
                cached = False,
                linker = True,
            ))
        if VeeREH1.dccm_enable:
            # Add DCCM region  (for linker/memory map)
            soc.bus.add_region("dccm", SoCRegion(
                origin = soc.mem_map.get("dccm"),
                size   = VeeREH1.dccm_size * 1024,
                cached = False,
                linker = True,
            ))     

    @staticmethod
    def _generate_snapshot(build_dir, vdir):
        """Generate configuration snapshot in the build directory."""
        snapshot_dir = os.path.join(build_dir, "veer_snapshot")

        # Create snapshot directory
        os.makedirs(snapshot_dir, exist_ok=True)

        # Build config command with all parameters
        config_args = [
            "-target=default",
            f"-set=iccm_enable={VeeREH1.iccm_enable}",
            f"-set=dccm_enable={VeeREH1.dccm_enable}",
            f"-set=reset_vec={hex(VeeREH1.reset_vec)}",
            f"-set=icache_enable={VeeREH1.icache_enable}",
            # Core parameters
            f"-set=ret_stack_size={VeeREH1.ret_stack_size}",
            f"-set=btb_size={VeeREH1.btb_size}",
            f"-set=bht_size={VeeREH1.bht_size}",
            # DCCM
            f"-set=dccm_size={VeeREH1.dccm_size}",
            f"-set=dccm_num_banks={VeeREH1.dccm_num_banks}",
            # ICCM
            f"-set=iccm_size={VeeREH1.iccm_size}",
            f"-set=iccm_num_banks={VeeREH1.iccm_num_banks}",
            # ICache
            f"-set=icache_size={VeeREH1.icache_size}",
            f"-set=icache_ecc={VeeREH1.icache_ecc}",
            # PIC
            f"-set=pic_2cycle={VeeREH1.pic_2cycle}",
            f"-set=pic_region={VeeREH1.pic_region}",
            f"-set=pic_offset={VeeREH1.pic_offset}",
            f"-set=pic_size={VeeREH1.pic_size}",
            f"-set=pic_total_int={VeeREH1.pic_total_int}",
            # FPGA optimization
            f"-set=fpga_optimize={VeeREH1.fpga_optimize}",
            # Buffer sizes
            f"-set=lsu_stbuf_depth={VeeREH1.lsu_stbuf_depth}",
            f"-set=dma_buf_depth={VeeREH1.dma_buf_depth}",
            f"-set=lsu_num_nbload={VeeREH1.lsu_num_nbload}",
            f"-set=dec_instbuf_depth={VeeREH1.dec_instbuf_depth}",
        ]

        # Set environment variables
        env = os.environ.copy()
        env['RV_ROOT'] = vdir
        env['BUILD_PATH'] = snapshot_dir

        # Run veer.config
        config_script = os.path.join(vdir, "configs/veer.config")
        if not os.path.exists(config_script):
            raise FileNotFoundError(f"veer.config not found at {config_script}")

        cmd = [config_script] + config_args

        try:
            subprocess.check_call(cmd, env=env, cwd=vdir)
            print(f"VeeREH1: Configuration generated at {snapshot_dir}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to generate configuration: {e}")

        # Patch common_defines.vh to undef disabled features
        common_defines = os.path.join(snapshot_dir, "common_defines.vh")
        if os.path.exists(common_defines):
            with open(common_defines, 'r') as f:
                content = f.read()
            
            # Replace macro definitions with undefs for disabled features.
            # These lines can be removed once issue #135 is resolved and the
            # pythondata-cpu-veer_eh1/system_verilog source is updated accordingly.
            # https://github.com/chipsalliance/Cores-VeeR-EH1/issues/135
            # [Bug] veer.config defines disabled features instead of undefining them.
            if VeeREH1.iccm_enable == 0:
                content = content.replace('`define RV_ICCM_ENABLE 0', '`undef RV_ICCM_ENABLE')
            if VeeREH1.dccm_enable == 0:
                content = content.replace('`define RV_DCCM_ENABLE 0', '`undef RV_DCCM_ENABLE')
            if VeeREH1.icache_enable == 0:
                content = content.replace('`define RV_ICACHE_ENABLE 0', '`undef RV_ICACHE_ENABLE')
            
            # Add undef ASSERT_ON at the end if not already there
            if '`undef ASSERT_ON' not in content:
                content += '\n`undef ASSERT_ON\n'
            
            with open(common_defines, 'w') as f:
                f.write(content)
            
            print(f"VeeREH1: Patched {common_defines} to undef disabled features")

        return snapshot_dir

    @staticmethod
    def add_sources(platform, dmi_enable=0):
        vdir = get_data_mod("cpu", "veer_eh1").data_location

        if getattr(platform, "output_dir", None) is not None:
            build_dir = os.path.join(platform.output_dir, "gateware")
        else:
            build_dir = os.getcwd()
            print(f"VeeREH1: platform.output_dir is None, using {build_dir}")

        os.makedirs(build_dir, exist_ok=True)

        # Generate snapshot in build directory
        snapshot_dir = VeeREH1._generate_snapshot(build_dir, vdir)

        # CRITICAL: Add include paths FIRST so Verilator can find them
        platform.add_verilog_include_path(os.path.join(vdir, "design"))
        platform.add_verilog_include_path(os.path.join(vdir, "design/include"))
        platform.add_verilog_include_path(snapshot_dir)

        # IMPORTANT: common_defines.vh MUST come BEFORE veer_types.sv
        platform.add_source(os.path.join(snapshot_dir, "common_defines.vh"))

        # Patch veer_types.sv to include common_defines.vh
        veer_types_orig = os.path.join(vdir, "design/include/veer_types.sv")
        veer_types_patched = os.path.join(snapshot_dir, "veer_types_patched.sv")
        with open(veer_types_orig, 'r') as f:
            content = f.read()
        with open(veer_types_patched, 'w') as f:
            f.write('`include "common_defines.vh"\n' + content)

        # Then veer_types.sv (which uses the defines) - use patched version
        platform.add_source(veer_types_patched)

        # Add design files recursively
        design_dir = os.path.join(vdir, "design")
        for root, dirs, files in os.walk(design_dir):
            for file in files:
                if file.endswith((".sv", ".v")):
                    file_path = os.path.join(root, file)
                    platform.add_source(file_path)

        if dmi_enable:
            wrapper_file = os.path.join(os.path.dirname(__file__), "veer_eh1_wrapper", "veer_eh1_dmi_wrapper.sv")
            platform.add_source(wrapper_file)

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.add_sources(self.platform, self.dmi_enable)
        if self.dmi_enable:
            self.specials += Instance("veer_wrapper_dmi", **self.cpu_params)
        else:
            self.specials += Instance("veer_wrapper", **self.cpu_params)