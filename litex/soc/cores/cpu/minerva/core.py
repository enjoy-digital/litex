#
# This file is part of LiteX.
#
# Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
from pathlib import Path
import shutil
import subprocess

from migen import *

from litex.gen import *

from litex import get_data_mod
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
    clint_addr           = 0x0200_0000
    clic_addr            = 0x0C00_0000

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
        self.timer_interrupt = Signal()    # Timer interrupt from CLINT
        self.software_interrupt = Signal() # Software interrupt from CLINT
        # CLIC interrupt signals
        self.clic_interrupt = Signal()     # CLIC interrupt request
        self.clic_interrupt_id = Signal(12)  # CLIC interrupt ID (up to 4096 interrupts)
        self.clic_interrupt_priority = Signal(8)  # CLIC interrupt priority
        self.clic_claim = Signal()         # CLIC claim output
        self.clic_threshold = Signal(8)    # CLIC threshold output
        self.ibus         = ibus = wishbone.Interface(data_width=32, address_width=32, addressing="word")
        self.dbus         = dbus = wishbone.Interface(data_width=32, address_width=32, addressing="word")
        self.periph_buses = [self.ibus, self.dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []                     # Memory buses (Connected directly to LiteDRAM).

        # # #

        self.cpu_params = dict(
            # Clk / Rst.
            i_clk = ClockSignal("sys"),
            i_rst = ResetSignal("sys") | self.reset,

            # IRQ.
            i_timer_interrupt    = self.timer_interrupt,
            i_software_interrupt = self.software_interrupt,
            i_external_interrupt = 0,
            i_fast_interrupt = self.interrupt,
            
            # CLIC.
            i_clic_interrupt          = self.clic_interrupt,
            i_clic_interrupt_id       = self.clic_interrupt_id,
            i_clic_interrupt_priority = self.clic_interrupt_priority,

            # Ibus.
            o_ibus__stb   = ibus.stb,
            o_ibus__cyc   = ibus.cyc,
            o_ibus__cti   = ibus.cti,
            o_ibus__bte   = ibus.bte,
            o_ibus__we    = ibus.we,
            o_ibus__adr   = ibus.adr,
            o_ibus__dat_w = ibus.dat_w,
            o_ibus__sel   = ibus.sel,
            i_ibus__ack   = ibus.ack,
            i_ibus__err   = ibus.err,
            i_ibus__dat_r = ibus.dat_r,

            # Dbus.
            o_dbus__stb   = dbus.stb,
            o_dbus__cyc   = dbus.cyc,
            o_dbus__cti   = dbus.cti,
            o_dbus__bte   = dbus.bte,
            o_dbus__we    = dbus.we,
            o_dbus__adr   = dbus.adr,
            o_dbus__dat_w = dbus.dat_w,
            o_dbus__sel   = dbus.sel,
            i_dbus__ack   = dbus.ack,
            i_dbus__err   = dbus.err,
            i_dbus__dat_r = dbus.dat_r,
        )

    def add_soc_components(self, soc):
        # CLIC and CLINT are mutually exclusive
        # Only add when explicitly requested via command line flags
        # When no flags are specified, nothing should be added
        pass

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address

    @staticmethod
    def elaborate(reset_address, with_icache, with_dcache, with_muldiv, verilog_filename):
        pipx_or_pdm = shutil.which("pipx") or shutil.which("pdm")

        if not pipx_or_pdm:
            raise OSError("Unable to elaborate Minerva CPU. Make sure \"pipx\" or \"pdm\" is installed.")

        cli_params = []
        cli_params.append("--reset-addr={}".format(reset_address))
        if with_icache:
            cli_params.append("--with-icache")
        if with_dcache:
            cli_params.append("--with-dcache")
        if with_muldiv:
            cli_params.append("--with-muldiv")
        cli_params.append("generate")
        cli_params.append("--type=v")

        this_dir = Path(__file__).resolve().parent
        sdir = get_data_mod("cpu", "minerva").data_location

        if subprocess.call([pipx_or_pdm, "run", this_dir / "minerva-pep-723.py", *cli_params],
                            stdout=open(verilog_filename, "w"),
                            cwd=sdir):
            raise OSError("Unable to elaborate Minerva CPU, please check your Amaranth/Yosys install")

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        verilog_filename = os.path.join(self.platform.output_dir, "gateware", "minerva.v")
        self.elaborate(
            reset_address    = self.reset_address,
            with_icache      = True,
            with_dcache      = True,
            with_muldiv      = True,
            verilog_filename = verilog_filename)
        self.platform.add_source(verilog_filename)
        self.specials += Instance("minerva_cpu", **self.cpu_params)
