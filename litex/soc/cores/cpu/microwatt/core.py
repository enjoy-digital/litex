# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
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
    io_regions           = {0x80000000: 0x80000000} # origin, length FIXME: check default IO regions

    @property
    def gcc_flags(self):
        # FIXME: add default flags
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
        platform.add_source(os.path.join(sdir, "decode_types.vhdl"))
        platform.add_source(os.path.join(sdir, "wishbone_types.vhdl"))
        platform.add_source(os.path.join(sdir, "common.vhdl"))
        platform.add_source(os.path.join(sdir, "fetch1.vhdl"))
        platform.add_source(os.path.join(sdir, "fetch2.vhdl"))
        platform.add_source(os.path.join(sdir, "decode1.vhdl"))
        platform.add_source(os.path.join(sdir, "helpers.vhdl"))
        platform.add_source(os.path.join(sdir, "decode2.vhdl"))
        platform.add_source(os.path.join(sdir, "register_file.vhdl"))
        platform.add_source(os.path.join(sdir, "cr_file.vhdl"))
        platform.add_source(os.path.join(sdir, "crhelpers.vhdl"))
        platform.add_source(os.path.join(sdir, "ppc_fx_insns.vhdl"))
        platform.add_source(os.path.join(sdir, "sim_console.vhdl"))
        platform.add_source(os.path.join(sdir, "logical.vhdl"))
        platform.add_source(os.path.join(sdir, "countzero.vhdl"))
        platform.add_source(os.path.join(sdir, "gpr_hazard.vhdl"))
        platform.add_source(os.path.join(sdir, "cr_hazard.vhdl"))
        platform.add_source(os.path.join(sdir, "control.vhdl"))
        platform.add_source(os.path.join(sdir, "execute1.vhdl"))
        platform.add_source(os.path.join(sdir, "loadstore1.vhdl"))
        platform.add_source(os.path.join(sdir, "dcache.vhdl"))
        platform.add_source(os.path.join(sdir, "multiply.vhdl"))
        platform.add_source(os.path.join(sdir, "divider.vhdl"))
        platform.add_source(os.path.join(sdir, "rotator.vhdl"))
        platform.add_source(os.path.join(sdir, "writeback.vhdl"))
        platform.add_source(os.path.join(sdir, "insn_helpers.vhdl"))
        platform.add_source(os.path.join(sdir, "core.vhdl"))
        platform.add_source(os.path.join(sdir, "icache.vhdl"))
        platform.add_source(os.path.join(sdir, "plru.vhdl"))
        platform.add_source(os.path.join(sdir, "cache_ram.vhdl"))
        platform.add_source(os.path.join(sdir, "core_debug.vhdl"))
        platform.add_source(os.path.join(sdir, "utils.vhdl"))
        platform.add_source(os.path.join(sdir, "..", "microwatt_wrapper.vhdl"))

    def do_finalize(self):
        self.specials += Instance("microwatt_wrapper", **self.cpu_params)
