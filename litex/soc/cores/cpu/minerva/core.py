import os

from migen import *

from litex.soc.interconnect import wishbone


class Minerva(Module):
    name = "minerva"
    endianness = "little"
    gcc_triple = ("riscv64-unknown-elf", "riscv32-unknown-elf")
    gcc_flags = "-march=rv32i -mabi=ilp32" + " -D__minerva__"
    linker_output_format = "elf32-littleriscv"

    def __init__(self, platform, cpu_reset_address, variant="standard"):
        assert variant is "standard", "Unsupported variant %s" % variant
        self.reset = Signal()
        self.ibus = wishbone.Interface()
        self.dbus = wishbone.Interface()
        self.interrupt = Signal(32)

        # # #

        self.specials += Instance("minerva_cpu",
            # clock / reset
            i_clk=ClockSignal(),
            i_rst=ResetSignal(),

            # interrupts
            i_external_interrupt=self.interrupt,

            # ibus
            o_ibus_stb=self.ibus.stb,
            o_ibus_cyc=self.ibus.cyc,
            o_ibus_cti=self.ibus.cti,
            o_ibus_bte=self.ibus.bte,
            o_ibus_we=self.ibus.we,
            o_ibus_adr=self.ibus.adr,
            o_ibus_dat_w=self.ibus.dat_w,
            o_ibus_sel=self.ibus.sel,
            i_ibus_ack=self.ibus.ack,
            i_ibus_err=self.ibus.err,
            i_ibus_dat_r=self.ibus.dat_r,

            # dbus
            o_dbus_stb=self.dbus.stb,
            o_dbus_cyc=self.dbus.cyc,
            o_dbus_cti=self.dbus.cti,
            o_dbus_bte=self.dbus.bte,
            o_dbus_we=self.dbus.we,
            o_dbus_adr=self.dbus.adr,
            o_dbus_dat_w=self.dbus.dat_w,
            o_dbus_sel=self.dbus.sel,
            i_dbus_ack=self.dbus.ack,
            i_dbus_err=self.dbus.err,
            i_dbus_dat_r=self.dbus.dat_r,
        )

        # add verilog sources
        self.add_sources(platform)

    @staticmethod
    def add_sources(platform):
        vdir = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "verilog")
        platform.add_source(os.path.join(vdir, "minerva.v"))
