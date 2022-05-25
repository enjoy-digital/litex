#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard"]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                               /-------- Base ISA
    #                               |/------- Hardware Multiply + Divide
    #                               ||/----- Atomics
    #                               |||/---- Compressed ISA
    #                               ||||/--- Single-Precision Floating-Point
    #                               |||||/-- Double-Precision Floating-Point
    #                               imacfd
    "standard":         "-march=rv32i     -mabi=ilp32",
}

# NEORV32 ------------------------------------------------------------------------------------------

class NEORV32(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "neorv32"
    human_name           = "NEORV32"
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
        flags =  GCC_FLAGS[self.variant]
        flags += " -D__neorv32__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.ibus         = ibus = wishbone.Interface()
        self.dbus         = dbus = wishbone.Interface()
        self.periph_buses = [ibus, dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []           # Memory buses (Connected directly to LiteDRAM).

        # # #

        class Open(Signal) : pass

        # IBus Adaptations. FIXME: Works but not optimal (latency).
        ibus_we = Signal()
        ibus_re = Signal()
        self.sync += [
            # Clear Cyc/Stb on Ack.
            If(ibus.ack,
                ibus.cyc.eq(0),
                ibus.stb.eq(0),
            ),
            # Set Cyc/Stb on We/Re.
            If(ibus_we | ibus_re,
                ibus.cyc.eq(1),
                ibus.stb.eq(1),
                ibus.we.eq(ibus_we)
            )
        ]

        # DBus Adaptations. FIXME: Works but not optimal (latency).
        dbus_we = Signal()
        dbus_re = Signal()
        self.sync += [
            # Clear Cyc/Stb on Ack.
            If(dbus.ack,
                dbus.cyc.eq(0),
                dbus.stb.eq(0),
            ),
            # Set Cyc/Stb on We/Re.
            If(dbus_we | dbus_re,
                dbus.cyc.eq(1),
                dbus.stb.eq(1),
                dbus.we.eq(dbus_we)
            )
        ]

        # CPU Instance.
        self.specials += Instance("neorv32_cpu_wrapper",
            # Global Control.
            i_clk_i         = ClockSignal("sys"),
            i_rstn_i        = ~(ResetSignal() | self.reset),
            o_sleep_o       = Open(),
            o_debug_o       = Open(),
            i_db_halt_req_i = 0,

            # Instruction Bus.
            o_i_bus_addr_o  = Cat(Signal(2), ibus.adr),
            i_i_bus_rdata_i = ibus.dat_r,
            o_i_bus_wdata_o = ibus.dat_w,
            o_i_bus_ben_o   = ibus.sel,
            o_i_bus_we_o    = ibus_we,
            o_i_bus_re_o    = ibus_re,
            o_i_bus_lock_o  = Open(), # FIXME.
            i_i_bus_ack_i   = ibus.ack,
            i_i_bus_err_i   = ibus.err,
            o_i_bus_fence_o = Open(), # FIXME.
            o_i_bus_priv_o  = Open(), # FIXME.

            # Data Bus.
            o_d_bus_addr_o  = Cat(Signal(2), dbus.adr),
            i_d_bus_rdata_i = dbus.dat_r,
            o_d_bus_wdata_o = dbus.dat_w,
            o_d_bus_ben_o   = dbus.sel,
            o_d_bus_we_o    = dbus_we,
            o_d_bus_re_o    = dbus_re,
            o_d_bus_lock_o  = Open(), # FIXME.
            i_d_bus_ack_i   = dbus.ack,
            i_d_bus_err_i   = dbus.err,
            o_d_bus_fence_o = Open(), # FIXME.
            o_d_bus_priv_o  = Open(), # FIXME.

            # System Time.
            i_time_i        = 0, # FIXME.

            # Interrupts.
            i_msw_irq_i     = 0, # FIXME.
            i_mext_irq_i    = 0, # FIXME.
            i_mtime_irq_i   = 0, # FIXME.
            i_firq_i        = 0  # FIXME.
        )

        # Add Verilog sources
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        assert reset_address == 0x0000_0000

    @staticmethod
    def add_sources(platform):
        cdir = os.path.abspath(os.path.dirname(__file__))
        # List VHDL sources.
        sources = [
            "neorv32_package.vhd",                  # Main CPU & Processor package file.
            "neorv32_fifo.vhd",                     # FIFO.
            "neorv32_cpu.vhd",                      # CPU top entity.
                "neorv32_cpu_alu.vhd",              # Arithmetic/logic unit.
                    "neorv32_cpu_cp_bitmanip.vhd",  # Bit-manipulation co-processor.
                    "neorv32_cpu_cp_cfu.vhd",       # Custom instructions co-processor.
                    "neorv32_cpu_cp_fpu.vhd",       # Single-precision FPU co-processor.
                    "neorv32_cpu_cp_muldiv.vhd",    # Integer multiplier/divider co-processor.
                    "neorv32_cpu_cp_shifter.vhd",   # Base ISA shifter unit.
                "neorv32_cpu_bus.vhd",              # Instruction and data bus interface unit.
                "neorv32_cpu_control.vhd",          # CPU control and CSR system.
                    "neorv32_cpu_decompressor.vhd", # Compressed instructions decoder.
                "neorv32_cpu_regfile.vhd",          # Data register file.
            "neorv32_cpu_wrapper.vhd",              # CPU top entity + default generics.
        ]

        # Download VHDL sources (if not already present).
        for source in sources:
            if not os.path.exists(os.path.join(cdir, source)):
                os.system(f"wget https://raw.githubusercontent.com/stnolting/neorv32/main/rtl/core/{source} -P {cdir}")

        # Convert VHDL to Verilog through GHDL/Yosys.
        from litex.build import tools
        import subprocess
        cdir = os.path.dirname(__file__)
        ys = []
        ys.append("ghdl --ieee=synopsys -fexplicit -frelaxed-rules --std=08 --work=neorv32 \\")
        for source in sources:
            ys.append(os.path.join(cdir, source) + " \\")
        ys.append("-e neorv32_cpu_wrapper")
        ys.append("chformal -assert -remove")
        ys.append("write_verilog {}".format(os.path.join(cdir, "neorv32.v")))
        tools.write_to_file(os.path.join(cdir, "neorv32.ys"), "\n".join(ys))
        if subprocess.call(["yosys", "-q", "-m", "ghdl", os.path.join(cdir, "neorv32.ys")]):
            raise OSError("Unable to convert NEORV32 CPU to verilog, please check your GHDL-Yosys-plugin install.")
        platform.add_source(os.path.join(cdir, "neorv32.v"))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
