#
# This file is part of LiteX.
#
# Copyright (c) 2022 Icenowy Zheng <uwu@icenowy.me>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re

from migen import *

from litex.gen import *

from litex import get_data_mod

from litex.soc.interconnect import axi
from litex.soc.interconnect import wishbone
from litex.soc.integration.soc import SoCRegion

from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV64

# Helpers ------------------------------------------------------------------------------------------

apb_layout = [
    ("paddr",  32),
    ("pwdata", 32),
    ("pwrite",  1),
    ("psel",    1),
    ("penable", 1),
    ("prdata", 32),
    ("pready",  1),
    ("pslverr", 1),
]

# Wishbone <> APB ----------------------------------------------------------------------------------

class Wishbone2APB(Module):
    def __init__(self, wb, apb):
        assert wb.data_width == 32
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(wb.cyc & wb.stb,
                NextState("ACK"),
            )
        )
        fsm.act("ACK",
            apb.penable.eq(1),
            wb.ack.eq(1),
            NextState("IDLE"),
        )

        self.comb += [
            apb.paddr.eq(Cat(Signal(2), wb.adr)),
            apb.pwrite.eq(wb.we),
            apb.psel.eq(1),
            apb.pwdata.eq(wb.dat_w),
            wb.dat_r.eq(apb.prdata),
        ]

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
    variants             = ["standard", "debug"]
    data_width           = 128
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV64
    linker_output_format = "elf64-littleriscv"
    nop                  = "nop"
    io_regions           = {0x9000_0000: 0x3000_0000} # Origin, Length.

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
            # By default, internal APB (contains PLIC and CLINT) is mapped at 0x9000_0000
            # Internal APB has a fixed size of 0x800_0000
            "plic":           0x9000_0000, # Region 1, Strong Order, Non-cacheable, Non-bufferable
            "clint":          0x9400_0000, # Region 1 too
            "ethmac":         0x9800_0000, # Region 1 too
            "riscv_dm":       0x9fff_f000, # Region 1 too
            "csr":            0xa000_0000, # Region 1 too
        }

    def __init__(self, platform, variant="standard", convert_periph_bus_to_wishbone=True):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.interrupt    = Signal(240)
        # Peripheral bus (Connected to main SoC's bus).
        self.axi_if = axi_if = axi.AXIInterface(data_width=128, address_width=40, id_width=8)
        if convert_periph_bus_to_wishbone:
            self.wb_if = wishbone.Interface(data_width=axi_if.data_width,
                                            adr_width=axi_if.address_width - log2_int(axi_if.data_width // 8))
            self.submodules += axi.AXI2Wishbone(axi_if, self.wb_if)
            self.periph_buses = [self.wb_if]
        else:
            self.periph_buses = [axi_if]
        self.memory_buses = []                 # Memory buses (Connected directly to LiteDRAM).

        # # #

        # Cycle count
        cycle_count = Signal(64)
        self.sync += cycle_count.eq(cycle_count + 1)

        # CPU Instance.
        self.cpu_params = dict(
            # Clk / Rst.
            i_pll_core_cpuclk  = ClockSignal("sys"),
            i_pad_cpu_rst_b    = ~ResetSignal("sys") & ~self.reset,
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
            o_biu_pad_awvalid  = axi_if.aw.valid,
            i_pad_biu_awready  = axi_if.aw.ready,
            o_biu_pad_awid     = axi_if.aw.id,
            o_biu_pad_awaddr   = axi_if.aw.addr,
            o_biu_pad_awlen    = axi_if.aw.len,
            o_biu_pad_awsize   = axi_if.aw.size,
            o_biu_pad_awburst  = axi_if.aw.burst,
            o_biu_pad_awlock   = axi_if.aw.lock,
            o_biu_pad_awcache  = axi_if.aw.cache,
            o_biu_pad_awprot   = axi_if.aw.prot,

            o_biu_pad_wvalid   = axi_if.w.valid,
            i_pad_biu_wready   = axi_if.w.ready,
            o_biu_pad_wdata    = axi_if.w.data,
            o_biu_pad_wstrb    = axi_if.w.strb,
            o_biu_pad_wlast    = axi_if.w.last,

            i_pad_biu_bvalid   = axi_if.b.valid,
            o_biu_pad_bready   = axi_if.b.ready,
            i_pad_biu_bid      = axi_if.b.id,
            i_pad_biu_bresp    = axi_if.b.resp,

            o_biu_pad_arvalid  = axi_if.ar.valid,
            i_pad_biu_arready  = axi_if.ar.ready,
            o_biu_pad_arid     = axi_if.ar.id,
            o_biu_pad_araddr   = axi_if.ar.addr,
            o_biu_pad_arlen    = axi_if.ar.len,
            o_biu_pad_arsize   = axi_if.ar.size,
            o_biu_pad_arburst  = axi_if.ar.burst,
            o_biu_pad_arlock   = axi_if.ar.lock,
            o_biu_pad_arcache  = axi_if.ar.cache,
            o_biu_pad_arprot   = axi_if.ar.prot,

            i_pad_biu_rvalid   = axi_if.r.valid,
            o_biu_pad_rready   = axi_if.r.ready,
            i_pad_biu_rid      = axi_if.r.id,
            i_pad_biu_rdata    = axi_if.r.data,
            i_pad_biu_rresp    = axi_if.r.resp,
            i_pad_biu_rlast    = axi_if.r.last,
        )

        if "debug" in variant:
            self.add_debug()

        # Add Verilog sources.
        add_manifest_sources(platform, "gen_rtl/filelists/C906_asic_rtl.fl")
        from litex.build.xilinx import XilinxPlatform
        if isinstance(platform, XilinxPlatform):
            # Import a filelist for Xilinx FPGAs
            add_manifest_sources(platform, "gen_rtl/filelists/xilinx_fpga.fl")
        else:
            # Import a filelist for generic platforms
            add_manifest_sources(platform, "gen_rtl/filelists/generic_fpga.fl")

    def add_debug(self):
        self.debug_bus = wishbone.Interface()
        debug_apb = Record(apb_layout)

        self.submodules += Wishbone2APB(self.debug_bus, debug_apb)
        self.cpu_params.update(
            i_sys_apb_clk     = ClockSignal("sys"),
            i_sys_apb_rst_b   = ~ResetSignal("sys") & ~self.reset,

            i_tdt_dmi_paddr   = debug_apb.paddr,
            i_tdt_dmi_penable = debug_apb.penable,
            i_tdt_dmi_psel    = debug_apb.psel,
            i_tdt_dmi_pwdata  = debug_apb.pwdata,
            i_tdt_dmi_pwrite  = debug_apb.pwrite,
            o_tdt_dmi_prdata  = debug_apb.prdata,
            o_tdt_dmi_pready  = debug_apb.pready,
            o_tdt_dmi_pslverr = debug_apb.pslverr,
        )

    def add_soc_components(self, soc):
        plic  = SoCRegion(origin=soc.mem_map.get("plic"), size=0x400_0000, cached=False)
        clint = SoCRegion(origin=soc.mem_map.get("clint"), size=0x400_0000, cached=False)
        soc.bus.add_region(name="plic",  region=plic)
        soc.bus.add_region(name="clint", region=clint)

        if "debug" in self.variant:
            soc.bus.add_slave("riscv_dm", self.debug_bus, region=
                SoCRegion(
                    origin = soc.mem_map.get("riscv_dm"),
                    size   = 0x1000,
                    cached = False
                )
            )

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(i_pad_cpu_rvba=Signal(40, reset=reset_address))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("openC906", **self.cpu_params)
