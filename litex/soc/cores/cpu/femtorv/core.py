#
# This file is part of LiteX.
#
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard"]

# FemtoRV ------------------------------------------------------------------------------------------

class FemtoRV(CPU):
    family               = "riscv"
    name                 = "femtorv"
    human_name           = "FemtoRV"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x80000000: 0x80000000} # Origin, Length.

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  "-march=rv32i "
        flags += "-mabi=ilp32 "
        flags += "-D__femtorv__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.idbus        = idbus = wishbone.Interface()
        self.periph_buses = [idbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []      # Memory buses (Connected directly to LiteDRAM).

        # # #

        # FemtoRV Mem Bus.
        # ----------------
        mbus = Record([
            ("addr",  32),
            ("wdata", 32),
            ("wmask",  4),
            ("rdata", 32),
            ("rstrb",  1),
            ("rbusy",  1),
            ("wbusy",  1),
        ])

        # FemtoRV Instance.
        # -----------------
        self.cpu_params = dict(
            # Parameters.
            p_ADDR_WIDTH = 32,
            p_RESET_ADDR = Constant(0, 32),

            # Clk / Rst.
            i_clk   = ClockSignal("sys"),
            i_reset = ~ResetSignal("sys"), # Active Low.

            # I/D Bus.
            o_mem_addr  = mbus.addr,
            o_mem_wdata = mbus.wdata,
            o_mem_wmask = mbus.wmask,
            i_mem_rdata = mbus.rdata,
            o_mem_rstrb = mbus.rstrb,
            i_mem_rbusy = mbus.rbusy,
            i_mem_wbusy = mbus.wbusy,
        )

        # Adapt FemtoRV Mem Bus to Wishbone.
        # ----------------------------------

        # Bytes to Words addressing conversion.
        self.comb += idbus.adr.eq(mbus.addr[2:])

        # Wdata/WMask direct connection.
        self.comb += idbus.dat_w.eq(mbus.wdata)
        self.comb += idbus.sel.eq(mbus.wmask)

        # Control adaptation.
        latch = Signal()
        write = mbus.wmask != 0
        read  = mbus.rstrb

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            idbus.stb.eq(read | write),
            idbus.cyc.eq(read | write),
            idbus.we.eq(write),
            If(read,
                mbus.rbusy.eq(1),
                NextState("READ")
            ).Elif(write,
                mbus.wbusy.eq(1),
                NextState("WRITE")
            )
        )
        fsm.act("READ",
            idbus.stb.eq(1),
            idbus.cyc.eq(1),
            mbus.rbusy.eq(1),
            If(idbus.ack,
                latch.eq(1),
                NextState("IDLE")
            )
        )
        fsm.act("WRITE",
            idbus.stb.eq(1),
            idbus.cyc.eq(1),
            idbus.we.eq(1),
            mbus.wbusy.eq(1),
            If(idbus.ack,
                NextState("IDLE")
            )
        )

        # Latch RData on Wishbone ack.
        self.sync += If(latch, mbus.rdata.eq(idbus.dat_r))

        # Add Verilog sources.
        # --------------------
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        self.cpu_params.update(p_RESET_ADDR=Constant(reset_address, 32))

    @staticmethod
    def add_sources(platform):
        if not os.path.exists("femtorv32_quark.v"):
            # Get FemtoRV32 source.
            os.system("wget https://raw.githubusercontent.com/BrunoLevy/learn-fpga/master/FemtoRV/RTL/PROCESSOR/femtorv32_quark.v")
        platform.add_source("femtorv32_quark.v")

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("FemtoRV32", **self.cpu_params)
