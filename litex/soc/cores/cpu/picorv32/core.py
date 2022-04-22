#
# This file is part of LiteX.
#
# Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2018 Sergiusz Bazanski <q3k@q3k.org>
# Copyright (c) 2019 Antmicro <www.antmicro.com>
# Copyright (c) 2019 Tim 'mithro' Ansell <me@mith.ro>
# Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["minimal", "standard"]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                               /-------- Base ISA
    #                               |/------- Hardware Multiply + Divide
    #                               ||/----- Atomics
    #                               |||/---- Compressed ISA
    #                               ||||/--- Single-Precision Floating-Point
    #                               |||||/-- Double-Precision Floating-Point
    #                               imacfd
    "minimal":          "-march=rv32i      -mabi=ilp32 ",
    "standard":         "-march=rv32im     -mabi=ilp32 ",
}

# PicoRV32 -----------------------------------------------------------------------------------------

class PicoRV32(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "picorv32"
    human_name           = "PicoRV32"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x80000000: 0x80000000} # origin, length

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  "-mno-save-restore "
        flags += GCC_FLAGS[self.variant]
        flags += "-D__picorv32__ "
        return flags

    # Reserved Interrupts.
    @property
    def reserved_interrupts(self):
        return {
            "timer":                0,
            "ebreak_ecall_illegal": 1,
            "bus_error":            2
        }

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.trap         = Signal()
        self.reset        = Signal()
        self.interrupt    = Signal(32)
        self.idbus        = idbus = wishbone.Interface()
        self.periph_buses = [idbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []      # Memory buses (Connected directly to LiteDRAM).

        # # #

        mem_valid = Signal()
        mem_instr = Signal()
        mem_ready = Signal()
        mem_addr  = Signal(32)
        mem_wdata = Signal(32)
        mem_wstrb = Signal(4)
        mem_rdata = Signal(32)

        # PicoRV32 parameters, change the desired parameters to create a create a new variant.
        self.cpu_params = dict(
            p_ENABLE_COUNTERS      = 1,
            p_ENABLE_COUNTERS64    = 1,
            p_ENABLE_REGS_16_31    = 1, # Changing REGS has no effect as on FPGAs, the regs are
            p_ENABLE_REGS_DUALPORT = 1, # implemented using a register file stored in DPRAM.
            p_LATCHED_MEM_RDATA    = 0,
            p_TWO_STAGE_SHIFT      = 1,
            p_TWO_CYCLE_COMPARE    = 0,
            p_TWO_CYCLE_ALU        = 0,
            p_CATCH_MISALIGN       = 1,
            p_CATCH_ILLINSN        = 1,
            p_ENABLE_PCPI          = 0,
            p_ENABLE_MUL           = 1,
            p_ENABLE_DIV           = 1,
            p_ENABLE_FAST_MUL      = 0,
            p_ENABLE_IRQ           = 1,
            p_ENABLE_IRQ_QREGS     = 1,
            p_ENABLE_IRQ_TIMER     = 1,
            p_ENABLE_TRACE         = 0,
            p_MASKED_IRQ           = 0x00000000,
            p_LATCHED_IRQ          = 0xffffffff,
            p_STACKADDR            = 0xffffffff,
        )

        # Enforce default parameters for Minimal variant.
        if variant == "minimal":
            self.cpu_params.update(
                p_ENABLE_COUNTERS   = 0,
                p_ENABLE_COUNTERS64 = 0,
                p_TWO_STAGE_SHIFT   = 0,
                p_CATCH_MISALIGN    = 0,
                p_ENABLE_MUL        = 0,
                p_ENABLE_DIV        = 0,
                p_ENABLE_IRQ_TIMER  = 0,
            )

        self.cpu_params.update(
            # Clk / Rst.
            i_clk    = ClockSignal("sys"),
            i_resetn = ~(ResetSignal("sys") | self.reset),

            # Trap.
            o_trap = self.trap,

            # Memory Interface.
            o_mem_valid = mem_valid,
            o_mem_instr = mem_instr,
            i_mem_ready = mem_ready,

            o_mem_addr  = mem_addr,
            o_mem_wdata = mem_wdata,
            o_mem_wstrb = mem_wstrb,
            i_mem_rdata = mem_rdata,

            # Look Ahead Interface (not used).
            o_mem_la_read  = Signal(),
            o_mem_la_write = Signal(),
            o_mem_la_addr  = Signal(32),
            o_mem_la_wdata = Signal(32),
            o_mem_la_wstrb = Signal(4),

            # Co-Processor interface (not used).
            o_pcpi_valid = Signal(),
            o_pcpi_insn  = Signal(32),
            o_pcpi_rs1   = Signal(32),
            o_pcpi_rs2   = Signal(32),
            i_pcpi_wr    = 0,
            i_pcpi_rd    = 0,
            i_pcpi_wait  = 0,
            i_pcpi_ready = 0,

            # IRQ interface.
            i_irq = self.interrupt,
            o_eoi = Signal(32)) # not used

        # Adapt Memory Interface to Wishbone.
        self.comb += [
            idbus.adr.eq(mem_addr[2:]),
            idbus.dat_w.eq(mem_wdata),
            idbus.we.eq(mem_wstrb != 0),
            idbus.sel.eq(mem_wstrb),
            idbus.cyc.eq(mem_valid),
            idbus.stb.eq(mem_valid),
            idbus.cti.eq(0),
            idbus.bte.eq(0),
            mem_ready.eq(idbus.ack),
            mem_rdata.eq(idbus.dat_r),
        ]

        # Add Verilog sources
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(
            p_PROGADDR_RESET = reset_address,
            p_PROGADDR_IRQ   = reset_address + 0x00000010
        )

    @staticmethod
    def add_sources(platform):
        vdir = get_data_mod("cpu", "picorv32").data_location
        platform.add_source(os.path.join(vdir, "picorv32.v"))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("picorv32", **self.cpu_params)
