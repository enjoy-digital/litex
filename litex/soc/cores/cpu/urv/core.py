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

# uRV Data Bus To Wishbone -------------------------------------------------------------------------

data_bus_layout = [
    ("addr",      32),
    ("data_s",    32),
    ("data_l",    32),
    ("sel",        4),
    ("store",      1),
    ("load",       1),
    ("load_done",  1),
    ("store_done", 1)
]

class DataBusToWishbone(LiteXModule):
    def __init__(self, dbus, wb_dbus):
        self.fifo = fifo = stream.SyncFIFO(
            layout=[("addr", 32), ("we", 1), ("data", 32), ("sel", 4)],
            depth=16,
        )
        self.comb += [
            fifo.sink.valid.eq(dbus.store | dbus.load),
            fifo.sink.we.eq(dbus.store),
            fifo.sink.addr.eq(dbus.addr),
            fifo.sink.data.eq(dbus.data_s),
            fifo.sink.sel.eq(dbus.sel),
        ]

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(fifo.source.valid,
                If(fifo.source.we,
                    NextState("WRITE")
                ).Else(
                    NextState("READ")
                )
            )
        )
        fsm.act("WRITE",
            wb_dbus.stb.eq(1),
            wb_dbus.cyc.eq(1),
            wb_dbus.we.eq(1),
            wb_dbus.adr.eq(fifo.source.addr),
            wb_dbus.sel.eq(fifo.source.sel),
            wb_dbus.dat_w.eq(fifo.source.data),
            If(wb_dbus.ack,
                fifo.source.ready.eq(1),
                dbus.store_done.eq(1),
                NextState("IDLE")
            )
        )
        fsm.act("READ",
            wb_dbus.stb.eq(1),
            wb_dbus.cyc.eq(1),
            wb_dbus.we.eq(0),
            wb_dbus.adr.eq(fifo.source.addr),
            wb_dbus.sel.eq(fifo.source.sel),
            If(wb_dbus.ack,
                fifo.source.ready.eq(1),
                dbus.load_done.eq(1),
                dbus.data_l.eq(wb_dbus.dat_r),
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

        # uRV Buses.
        # ----------
        im_bus = Record(instruction_bus_layout)
        dm_bus = Record(data_bus_layout)

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
            o_dm_addr_o        = dm_bus.addr,
            o_dm_data_s_o      = dm_bus.data_s,
            i_dm_data_l_i      = dm_bus.data_l,
            o_dm_data_select_o = dm_bus.sel,

            o_dm_store_o       = dm_bus.store,
            o_dm_load_o        = dm_bus.load,
            i_dm_load_done_i   = dm_bus.load_done,
            i_dm_store_done_i  = dm_bus.store_done,
        )

        # uRV Bus Adaptation.
        # -------------------
        self.submodules += InstructionBusToWishbone(im_bus, ibus)
        self.submodules += DataBusToWishbone(dm_bus, dbus)

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
