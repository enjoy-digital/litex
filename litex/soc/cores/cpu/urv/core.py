#
# This file is part of LiteX.
#
# Copyright (c) 2024 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex.soc.interconnect import stream

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = {
    "standard": "urv",
}

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                       /------------ Base ISA
    #                       |    /------- Hardware Multiply + Divide
    #                       |    |/----- Atomics
    #                       |    ||/---- Compressed ISA
    #                       |    |||/--- Single-Precision Floating-Point
    #                       |    ||||/-- Double-Precision Floating-Point
    #                       i    macfd
    "standard": "-march=rv32i2p0_m    -mabi=ilp32",
}

# uRV Instruction Bus To Wishbone ------------------------------------------------------------------

instruction_bus_layout = [
    ("addr", 32),
    ("rd",    1),
    ("data", 32),
    ("valid", 1)
]

class InstructionBusToWishbone(LiteXModule):
    def __init__(self, ibus, wb_ibus):
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(ibus.rd,
                NextValue(ibus.valid, 0),
                NextState("READ")
            )
        )
        fsm.act("READ",
            wb_ibus.stb.eq(1),
            wb_ibus.cyc.eq(1),
            wb_ibus.we.eq(0),
            wb_ibus.adr.eq(ibus.addr),
            wb_ibus.sel.eq(0b1111),
            If(wb_ibus.ack,
                NextValue(ibus.valid, 1),
                NextValue(ibus.data, wb_ibus.dat_r),
                NextState("IDLE")
            )
        )

# uRV ----------------------------------------------------------------------------------------------

class uRV(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "urv"
    human_name           = "urv"
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
        flags += " -D__urv__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.human_name   = f"uRV-{variant.upper()}"
        self.reset        = Signal()
        self.ibus         = ibus = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
        self.dbus         = dbus = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
        self.periph_buses = [ibus, dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []           # Memory buses (Connected directly to LiteDRAM).

        # uRV Signals.
        # ------------
        im_bus = Record(instruction_bus_layout)

        dm_addr        = Signal(32)
        dm_data_s      = Signal(32)
        dm_data_l      = Signal(32)
        dm_data_select = Signal(4)
        dm_store       = Signal()
        dm_load        = Signal()
        dm_load_done   = Signal()
        dm_store_done  = Signal()

        # uRV Instance.
        # -------------
        self.cpu_params = dict(
            # Parameters.
            p_g_timer_frequency       = 1000,      # FIXME.
            p_g_clock_frequency       = 100000000, # FIXME.
            p_g_with_hw_div           = 1,
            p_g_with_hw_mulh          = 1,
            p_g_with_hw_mul           = 1,
            p_g_with_hw_debug         = 0,
            p_g_with_ecc              = 0,
            p_g_with_compressed_insns = 0,

            # Clk / Rst.
            i_clk_i            = ClockSignal("sys"),
            i_rst_i            = ResetSignal("sys") | self.reset,

            # Instruction Mem Bus.
            o_im_addr_o        = im_bus.addr,
            o_im_rd_o          = im_bus.rd,
            i_im_data_i        = im_bus.data,
            i_im_valid_i       = im_bus.valid,

            # Data Mem Bus.
            o_dm_addr_o        = dm_addr,
            o_dm_data_s_o      = dm_data_s,
            i_dm_data_l_i      = dm_data_l,
            o_dm_data_select_o = dm_data_select,

            o_dm_store_o       = dm_store,
            o_dm_load_o        = dm_load,
            i_dm_load_done_i   = dm_load_done,
            i_dm_store_done_i  = dm_store_done,
        )

        # uRV Bus Adaptation.
        # -------------------
        self.submodules += InstructionBusToWishbone(im_bus, ibus)

        # uRV Data Bus.
        # -------------
        self.dm_fifo = dm_fifo = stream.SyncFIFO(
            layout = [("addr", 32), ("we", 1), ("data", 32), ("sel", 4)],
            depth = 16,
        )
        self.comb += [
            dm_fifo.sink.valid.eq(dm_store | dm_load),
            dm_fifo.sink.we.eq(dm_store),
            dm_fifo.sink.addr.eq(dm_addr),
            dm_fifo.sink.data.eq(dm_data_s),
            dm_fifo.sink.sel.eq(dm_data_select),
        ]
        self.dm_fsm = dm_fsm = FSM(reset_state="IDLE")
        dm_fsm.act("IDLE",
            If(dm_fifo.source.valid,
                If(dm_fifo.source.we,
                    NextState("WRITE")
                ).Else(
                    NextState("READ")
                )
            )
        )
        dm_fsm.act("WRITE",
            dbus.stb.eq(1),
            dbus.cyc.eq(1),
            dbus.we.eq(1),
            dbus.adr.eq(dm_fifo.source.addr),
            dbus.sel.eq(dm_fifo.source.sel),
            dbus.dat_w.eq(dm_fifo.source.data),
            If(dbus.ack,
                dm_fifo.source.ready.eq(1),
                dm_store_done.eq(1),
                NextState("IDLE")
            )
        )
        dm_fsm.act("READ",
            dbus.stb.eq(1),
            dbus.cyc.eq(1),
            dbus.we.eq(0),
            dbus.adr.eq(dm_fifo.source.addr),
            dbus.sel.eq(dm_fifo.source.sel),
            If(dbus.ack,
                dm_fifo.source.ready.eq(1),
                dm_load_done.eq(1),
                dm_data_l.eq(dbus.dat_r),
                NextState("IDLE")
            )
        )

        # Add Verilog sources.
        # --------------------
        self.add_sources(platform, variant)

    def set_reset_address(self, reset_address):
        assert reset_address == 0
        self.reset_address = reset_address

    @staticmethod
    def add_sources(platform, variant):
        if not os.path.exists("urv-core"):
            os.system(f"git clone https://ohwr.org/project/urv-core/")
        platform.add_verilog_include_path("urv-core/rtl")
        platform.add_sources("urv-core/rtl",
            "urv_cpu.v",
            "urv_exec.v",
            "urv_fetch.v",
            "urv_decode.v",
            "urv_regfile.v",
            "urv_writeback.v",
            "urv_shifter.v",
            "urv_multiply.v",
            "urv_divide.v",
            "urv_csr.v",
            "urv_timer.v",
            "urv_exceptions.v",
            "urv_iram.v",
            "urv_ecc.v",
        )

    def do_finalize(self):
        self.specials += Instance("urv_cpu", **self.cpu_params)
