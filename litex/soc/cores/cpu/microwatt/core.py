#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Benjamin Herrenschmidt <benh@ozlabs.org>
# Copyright (c) 2020 Raptor Engineering <sales@raptorengineering.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import *
from litex.gen.common import reverse_bytes
from litex.soc.cores.cpu import CPU

class Open(Signal): pass

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard", "standard+ghdl", "standard+irq", "standard+ghdl+irq"]

# Microwatt ----------------------------------------------------------------------------------------

class Microwatt(CPU):
    category             = "softcore"
    family               = "ppc64"
    name                 = "microwatt"
    human_name           = "Microwatt"
    variants             = CPU_VARIANTS
    data_width           = 64
    endianness           = "little"
    gcc_triple           = ("powerpc64le-linux", "powerpc64le-linux-gnu", "ppc64le-linux", "ppc64le-linux-musl")
    linker_output_format = "elf64-powerpcle"
    nop                  = "nop"
    io_regions           = {0xc0000000: 0x10000000} # Origin, Length.

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            # Keep the lower 128MBs for SoC IOs auto-allocation.
            "csr":      0xc8000000,
            "xicsicp":  0xcbff0000,
            "xicsics":  0xcbff1000,
        }

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags  = "-m64 "
        flags += "-mabi=elfv2 "
        flags += "-msoft-float "
        flags += "-mno-string "
        flags += "-mno-multiple "
        flags += "-mno-vsx "
        flags += "-mno-altivec "
        flags += "-mlittle-endian "
        flags += "-mstrict-align "
        flags += "-fno-stack-protector "
        flags += "-D__microwatt__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.ibus         = ibus = wishbone.Interface(data_width=64, adr_width=29)
        self.dbus         = dbus = wishbone.Interface(data_width=64, adr_width=29)
        self.periph_buses = [ibus, dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []           # Memory buses (Connected directly to LiteDRAM).
        if "irq" in variant:
            self.interrupt = Signal(16)
        self.core_ext_irq = Signal()

        # # #

        self.cpu_params = dict(
            # Clk / Rst.
            i_clk = ClockSignal("sys"),
            i_rst = ResetSignal("sys") | self.reset,

            # IBus.
            i_wishbone_insn_dat_r = ibus.dat_r,
            i_wishbone_insn_ack   = ibus.ack,
            i_wishbone_insn_stall = ibus.cyc & ~ibus.ack, # No burst support

            o_wishbone_insn_adr   = ibus.adr,
            o_wishbone_insn_dat_w = ibus.dat_w,
            o_wishbone_insn_cyc   = ibus.cyc,
            o_wishbone_insn_stb   = ibus.stb,
            o_wishbone_insn_sel   = ibus.sel,
            o_wishbone_insn_we    = ibus.we,

            # DBus.
            i_wishbone_data_dat_r = dbus.dat_r,
            i_wishbone_data_ack   = dbus.ack,
            i_wishbone_data_stall = dbus.cyc & ~dbus.ack, # No burst support

            o_wishbone_data_adr   = dbus.adr,
            o_wishbone_data_dat_w = dbus.dat_w,
            o_wishbone_data_cyc   = dbus.cyc,
            o_wishbone_data_stb   = dbus.stb,
            o_wishbone_data_sel   = dbus.sel,
            o_wishbone_data_we    = dbus.we,

            # Snoop.
            i_wb_snoop_in_adr   = 0,
            i_wb_snoop_in_dat_w = 0,
            i_wb_snoop_in_cyc   = 0,
            i_wb_snoop_in_stb   = 0,
            i_wb_snoop_in_sel   = 0,
            i_wb_snoop_in_we    = 0,

            # Debug.
            i_dmi_addr = 0,
            i_dmi_din  = 0,
            o_dmi_dout = Open(),
            i_dmi_req  = 0,
            i_dmi_wr   = 0,
            o_dmi_ack  = Open(),

            # IRQ.
            i_core_ext_irq = self.core_ext_irq,
        )

        # Add VHDL sources.
        self.add_sources(platform, use_ghdl_yosys_plugin="ghdl" in self.variant)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        assert reset_address == 0x00000000

    def add_soc_components(self, soc, soc_region_cls):
        if "irq" in self.variant:
            self.submodules.xics = XICSSlave(
                platform     = self.platform,
                variant      = self.variant,
                core_irq_out = self.core_ext_irq,
                int_level_in = self.interrupt,
            )
            xicsicp_region = soc_region_cls(origin=soc.mem_map.get("xicsicp"), size=4096, cached=False)
            xicsics_region = soc_region_cls(origin=soc.mem_map.get("xicsics"), size=4096, cached=False)
            soc.bus.add_slave(name="xicsicp", slave=self.xics.icp_bus, region=xicsicp_region)
            soc.bus.add_slave(name="xicsics", slave=self.xics.ics_bus, region=xicsics_region)

    @staticmethod
    def add_sources(platform, use_ghdl_yosys_plugin=False):
        sources = [
            # Common / Types / Helpers.
            "decode_types.vhdl",
            "wishbone_types.vhdl",
            "utils.vhdl",
            "common.vhdl",
            "helpers.vhdl",
            "nonrandom.vhdl",

            # Fetch.
            "fetch1.vhdl",

            # Instruction/Data Cache.
            "cache_ram.vhdl",
            "plru.vhdl",
            "dcache.vhdl",
            "icache.vhdl",

            # Decode.
            "insn_helpers.vhdl",
            "decode1.vhdl",
            "control.vhdl",
            "decode2.vhdl",

            # Register/CR File.
            "register_file.vhdl",
            "crhelpers.vhdl",
            "cr_file.vhdl",

            # Execute.
            "ppc_fx_insns.vhdl",
            "logical.vhdl",
            "rotator.vhdl",
            "countbits.vhdl",
            "execute1.vhdl",

            # Load/Store.
            "loadstore1.vhdl",

            # Divide.
            "divider.vhdl",

            # FPU.
            "fpu.vhdl",

            # PMU.
            "pmu.vhdl",

            # Writeback.
            "writeback.vhdl",

            # MMU.
            "mmu.vhdl",

            # Core.
            "core_debug.vhdl",
            "core.vhdl",
        ]
        from litex.build.xilinx import XilinxPlatform
        if isinstance(platform, XilinxPlatform) and not use_ghdl_yosys_plugin:
            sources.append("xilinx-mult.vhdl")
        else:
            sources.append("multiply.vhdl")

        sdir = get_data_mod("cpu", "microwatt").data_location
        cdir = os.path.dirname(__file__)
        # Convert VHDL to Verilog through GHDL/Yosys.
        if use_ghdl_yosys_plugin:
            from litex.build import tools
            import subprocess
            ys = []
            ys.append("ghdl --ieee=synopsys -fexplicit -frelaxed-rules --std=08 \\")
            for source in sources:
                ys.append(os.path.join(sdir, source) + " \\")
            ys.append(os.path.join(os.path.dirname(__file__), "microwatt_wrapper.vhdl") + " \\")
            ys.append("-e microwatt_wrapper")
            ys.append("chformal -assert -remove")
            ys.append("write_verilog {}".format(os.path.join(cdir, "microwatt.v")))
            tools.write_to_file(os.path.join(cdir, "microwatt.ys"), "\n".join(ys))
            if subprocess.call(["yosys", "-q", "-m", "ghdl", os.path.join(cdir, "microwatt.ys")]):
                raise OSError("Unable to convert Microwatt CPU to verilog, please check your GHDL-Yosys-plugin install")
            platform.add_source(os.path.join(cdir, "microwatt.v"))
        # Direct use of VHDL sources.
        else:
            platform.add_sources(sdir, *sources)
            platform.add_source(os.path.join(os.path.dirname(__file__), "microwatt_wrapper.vhdl"))

    def do_finalize(self):
        self.specials += Instance("microwatt_wrapper", **self.cpu_params)

# XICS Slave ---------------------------------------------------------------------------------------

class XICSSlave(Module, AutoCSR):
    def __init__(self, platform, core_irq_out=Signal(), int_level_in=Signal(16), variant="standard"):
        self.variant = variant

        self.icp_bus = icp_bus = wishbone.Interface(data_width=32, adr_width=12)
        self.ics_bus = ics_bus = wishbone.Interface(data_width=32, adr_width=12)

        # XICS signals.
        self.ics_icp_xfer_src = Signal(4)
        self.ics_icp_xfer_pri = Signal(8)

        self.icp_params = dict(
            # Clk / Rst.
            i_clk            = ClockSignal("sys"),
            i_rst            = ResetSignal("sys"),

            # Wishbone Bus.
            o_wishbone_dat_r = icp_bus.dat_r,
            o_wishbone_ack   = icp_bus.ack,

            i_wishbone_adr   = icp_bus.adr,
            i_wishbone_dat_w = icp_bus.dat_w,
            i_wishbone_cyc   = icp_bus.cyc,
            i_wishbone_stb   = icp_bus.stb,
            i_wishbone_sel   = icp_bus.sel,
            i_wishbone_we    = icp_bus.we,

            i_ics_in_src     = self.ics_icp_xfer_src,
            i_ics_in_pri     = self.ics_icp_xfer_pri,

            o_core_irq_out   = core_irq_out,
        )

        self.ics_params = dict(
            # Clk / Rst.
            i_clk            = ClockSignal("sys"),
            i_rst            = ResetSignal("sys"),

            # Wishbone Bus.
            o_wishbone_dat_r = ics_bus.dat_r,
            o_wishbone_ack   = ics_bus.ack,

            i_wishbone_adr   = ics_bus.adr,
            i_wishbone_dat_w = ics_bus.dat_w,
            i_wishbone_cyc   = ics_bus.cyc,
            i_wishbone_stb   = ics_bus.stb,
            i_wishbone_sel   = ics_bus.sel,
            i_wishbone_we    = ics_bus.we,

            i_int_level_in   = int_level_in,

            o_icp_out_src    = self.ics_icp_xfer_src,
            o_icp_out_pri    = self.ics_icp_xfer_pri,
        )

        # Add VHDL sources.
        self.add_sources(platform, use_ghdl_yosys_plugin="ghdl" in self.variant)

    @staticmethod
    def add_sources(platform, use_ghdl_yosys_plugin=False):
        sources = [
            # Common / Types / Helpers
            "decode_types.vhdl",
            "wishbone_types.vhdl",
            "utils.vhdl",
            "common.vhdl",
            "helpers.vhdl",

            # XICS controller
            "xics.vhdl",
        ]
        sdir = get_data_mod("cpu", "microwatt").data_location
        cdir = os.path.dirname(__file__)
        if use_ghdl_yosys_plugin:
            from litex.build import tools
            import subprocess

            # ICP
            ys = []
            ys.append("ghdl --ieee=synopsys -fexplicit -frelaxed-rules --std=08 \\")
            for source in sources:
                ys.append(os.path.join(sdir, source) + " \\")
            ys.append(os.path.join(os.path.dirname(__file__), "xics_wrapper.vhdl") + " \\")
            ys.append("-e xics_icp_wrapper")
            ys.append("chformal -assert -remove")
            ys.append("write_verilog {}".format(os.path.join(cdir, "xics_icp.v")))
            tools.write_to_file(os.path.join(cdir, "xics_icp.ys"), "\n".join(ys))
            if subprocess.call(["yosys", "-q", "-m", "ghdl", os.path.join(cdir, "xics_icp.ys")]):
                raise OSError("Unable to convert Microwatt XICS ICP controller to verilog, please check your GHDL-Yosys-plugin install")
            platform.add_source(os.path.join(cdir, "xics_icp.v"))

            # ICS
            ys = []
            ys.append("ghdl --ieee=synopsys -fexplicit -frelaxed-rules --std=08 \\")
            for source in sources:
                ys.append(os.path.join(sdir, source) + " \\")
            ys.append(os.path.join(os.path.dirname(__file__), "xics_wrapper.vhdl") + " \\")
            ys.append("-e xics_ics_wrapper")
            ys.append("chformal -assert -remove")
            ys.append("write_verilog {}".format(os.path.join(cdir, "xics_ics.v")))
            tools.write_to_file(os.path.join(cdir, "xics_ics.ys"), "\n".join(ys))
            if subprocess.call(["yosys", "-q", "-m", "ghdl", os.path.join(cdir, "xics_ics.ys")]):
                raise OSError("Unable to convert Microwatt XICS ICP controller to verilog, please check your GHDL-Yosys-plugin install")
            platform.add_source(os.path.join(cdir, "xics_ics.v"))
        else:
            platform.add_sources(sdir, *sources)
            platform.add_source(os.path.join(os.path.dirname(__file__), "xics_wrapper.vhdl"))

    def do_finalize(self):
        self.specials += Instance("xics_icp_wrapper", **self.icp_params)
        self.specials += Instance("xics_ics_wrapper", **self.ics_params)
