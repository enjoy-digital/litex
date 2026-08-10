# This file is part of LiteX.
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
from sys import platform

from migen import *
from litex.gen import *
from litex import get_data_mod
from litex.soc.interconnect import axi
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

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
    io_regions           = {0x8000_0000: 0x8000_0000} # Origin, Length.

    # Default parameters
    iccm_enable          = 1
    dccm_enable          = 1
    reset_vec            = 0x80000000

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags = "-march=rv32imc_zicsr_zifencei -mabi=ilp32"
        flags += " -D__veer_eh1__ "
        return flags

    # Command line configuration arguments
    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group(title="VeeR EH1 CPU options")
        cpu_group.add_argument("--veer-iccm-enable",    default=1,          help="Enable ICCM (Instruction Tightly Coupled Memory).", type=int)
        cpu_group.add_argument("--veer-dccm-enable",    default=1,          help="Enable DCCM (Data Tightly Coupled Memory).", type=int)
        cpu_group.add_argument("--veer-reset-vec",      default="0x80000000", help="Reset vector address.")

    @staticmethod
    def args_read(args):
        VeeREH1.iccm_enable       = args.veer_iccm_enable
        VeeREH1.dccm_enable       = args.veer_dccm_enable
        VeeREH1.reset_vec         = int(args.veer_reset_vec, 16)

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.interrupt    = Signal(8)  # RV_PIC_TOTAL_INT = 8

        # Create individual interrupt signals
        self.timer_int = Signal()
        self.extintsrc_req = Signal(7)

        # AXI Interfaces
        self.ibus = axi.AXIInterface(data_width=64, address_width=32, id_width=3)  # RV_IFU_BUS_TAG = 3
        self.dbus = axi.AXIInterface(data_width=64, address_width=32, id_width=4)  # RV_LSU_BUS_TAG = 4

        self.periph_buses = [self.ibus, self.dbus]
        self.memory_buses = []

        # JTAG signals
        self.jtag_tck  = Signal()
        self.jtag_tms  = Signal()
        self.jtag_trst = Signal()
        self.jtag_tdi  = Signal()
        self.jtag_tdo  = Signal()

        # Connect interrupt signals bit by bit (avoid slice issues)
        self.comb += [
            self.timer_int.eq(self.interrupt[0]),
        ]
        for i in range(7):
            self.comb += self.extintsrc_req[i].eq(self.interrupt[i+1])

        # CPU Instance parameters
        self.cpu_params = dict(
            # Clk / Rst.
            i_clk               = ClockSignal("sys"),
            i_rst_l             = ~(ResetSignal("sys") | self.reset),
            i_dbg_rst_l         = ~ResetSignal("sys"),

            # Reset/NMI Vectors
            i_rst_vec           = VeeREH1.reset_vec >> 1,
            i_nmi_vec           = 0x11110000 >> 1,
            i_jtag_id           = 0xDEADBEEF,

            # Interrupts
            i_nmi_int           = 0,
            i_timer_int         = self.timer_int,
            i_extintsrc_req     = self.extintsrc_req,

            # Bus clock enables
            i_lsu_bus_clk_en    = 1,
            i_ifu_bus_clk_en    = 1,
            i_dbg_bus_clk_en    = 1,
            i_dma_bus_clk_en    = 1,

            # JTAG
            i_jtag_tck          = self.jtag_tck,
            i_jtag_tms          = self.jtag_tms,
            i_jtag_tdi          = self.jtag_tdi,
            i_jtag_trst_n       = self.jtag_trst,
            o_jtag_tdo          = self.jtag_tdo,

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
            o_lsu_axi_awregion  = Open(),

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
            o_lsu_axi_arregion  = Open(),

            i_lsu_axi_rvalid    = self.dbus.r.valid,
            o_lsu_axi_rready    = self.dbus.r.ready,
            i_lsu_axi_rid       = self.dbus.r.id,
            i_lsu_axi_rdata     = self.dbus.r.data,
            i_lsu_axi_rresp     = self.dbus.r.resp,
            i_lsu_axi_rlast     = self.dbus.r.last,

            # SB AXI - tie off
            o_sb_axi_awvalid    = Open(),
            i_sb_axi_awready    = 0,
            o_sb_axi_awid       = Open(),
            o_sb_axi_awaddr     = Open(),
            o_sb_axi_awlen      = Open(),
            o_sb_axi_awsize     = Open(),
            o_sb_axi_awburst    = Open(),
            o_sb_axi_awlock     = Open(),
            o_sb_axi_awcache    = Open(),
            o_sb_axi_awprot     = Open(),
            o_sb_axi_awqos      = Open(),
            o_sb_axi_awregion   = Open(),
            o_sb_axi_wvalid     = Open(),
            i_sb_axi_wready     = 0,
            o_sb_axi_wdata      = Open(),
            o_sb_axi_wstrb      = Open(),
            o_sb_axi_wlast      = Open(),
            i_sb_axi_bvalid     = 0,
            o_sb_axi_bready     = Open(),
            i_sb_axi_bresp      = 0,
            i_sb_axi_bid        = 0,
            o_sb_axi_arvalid    = Open(),
            i_sb_axi_arready    = 0,
            o_sb_axi_arid       = Open(),
            o_sb_axi_araddr     = Open(),
            o_sb_axi_arlen      = Open(),
            o_sb_axi_arsize     = Open(),
            o_sb_axi_arburst    = Open(),
            o_sb_axi_arlock     = Open(),
            o_sb_axi_arcache    = Open(),
            o_sb_axi_arprot     = Open(),
            o_sb_axi_arqos      = Open(),
            o_sb_axi_arregion   = Open(),
            i_sb_axi_rvalid     = 0,
            o_sb_axi_rready     = Open(),
            i_sb_axi_rid        = 0,
            i_sb_axi_rdata      = 0,
            i_sb_axi_rresp      = 0,
            i_sb_axi_rlast      = 0,

            # DMA AXI - tie off
            i_dma_axi_awvalid   = 0,
            o_dma_axi_awready   = Open(),
            i_dma_axi_awid      = 0,
            i_dma_axi_awaddr    = 0,
            i_dma_axi_awsize    = 0,
            i_dma_axi_awprot    = 0,
            i_dma_axi_awlen     = 0,
            i_dma_axi_awburst   = 0,
            i_dma_axi_wvalid    = 0,
            o_dma_axi_wready    = Open(),
            i_dma_axi_wdata     = 0,
            i_dma_axi_wstrb     = 0,
            i_dma_axi_wlast     = 0,
            o_dma_axi_bvalid    = Open(),
            i_dma_axi_bready    = 0,
            o_dma_axi_bresp     = Open(),
            o_dma_axi_bid       = Open(),
            i_dma_axi_arvalid   = 0,
            o_dma_axi_arready   = Open(),
            i_dma_axi_arid      = 0,
            i_dma_axi_araddr    = 0,
            i_dma_axi_arsize    = 0,
            i_dma_axi_arprot    = 0,
            i_dma_axi_arlen     = 0,
            i_dma_axi_arburst   = 0,
            o_dma_axi_rvalid    = Open(),
            i_dma_axi_rready    = 0,
            o_dma_axi_rid       = Open(),
            o_dma_axi_rdata     = Open(),
            o_dma_axi_rresp     = Open(),
            o_dma_axi_rlast     = Open(),

            # Debug - tie off
            i_mpc_debug_halt_req = 0,
            i_mpc_debug_run_req  = 0,
            i_mpc_reset_run_req  = 0,
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

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        VeeREH1.reset_vec = reset_address
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

    @staticmethod
    def _generate_snapshot(build_dir, vdir):
        """Generate configuration snapshot in the build directory."""
        snapshot_dir = os.path.join(build_dir, "veer_snapshot")
        
        # Create snapshot directory
        os.makedirs(snapshot_dir, exist_ok=True)
        
        # Build config command with parameters from class variables
        config_args = [
            "-target=default",
            f"-set=iccm_enable={VeeREH1.iccm_enable}",
            f"-set=dccm_enable={VeeREH1.dccm_enable}",
            f"-set=reset_vec={hex(VeeREH1.reset_vec)}",
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
        
        # Add `undef ASSERT_ON to common_defines.vh
        common_defines = os.path.join(snapshot_dir, "common_defines.vh")
        if os.path.exists(common_defines):
            with open(common_defines, 'a') as f:
                f.write('\n`undef ASSERT_ON\n')
            print(f"VeeREH1: Added `undef ASSERT_ON to {common_defines}")
        
        return snapshot_dir

    @staticmethod
    def add_sources(platform):
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
        
        # Then veer_types.sv (which uses the defines)
        platform.add_source(os.path.join(vdir, "design/include/veer_types.sv"))
        
        # Skip problematic files
        skip_files = [
            "pic_ctrl_verilator_unroll.sv",
            "pic_map_auto.h",
        ]
        
        # Add design files recursively
        design_dir = os.path.join(vdir, "design")
        for root, dirs, files in os.walk(design_dir):
            for file in files:
                if file.endswith((".sv", ".v")):
                    if file in skip_files:
                        print(f"VeeREH1: Skipping {file} (not needed for simulation)")
                        continue
                    file_path = os.path.join(root, file)
                    platform.add_source(file_path)

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        # Add sources before instantiating (like VexRiscv)
        self.add_sources(self.platform)
        self.specials += Instance("veer_wrapper", **self.cpu_params)