#
# This file is part of LiteX.
#
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re

from migen import *
from migen.fhdl.specials import Tristate

from litex import get_data_mod
from litex.soc.interconnect import wishbone, stream
from litex.soc.interconnect.csr import *
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard", "full"]

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
    "full":     "-march=rv32i2p0_mfc   -mabi=ilp32 ",
}

# OBI / APB / Trace Layouts ------------------------------------------------------------------------

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

apb_layout = [
    ("paddr",  32),
    ("pwdata", 32),
    ("pwrite",  1),
    ("psel",    1),
    ("penable", 1),
    ("prdata", 32),
    ("pready",  1),
    ("pslverr", 1),
]

trace_layout = [
    ("ivalid",     1),
    ("iexception", 1),
    ("interrupt",  1),
    ("cause",      5),
    ("tval",      32),
    ("priv",       3),
    ("iaddr",     32),
    ("instr",     32),
    ("compressed", 1),
]

# Helpers ------------------------------------------------------------------------------------------

def add_manifest_sources(platform, manifest):
    basedir = get_data_mod("cpu", "cv32e40p").data_location
    with open(os.path.join(basedir, manifest), 'r') as f:
        for l in f:
            res = re.search('\$\{DESIGN_RTL_DIR\}/(.+)', l)
            if res and not re.match('//', l):
                if re.match('\+incdir\+', l):
                    platform.add_verilog_include_path(os.path.join(basedir, 'rtl', res.group(1)))
                else:
                    platform.add_source(os.path.join(basedir, 'rtl', res.group(1)))

# OBI <> Wishbone ----------------------------------------------------------------------------------

class OBI2Wishbone(Module):
    def __init__(self, obi, wb):
        addr  = Signal.like(obi.addr)
        be    = Signal.like(obi.be)
        we    = Signal.like(obi.we)
        wdata = Signal.like(obi.wdata)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
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

class Wishbone2OBI(Module):
    def __init__(self, wb, obi):
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(wb.cyc & wb.stb,
                obi.req.eq(1),
                NextState("ACK"),
            )
        )
        fsm.act("ACK",
            wb.ack.eq(1),
            NextState("IDLE"),
        )

        self.comb += [
            obi.we.eq(wb.we),
            obi.be.eq(wb.sel),
            obi.addr.eq(Cat(Signal(2), wb.adr)),
            obi.wdata.eq(wb.dat_w),
            wb.dat_r.eq(obi.rdata),
        ]

# Wishbone <> APB ----------------------------------------------------------------------------------

class Wishbone2APB(Module):
    def __init__(self, wb, apb):
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(wb.cyc & wb.stb,
                NextState("ACK"),
            )
        )
        fsm.act("ACK",
            apb.penable.eq(1),
            wb.ack.eq(1),
            NextState("IDLE"),
        )

        self.comb += [
            apb.paddr.eq(Cat(Signal(2), wb.adr)),
            apb.pwrite.eq(wb.we),
            apb.psel.eq(1),
            apb.pwdata.eq(wb.dat_w),
            wb.dat_r.eq(apb.prdata),
        ]

# Trace Collector ----------------------------------------------------------------------------------

class TraceCollector(Module, AutoCSR):
    def __init__(self, trace_depth=16384):
        self.bus  = bus  = wishbone.Interface()
        self.sink = sink = stream.Endpoint([("data", 32)])

        clear   = Signal()
        enable  = Signal()
        pointer = Signal(32)

        self._enable  = CSRStorage()
        self._clear   = CSRStorage()
        self._pointer = CSRStatus(32)

        mem = Memory(32, trace_depth)
        rd_port = mem.get_port()
        wr_port = mem.get_port(write_capable=True)

        self.specials += rd_port, wr_port, mem

        self.sync += [
            # wishbone
            bus.ack.eq(0),
            If(bus.cyc & bus.stb & ~bus.ack, bus.ack.eq(1)),
            # trace core
            If(clear, pointer.eq(0)).Else(
                If(sink.ready & sink.valid, pointer.eq(pointer+1)),
            ),
        ]

        self.comb += [
            # wishbone
            rd_port.adr.eq(bus.adr),
            bus.dat_r.eq(rd_port.dat_r),
            # trace core
            wr_port.adr.eq(pointer),
            wr_port.dat_w.eq(sink.data),
            wr_port.we.eq(sink.ready & sink.valid),
            sink.ready.eq(enable & (pointer < trace_depth)),
            # csrs
            enable.eq(self._enable.storage),
            clear.eq(self._clear.storage),
            self._pointer.status.eq(pointer),
        ]

# Trace Debugger -----------------------------------------------------------------------------------

class TraceDebugger(Module):
    def __init__(self):
        self.bus      = wishbone.Interface()
        self.source   = source   = stream.Endpoint([("data", 32)])
        self.trace_if = trace_if = Record(trace_layout)

        apb = Record(apb_layout)

        self.submodules.bus_conv = Wishbone2APB(self.bus, apb)

        self.trace_params = dict(
            # Clk / Rst.
            i_clk_i               = ClockSignal("sys"),
            i_rst_ni              = ~ResetSignal("sys"),
            i_test_mode_i         = 0,

            # CPU Interface.
            i_ivalid_i            = trace_if.ivalid,
            i_iexception_i        = trace_if.iexception,
            i_interrupt_i         = trace_if.interrupt,
            i_cause_i             = trace_if.cause,
            i_tval_i              = trace_if.tval,
            i_priv_i              = trace_if.priv,
            i_iaddr_i             = trace_if.iaddr,
            i_instr_i             = trace_if.instr,
            i_compressed_i        = trace_if.compressed,

            # APB Interface.
            i_paddr_i             = apb.paddr,
            i_pwdata_i            = apb.pwdata,
            i_pwrite_i            = apb.pwrite,
            i_psel_i              = apb.psel,
            i_penable_i           = apb.penable,
            o_prdata_o            = apb.prdata,
            o_pready_o            = apb.pready,
            o_pslverr_o           = apb.pslverr,

            # Data Output.
            o_packet_word_o       = source.data,
            o_packet_word_valid_o = source.valid,
            i_grant_i             = source.ready,
        )
        self.specials += Instance("trace_debugger", **self.trace_params)

    @staticmethod
    def add_sources(platform):
        add_manifest_sources(platform, "cv32e40p_trace_manifest.flist")

# Debug Module -------------------------------------------------------------------------------------

class DebugModule(Module):
    jtag_layout = [
        ("tck",  1),
        ("tms",  1),
        ("trst", 1),
        ("tdi",  1),
        ("tdo",  1),
    ]
    def __init__(self, pads=None):
        if pads is None:
            pads = Record(self.jtag_layout)
        self.pads = pads
        self.dmbus = wishbone.Interface()
        self.sbbus = wishbone.Interface()
        dmbus = Record(obi_layout)
        sbbus = Record(obi_layout)

        self.submodules.sbbus_conv = OBI2Wishbone(sbbus, self.sbbus)
        self.submodules.dmbus_conv = Wishbone2OBI(self.dmbus, dmbus)

        self.debug_req = Signal()
        self.ndmreset  = Signal()

        tdo_i  = Signal()
        tdo_o  = Signal()
        tdo_oe = Signal()

        self.specials += Tristate(pads.tdo, tdo_o, tdo_oe, tdo_i)

        self.dm_params = dict(
            # Clk / Rst.
            i_clk       = ClockSignal("sys"),
            i_rst_n     = ~ResetSignal("sys"),
            o_ndmreset  = self.ndmreset,
            o_debug_req = self.debug_req,

            # Slave Bus.
            i_dm_req    = dmbus.req,
            i_dm_we     = dmbus.we,
            i_dm_addr   = dmbus.addr,
            i_dm_be     = dmbus.be,
            i_dm_wdata  = dmbus.wdata,
            o_dm_rdata  = dmbus.rdata,

            # Master Bus.
            o_sb_req    = sbbus.req,
            o_sb_addr   = sbbus.addr,
            o_sb_we     = sbbus.we,
            o_sb_wdata  = sbbus.wdata,
            o_sb_be     = sbbus.be,
            i_sb_gnt    = sbbus.gnt,
            i_sb_rvalid = sbbus.rvalid,
            i_sb_rdata  = sbbus.rdata,

            # JTAG.
            i_tck       = pads.tck,
            i_tms       = pads.tms,
            i_trst_n    = pads.trst,
            i_tdi       = pads.tdi,
            o_tdo       = tdo_o,
            o_tdo_oe    = tdo_oe,
        )

        self.comb += [
            dmbus.gnt.eq(dmbus.req),
            dmbus.rvalid.eq(dmbus.gnt),
        ]

        self.specials += Instance("dm_wrap", **self.dm_params)

    @staticmethod
    def add_sources(platform):
        add_manifest_sources(platform, "cv32e40p_dm_manifest.flist")

# CV32E40P -----------------------------------------------------------------------------------------

class CV32E40P(CPU):
    family               = "riscv"
    category             = "softcore"
    name                 = "cv32e40p"
    human_name           = "CV32E40P"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x80000000: 0x80000000} # Origin, Length.

    has_fpu              = ["full"]

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags = GCC_FLAGS[self.variant]
        flags += "-D__cv32e40p__ "
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
        self.submodules.ibus_conv = OBI2Wishbone(ibus, self.ibus)
        self.submodules.dbus_conv = OBI2Wishbone(dbus, self.dbus)

        self.comb += [
            ibus.we.eq(0),
            ibus.be.eq(1111),
        ]

        self.cpu_params = dict(
            # Clk / Rst.
            i_clk_i              = ClockSignal("sys"),
            i_rst_ni             = ~ResetSignal("sys"),

            # Controls.
            i_clock_en_i         = 1,
            i_test_en_i          = 0,
            i_fregfile_disable_i = 0,
            i_core_id_i          = 0,
            i_cluster_id_i       = 0,

            # IBus.
            o_instr_req_o        = ibus.req,
            i_instr_gnt_i        = ibus.gnt,
            i_instr_rvalid_i     = ibus.rvalid,
            o_instr_addr_o       = ibus.addr,
            i_instr_rdata_i      = ibus.rdata,

            # DBus.
            o_data_req_o         = dbus.req,
            i_data_gnt_i         = dbus.gnt,
            i_data_rvalid_i      = dbus.rvalid,
            o_data_we_o          = dbus.we,
            o_data_be_o          = dbus.be,
            o_data_addr_o        = dbus.addr,
            o_data_wdata_o       = dbus.wdata,
            i_data_rdata_i       = dbus.rdata,

            # APU.
            i_apu_master_gnt_i   = 0,
            i_apu_master_valid_i = 0,

            # IRQ.
            i_irq_sec_i          = 0,
            i_irq_software_i     = 0,
            i_irq_external_i     = 0,
            i_irq_fast_i         = self.interrupt,
            i_irq_nmi_i          = 0,
            i_irq_fastx_i        = 0,

            # Debug.
            i_debug_req_i        = 0,

            # CPU Control.
            i_fetch_enable_i     = 1,
        )

        # Add Verilog sources.
        add_manifest_sources(platform, 'cv32e40p_manifest.flist')

        # Specific FPU variant parameters/files.
        if variant in self.has_fpu:
            self.cpu_params.update(p_FPU=1)
            add_manifest_sources(platform, 'cv32e40p_fpu_manifest.flist')

    def add_debug_module(self, dm):
        self.cpu_params.update(i_debug_req_i=dm.debug_req)
        self.cpu_params.update(i_rst_ni=~(ResetSignal() | dm.ndmreset))

    def add_trace_core(self, trace):
        trace_if = trace.trace_if

        self.cpu_params.update(
            o_ivalid_o     = trace_if.ivalid,
            o_iexception_o = trace_if.iexception,
            o_interrupt_o  = trace_if.interrupt,
            o_cause_o      = trace_if.cause,
            o_tval_o       = trace_if.tval,
            o_priv_o       = trace_if.priv,
            o_iaddr_o      = trace_if.iaddr,
            o_instr_o      = trace_if.instr,
            o_compressed_o = trace_if.compressed,
        )

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(i_boot_addr_i=Signal(32, reset=reset_address))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("riscv_core", **self.cpu_params)
