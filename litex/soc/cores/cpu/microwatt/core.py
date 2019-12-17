# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Benjamin Herrenschmidt <benh@ozlabs.org>
# License: BSD

import os

from migen import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU


CPU_VARIANTS = ["standard"]


class Microwatt(CPU):
    name                 = "microwatt"
    data_width           = 64
    endianness           = "little"
    gcc_triple           = ("powerpc64le-linux")
    linker_output_format = "elf64-powerpc64le"
    io_regions           = {0xc0000000: 0x10000000} # origin, length

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
        flags += "-D__microwatt__ "
        return flags

    def __init__(self, platform, variant="standard"):
        assert variant in CPU_VARIANTS, "Unsupported variant %s" % variant
        self.platform = platform
        self.variant  = variant
        self.reset    = Signal()
        self.wb_insn  = wb_insn = wishbone.Interface(data_width=64, adr_width=28)
        self.wb_data  = wb_data = wishbone.Interface(data_width=64, adr_width=28)
        self.buses    = [wb_insn, wb_data]

        # # #

        self.cpu_params = dict(
            # Clock / Reset
            i_clk                 = ClockSignal(),
            i_rst                 = ResetSignal() | self.reset,

            # Wishbone instruction bus
            i_wishbone_insn_dat_r = wb_insn.dat_r,
            i_wishbone_insn_ack   = wb_insn.ack,
            i_wishbone_insn_stall = wb_insn.cyc & ~wb_insn.ack, # No burst support

            o_wishbone_insn_adr   = Cat(Signal(4), wb_insn.adr),
            o_wishbone_insn_dat_w = wb_insn.dat_w,
            o_wishbone_insn_cyc   = wb_insn.cyc,
            o_wishbone_insn_stb   = wb_insn.stb,
            o_wishbone_insn_sel   = wb_insn.sel,
            o_wishbone_insn_we    = wb_insn.we,

            # Wishbone data bus
            i_wishbone_data_dat_r = wb_data.dat_r,
            i_wishbone_data_ack   = wb_data.ack,
            i_wishbone_data_stall = wb_data.cyc & ~wb_data.ack, # No burst support

            o_wishbone_data_adr   = Cat(Signal(4), wb_data.adr),
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
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        assert reset_address == 0x00000000

    @staticmethod
    def add_sources(platform):
        sdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "sources")
        platform.add_source(sdir,
            "decode_types.vhdl",
            "wishbone_types.vhdl",
            "common.vhdl",
            "fetch1.vhdl",
            "fetch2.vhdl",
            "decode1.vhdl",
            "helpers.vhdl",
            "decode2.vhdl",
            "register_file.vhdl",
            "cr_file.vhdl",
            "crhelpers.vhdl",
            "ppc_fx_insns.vhdl",
            "sim_console.vhdl",
            "logical.vhdl",
            "countzero.vhdl",
            "gpr_hazard.vhdl",
            "cr_hazard.vhdl",
            "control.vhdl",
            "execute1.vhdl",
            "loadstore1.vhdl",
            "dcache.vhdl",
            "multiply.vhdl",
            "divider.vhdl",
            "rotator.vhdl",
            "writeback.vhdl",
            "insn_helpers.vhdl",
            "core.vhdl",
            "icache.vhdl",
            "plru.vhdl",
            "cache_ram.vhdl",
            "core_debug.vhdl",
            "utils.vhdl"
        )
        platform.add_source(os.path.join(sdir, "..", "microwatt_wrapper.vhdl"))

    def do_finalize(self):
        self.specials += Instance("microwatt_wrapper", **self.cpu_params)
