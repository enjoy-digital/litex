#
# This file is part of LiteX.
#
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard"]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                       /------------ Base ISA
    #                       |    /------- Hardware Multiply + Divide
    #                       |    |/----- Atomics
    #                       |    ||/---- Compressed ISA
    #                       |    |||/--- Single-Precision Floating-Point
    #                       |    ||||/-- Double-Precision Floating-Point
    #                       i    macfd
    "standard": "-march=rv32i2p0_mc    -mabi=ilp32 ",
}

# OBI <> Wishbone ----------------------------------------------------------------------------------

obi_layout = [
    ("req",    1),
    ("gnt",    1),
    ("addr",  32),
    ("we",     1),
    ("be",     4),
    ("wdata", 32),
    ("rvalid", 1),
    ("rdata", 32),
]

class OBI2Wishbone(Module):
    def __init__(self, obi, wb):
        addr  = Signal.like(obi.addr)
        be    = Signal.like(obi.be)
        we    = Signal.like(obi.we)
        wdata = Signal.like(obi.wdata)

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            # On OBI request:
            If(obi.req,
                # Drive Wishbone bus from OBI bus.
                wb.adr.eq(obi.addr[2:32]),
                wb.stb.eq(            1),
                wb.dat_w.eq(  obi.wdata),
                wb.cyc.eq(            1),
                wb.sel.eq(       obi.be),
                wb.we.eq(        obi.we),

                # Store OBI bus values.
                NextValue(addr,  obi.addr),
                NextValue(be,    obi.be),
                NextValue(we,    obi.we),
                NextValue(wdata, obi.wdata),

                # Now we need to wait Wishbone Ack.
                NextState("ACK")
            ),
            obi.gnt.eq(1), # Always ack OBI request in Idle.
        )
        fsm.act("ACK",
            # Drive Wishbone bus from stored OBI bus values.
            wb.adr.eq(addr[2:32]),
            wb.stb.eq(         1),
            wb.dat_w.eq(   wdata),
            wb.cyc.eq(         1),
            wb.sel.eq(        be),
            wb.we.eq(         we),

            # On Wishbone Ack:
            If(wb.ack,
                # Generate OBI response.
                obi.rvalid.eq(1),
                obi.rdata.eq(wb.dat_r),

                # Return to Idle.
                NextState("IDLE")
            )
        )

# Ibex ---------------------------------------------------------------------------------------------

class Ibex(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "ibex"
    human_name           = "Ibex"
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
        flags = GCC_FLAGS[self.variant]
        flags += "-D__ibex__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.ibus         = wishbone.Interface()
        self.dbus         = wishbone.Interface()
        self.periph_buses = [self.ibus, self.dbus]
        self.memory_buses = []
        self.interrupt    = Signal(15)

        ibus = Record(obi_layout)
        dbus = Record(obi_layout)

        # OBI <> Wishbone.
        self.ibus_conv = OBI2Wishbone(ibus, self.ibus)
        self.dbus_conv = OBI2Wishbone(dbus, self.dbus)

        self.comb += [
            ibus.we.eq(0),
            ibus.be.eq(1111),
        ]

        self.cpu_params = dict(
            # Configuration.
            p_RegFile        = 1, # RegFileFPGA
            i_test_en_i      = 0,
            i_hart_id_i      = 0,

            # Clk/Rst.
            i_clk_i          = ClockSignal("sys"),
            i_rst_ni         = ~ResetSignal("sys"),

            # Instruction bus.
            o_instr_req_o    = ibus.req,
            i_instr_gnt_i    = ibus.gnt,
            i_instr_rvalid_i = ibus.rvalid,
            o_instr_addr_o   = ibus.addr,
            i_instr_rdata_i  = ibus.rdata,
            i_instr_err_i    = 0,

            # Data bus.
            o_data_req_o     = dbus.req,
            i_data_gnt_i     = dbus.gnt,
            i_data_rvalid_i  = dbus.rvalid,
            o_data_we_o      = dbus.we,
            o_data_be_o      = dbus.be,
            o_data_addr_o    = dbus.addr,
            o_data_wdata_o   = dbus.wdata,
            i_data_rdata_i   = dbus.rdata,
            i_data_err_i     = 0,

            # Interrupts.
            i_irq_software_i = 0,
            i_irq_timer_i    = 0,
            i_irq_external_i = 0,
            i_irq_fast_i     = self.interrupt,
            i_irq_nm_i       = 0,

            # Debug.
            i_debug_req_i    = 0,

            # Control/Status.
            i_fetch_enable_i = 1,
            o_alert_minor_o  = Open(),
            o_alert_major_o  = Open(),
            o_core_sleep_o   = Open()
        )

        # Add Verilog sources
        self.add_sources(platform)

    @staticmethod
    def add_sources(platform):
        ibexdir = get_data_mod("cpu", "ibex").data_location
        platform.add_verilog_include_path(os.path.join(ibexdir, "rtl"))
        platform.add_verilog_include_path(os.path.join(ibexdir,
            "vendor", "lowrisc_ip", "dv", "sv", "dv_utils")
        )
        platform.add_verilog_include_path(os.path.join(ibexdir,
            "vendor", "lowrisc_ip", "ip", "prim", "rtl")
        )
        platform.add_source(os.path.join(ibexdir, "syn", "rtl", "prim_clock_gating.v"))
        platform.add_sources(os.path.join(ibexdir, "vendor", "lowrisc_ip", "ip", "prim", "rtl"),
            "prim_alert_pkg.sv",
            "prim_assert.sv",
            "prim_ram_1p_pkg.sv",
        )
        platform.add_sources(os.path.join(ibexdir, "rtl"),
            "ibex_pkg.sv",
            "ibex_alu.sv",
            "ibex_compressed_decoder.sv",
            "ibex_controller.sv",
            "ibex_counter.sv",
            "ibex_cs_registers.sv",
            "ibex_csr.sv",
            "ibex_decoder.sv",
            "ibex_ex_block.sv",
            "ibex_id_stage.sv",
            "ibex_if_stage.sv",
            "ibex_load_store_unit.sv",
            "ibex_multdiv_slow.sv",
            "ibex_multdiv_fast.sv",
            "ibex_prefetch_buffer.sv",
            "ibex_fetch_fifo.sv",
            "ibex_register_file_fpga.sv",
            "ibex_wb_stage.sv",
            "ibex_core.sv",
            "ibex_top.sv"
        )

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(i_boot_addr_i=Signal(32, reset=reset_address))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("ibex_top", **self.cpu_params)
