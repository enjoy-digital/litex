# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Benjamin Herrenschmidt <benh@ozlabs.org>
# License: BSD

import os

from migen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU


CPU_VARIANTS = ["standard", "standard+ghdl"]


class Microwatt(CPU):
    name                 = "microwatt"
    human_name           = "Microwatt"
    variants             = CPU_VARIANTS
    data_width           = 64
    endianness           = "little"
    gcc_triple           = ("powerpc64le-linux", "powerpc64le-linux-gnu")
    linker_output_format = "elf64-powerpcle"
    nop                  = "nop"
    io_regions           = {0xc0000000: 0x10000000} # origin, length

    @property
    def mem_map(self):
        return {"csr": 0xc0000000}

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
        self.wb_insn      = wb_insn = wishbone.Interface(data_width=64, adr_width=29)
        self.wb_data      = wb_data = wishbone.Interface(data_width=64, adr_width=29)
        self.periph_buses = [wb_insn, wb_data]
        self.memory_buses = []

        # # #

        self.cpu_params = dict(
            # Clock / Reset
            i_clk                 = ClockSignal(),
            i_rst                 = ResetSignal() | self.reset,

            # Wishbone instruction bus
            i_wishbone_insn_dat_r = wb_insn.dat_r,
            i_wishbone_insn_ack   = wb_insn.ack,
            i_wishbone_insn_stall = wb_insn.cyc & ~wb_insn.ack, # No burst support

            o_wishbone_insn_adr   = Cat(Signal(3), wb_insn.adr),
            o_wishbone_insn_dat_w = wb_insn.dat_w,
            o_wishbone_insn_cyc   = wb_insn.cyc,
            o_wishbone_insn_stb   = wb_insn.stb,
            o_wishbone_insn_sel   = wb_insn.sel,
            o_wishbone_insn_we    = wb_insn.we,

            # Wishbone data bus
            i_wishbone_data_dat_r = wb_data.dat_r,
            i_wishbone_data_ack   = wb_data.ack,
            i_wishbone_data_stall = wb_data.cyc & ~wb_data.ack, # No burst support

            o_wishbone_data_adr   = Cat(Signal(3), wb_data.adr),
            o_wishbone_data_dat_w = wb_data.dat_w,
            o_wishbone_data_cyc   = wb_data.cyc,
            o_wishbone_data_stb   = wb_data.stb,
            o_wishbone_data_sel   = wb_data.sel,
            o_wishbone_data_we    = wb_data.we,

            # Debug bus
            i_dmi_addr            = 0,
            i_dmi_din             = 0,
            #o_dmi_dout           =,
            i_dmi_req             = 0,
            i_dmi_wr              = 0,
            #o_dmi_ack            =,
        )

        # add vhdl sources
        self.add_sources(platform, use_ghdl_yosys_plugin="ghdl" in self.variant)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        assert reset_address == 0x00000000

    @staticmethod
    def add_sources(platform, use_ghdl_yosys_plugin=False):
        sources = [
            # Common / Types / Helpers
            "decode_types.vhdl",
            "wishbone_types.vhdl",
            "utils.vhdl",
            "common.vhdl",
            "helpers.vhdl",

            # Fetch
            "fetch1.vhdl",
            "fetch2.vhdl",

            # Instruction/Data Cache
            "cache_ram.vhdl",
            "plru.vhdl",
            "dcache.vhdl",
            "icache.vhdl",

            # Decode
            "insn_helpers.vhdl",
            "decode1.vhdl",
            "gpr_hazard.vhdl",
            "cr_hazard.vhdl",
            "control.vhdl",
            "decode2.vhdl",

            # Register/CR File
            "register_file.vhdl",
            "crhelpers.vhdl",
            "cr_file.vhdl",

            # Execute
            "ppc_fx_insns.vhdl",
            "logical.vhdl",
            "rotator.vhdl",
            "countzero.vhdl",
            "execute1.vhdl",

            # Load/Store
            "loadstore1.vhdl",

            # Multiply/Divide
            "multiply.vhdl",
            "divider.vhdl",

            # Writeback
            "writeback.vhdl",

            # Core
            "core_debug.vhdl",
            "core.vhdl",
        ]
        sdir = get_data_mod("cpu", "microwatt").data_location
        cdir = os.path.dirname(__file__)
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
        else:
            platform.add_sources(sdir, *sources)
            platform.add_source(os.path.join(os.path.dirname(__file__), "microwatt_wrapper.vhdl"))

    def do_finalize(self):
        self.specials += Instance("microwatt_wrapper", **self.cpu_params)
