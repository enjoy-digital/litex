#
# This file is part of LiteX.
#
# Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.build.amaranth2v_converter import Amaranth2VConverter
from litex.soc.cores.cpu.amaranth import check_required_modules, import_from_pythondata
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard"]

# Minerva ------------------------------------------------------------------------------------------

class Minerva(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "minerva"
    human_name           = "Minerva"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x8000_0000: 0x8000_0000} # Origin, Length.

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  "-march=rv32i2p0_m "
        flags += "-mabi=ilp32 "
        flags += "-D__minerva__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.interrupt    = Signal(16)
        self.ibus         = wishbone.Interface(data_width=32, address_width=32, addressing="word")
        self.dbus         = wishbone.Interface(data_width=32, address_width=32, addressing="word")
        self.periph_buses = [self.ibus, self.dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []                     # Memory buses (Connected directly to LiteDRAM).

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        check_required_modules({
            "amaranth": "pip3 install --user amaranth==0.5.8",
            "amaranth_soc": "pip3 install --user git+https://github.com/amaranth-lang/amaranth-soc.git",
        })

        minerva_core = import_from_pythondata("cpu", "minerva", "minerva.core")
        amaranth_cpu = minerva_core.Minerva(
            reset_address = self.reset_address,
            with_icache   = True,
            with_dcache   = True,
            with_muldiv   = True,
        )

        self.converter = Amaranth2VConverter(self.platform,
            name        = "minerva_cpu",
            module      = amaranth_cpu,
            ports       = dict(
                # Clk / Rst.
                i_sync_clk = ClockSignal("sys"),
                i_sync_rst = ResetSignal("sys") | self.reset,

                # IRQ.
                i_timer_interrupt    = 0,
                i_software_interrupt = 0,
                i_external_interrupt = 0,
                i_fast_interrupt     = self.interrupt,

                # Ibus.
                o_ibus_stb   = self.ibus.stb,
                o_ibus_cyc   = self.ibus.cyc,
                o_ibus_cti   = self.ibus.cti,
                o_ibus_bte   = self.ibus.bte,
                o_ibus_we    = self.ibus.we,
                o_ibus_adr   = self.ibus.adr,
                o_ibus_dat_w = self.ibus.dat_w,
                o_ibus_sel   = self.ibus.sel,
                i_ibus_ack   = self.ibus.ack,
                i_ibus_err   = self.ibus.err,
                i_ibus_dat_r = self.ibus.dat_r,

                # Dbus.
                o_dbus_stb   = self.dbus.stb,
                o_dbus_cyc   = self.dbus.cyc,
                o_dbus_cti   = self.dbus.cti,
                o_dbus_bte   = self.dbus.bte,
                o_dbus_we    = self.dbus.we,
                o_dbus_adr   = self.dbus.adr,
                o_dbus_dat_w = self.dbus.dat_w,
                o_dbus_sel   = self.dbus.sel,
                i_dbus_ack   = self.dbus.ack,
                i_dbus_err   = self.dbus.err,
                i_dbus_dat_r = self.dbus.dat_r,
            ),
        )
