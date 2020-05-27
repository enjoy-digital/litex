# This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 Greg Davill <greg.davill@gmail.com>
# License: BSD

import os

from migen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32


CPU_VARIANTS = ["standard"]


class SERV(CPU):
    name                 = "serv"
    human_name           = "SERV"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x80000000: 0x80000000} # origin, length

    @property
    def gcc_flags(self):
        flags =  "-march=rv32i "
        flags += "-mabi=ilp32 "
        flags += "-D__serv__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.ibus         = ibus = wishbone.Interface()
        self.dbus         = dbus = wishbone.Interface()
        self.periph_buses = [ibus, dbus]
        self.memory_buses = []

        # # #

        self.cpu_params = dict(
            # clock / reset
            i_clk   = ClockSignal(),
            i_i_rst = ResetSignal() | self.reset,

            # timer irq
            i_i_timer_irq = 0,

            # ibus
            o_o_ibus_adr = Cat(Signal(2), ibus.adr),
            o_o_ibus_cyc = ibus.cyc,
            i_i_ibus_rdt = ibus.dat_r,
            i_i_ibus_ack = ibus.ack,

            # dbus
            o_o_dbus_adr = Cat(Signal(2), dbus.adr),
            o_o_dbus_dat = dbus.dat_w,
            o_o_dbus_sel = dbus.sel,
            o_o_dbus_we  = dbus.we,
            o_o_dbus_cyc = dbus.cyc,
            i_i_dbus_rdt = dbus.dat_r,
            i_i_dbus_ack = dbus.ack,
        )
        self.comb += [
            ibus.stb.eq(ibus.cyc),
            ibus.sel.eq(0xf),
            dbus.stb.eq(dbus.cyc),
        ]

        # add verilog sources
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        self.cpu_params.update(p_RESET_PC=reset_address)

    @staticmethod
    def add_sources(platform):
        vdir = get_data_mod("cpu", "serv").data_location
        platform.add_source_dir(os.path.join(vdir, "rtl"))
        platform.add_verilog_include_path(os.path.join(vdir, "rtl"))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("serv_rf_top", **self.cpu_params)
