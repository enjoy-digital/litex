# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>

# License: BSD

import os

from migen import *

from litex.soc.interconnect import wishbone

CPU_VARIANTS = ["standard"]


class SERV(Module):
    @property
    def name(self):
        return "serv"

    @property
    def endianness(self):
        return "little"

    @property
    def gcc_triple(self):
        return ("riscv64-unknown-elf", "riscv32-unknown-elf")

    @property
    def gcc_flags(self):
        flags =  "-march=rv32i "
        flags += "-mabi=ilp32 "
        flags += "-D__serv__ "
        return flags

    @property
    def linker_output_format(self):
        return "elf32-littleriscv"

    @property
    def reserved_interrupts(self):
        return {}

    def __init__(self, platform, variant="standard"):
        assert variant is "standard", "Unsupported variant %s" % variant
        self.platform  = platform
        self.variant   = variant
        self.reset     = Signal()
        self.ibus      = wishbone.Interface()
        self.dbus      = wishbone.Interface()
        self.interrupt = Signal(32)

        # # #

        self.cpu_params -= dict(
            # clock / reset
            i_clk   = ClockSignal(),
            i_i_rst = ResetSignal(),

            # timer irq
            i_i_timer_irq = 0,

            # ibus
            o_o_ibus_adr = self.ibus.adr,
            o_o_ibus_cyc = self.ibus.cyc,
            i_i_ibus_rdt = self.ibus.dat_r,
            i_i_ibus_ack = self.ibus.ack,


            # dbus
            o_o_dbus_adr = self.dbus.adr,
            o_o_dbus_dat = self.dbus.dat_w,
            o_o_dbus_sel = self.dbus.sel,
            o_o_dbus_we  = self.dbus.we,
            o_o_dbus_cyc = self.dbus.cyc,
            i_i_dbus_rdt = self.dbus.dat_r,
            i_i_dbus_ack = self.dbus.ack,
        )
        self.comb += [
            self.ibus.stb.eq(self.ibus.cyc),
            self.dbus.stb.eq(self.dbus.cyc),
        ]

        # add verilog sources
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        self.cpu_params.update(p_RESET_PC=reset_address)

    @staticmethod
    def add_sources(platform):
        vdir = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            "verilog", "rtl")
        platform.add_source_dir(vdir)
        platform.add_verilog_include_path(vdir)

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("serv_top", **self.cpu_params)
