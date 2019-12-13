# This file is Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import os
import subprocess

from migen import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU

CPU_VARIANTS = ["standard"]


class Minerva(CPU):
    name                 = "minerva"
    data_width           = 32
    endianness           = "little"
    gcc_triple           = ("riscv64-unknown-elf", "riscv32-unknown-elf", "riscv-none-embed")
    linker_output_format = "elf32-littleriscv"
    io_regions           = {0x80000000: 0x80000000} # origin, length

    @property
    def gcc_flags(self):
        flags =  "-march=rv32im "
        flags += "-mabi=ilp32 "
        flags += "-D__minerva__ "
        return flags

    def __init__(self, platform, variant="standard"):
        assert variant is "standard", "Unsupported variant %s" % variant
        self.platform  = platform
        self.variant   = variant
        self.reset     = Signal()
        self.ibus      = wishbone.Interface()
        self.dbus      = wishbone.Interface()
        self.buses     = [self.ibus, self.dbus]
        self.interrupt = Signal(32)

        # TODO: create variants
        self.with_icache = False
        self.with_dcache = False
        self.with_muldiv = True

        # # #

        self.cpu_params = dict(
            # clock / reset
            i_clk=ClockSignal(),
            i_rst=ResetSignal() | self.reset,

            # interrupts
            i_timer_interrupt    = 0,
            i_software_interrupt = 0,
            i_external_interrupt = self.interrupt,

            # ibus
            o_ibus__stb   = self.ibus.stb,
            o_ibus__cyc   = self.ibus.cyc,
            o_ibus__cti   = self.ibus.cti,
            o_ibus__bte   = self.ibus.bte,
            o_ibus__we    = self.ibus.we,
            o_ibus__adr   = self.ibus.adr,
            o_ibus__dat_w = self.ibus.dat_w,
            o_ibus__sel   = self.ibus.sel,
            i_ibus__ack   = self.ibus.ack,
            i_ibus__err   = self.ibus.err,
            i_ibus__dat_r = self.ibus.dat_r,

            # dbus
            o_dbus__stb   = self.dbus.stb,
            o_dbus__cyc   = self.dbus.cyc,
            o_dbus__cti   = self.dbus.cti,
            o_dbus__bte   = self.dbus.bte,
            o_dbus__we    = self.dbus.we,
            o_dbus__adr   = self.dbus.adr,
            o_dbus__dat_w = self.dbus.dat_w,
            o_dbus__sel   = self.dbus.sel,
            i_dbus__ack   = self.dbus.ack,
            i_dbus__err   = self.dbus.err,
            i_dbus__dat_r = self.dbus.dat_r,
        )

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address

    @staticmethod
    def elaborate(reset_address, with_icache, with_dcache, with_muldiv, verilog_filename):
        cli_params = []
        cli_params.append("--reset-addr={}".format(reset_address))
        if with_icache:
            cli_params.append("--with-icache")
        if with_dcache:
            cli_params.append("--with-dcache")
        if with_muldiv:
            cli_params.append("--with-muldiv")
        _dir = os.path.abspath(os.path.dirname(__file__))
        if subprocess.call(["python3", os.path.join(_dir, "verilog", "cli.py"), *cli_params, "generate"],
            stdout=open(verilog_filename, "w")):
            raise OSError("Unable to elaborate Minerva CPU, please check your nMigen/Yosys install")

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        verilog_filename = os.path.join(self.platform.output_dir, "gateware", "minerva.v")
        self.elaborate(
            reset_address    = self.reset_address,
            with_icache      = self.with_icache,
            with_dcache      = self.with_dcache,
            with_muldiv      = self.with_muldiv,
            verilog_filename = verilog_filename)
        self.platform.add_source(verilog_filename)
        self.specials += Instance("minerva_cpu", **self.cpu_params)
