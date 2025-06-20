#
# This file is part of LiteX.
#
# Copyright (c) 2024 Jiaxun Yang <jiaxun.yang@flygoat.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *
from litex.gen import *

from litex.soc.interconnect import axi
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_MIPS

class GS232(CPU):
    category             = "softcore"
    family               = "mips"
    name                 = "gs232"
    human_name           = "Loongson GS232"
    variants             = ["standard"]
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_MIPS
    linker_output_format = "elf32-tradlittlemips"
    nop                  = "nop"
    io_regions           = {0x1000_0000: 0x0c00_0000} # Origin, Length.

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags = "-march=mips32 -mabi=32 -msoft-float"
        flags += " -D__gs232__ "
        flags += " -DUART_POLLING"
        return flags

    # Memory Mapping.
    @property
    def mem_map(self):
        # Based on vanilla sysmap.h
        return {
            "main_ram" : 0x0000_0000,
            "csr"      : 0x1800_0000,
            "sram"     : 0x1c00_0000,
            "rom"      : 0x1fc0_0000,
        }

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.interrupt    = Signal(5)
        # Peripheral bus (Connected to main SoC's bus).
        axi_if = axi.AXIInterface(data_width=32, address_width=32, id_width=4)
        self.periph_buses = [axi_if]
        # Memory buses (Connected directly to LiteDRAM).
        self.memory_buses = []

        tlb_to_ram = Signal(66)
        ram_to_tlb = Signal(52)
        icache_to_ram = Signal(1444)
        ram_to_icache = Signal(1152)
        dcache_to_ram = Signal(1404)
        ram_to_dcache = Signal(1112)

        # CPU Instance.
        self.cpu_params = dict(
            # Clk / Rst
            i_coreclock     = ClockSignal("sys"),
            i_areset_n      = ~ResetSignal("sys") & ~self.reset,
            o_core_rst_     = Open(),

            # Interrupts (Low active)
            i_interrupt_i   = ~self.interrupt,
            i_nmi           = 1,

            # AXI interface
            i_aclk          = ClockSignal("sys"),
            o_arid          = axi_if.ar.id,
            o_araddr        = axi_if.ar.addr,
            o_arlen         = axi_if.ar.len,
            o_arsize        = axi_if.ar.size,
            o_arburst       = axi_if.ar.burst,
            o_arlock        = axi_if.ar.lock,
            o_arcache       = axi_if.ar.cache,
            o_arprot        = axi_if.ar.prot,
            o_arvalid       = axi_if.ar.valid,
            i_arready       = axi_if.ar.ready,

            i_rid           = axi_if.r.id,
            i_rdata         = axi_if.r.data,
            i_rresp         = axi_if.r.resp,
            i_rlast         = axi_if.r.last,
            i_rvalid        = axi_if.r.valid,
            o_rready        = axi_if.r.ready,

            o_awid          = axi_if.aw.id,
            o_awaddr        = axi_if.aw.addr,
            o_awlen         = axi_if.aw.len,
            o_awsize        = axi_if.aw.size,
            o_awburst       = axi_if.aw.burst,
            o_awlock        = axi_if.aw.lock,
            o_awcache       = axi_if.aw.cache,
            o_awprot        = axi_if.aw.prot,
            o_awvalid       = axi_if.aw.valid,
            i_awready       = axi_if.aw.ready,

            o_wid           = axi_if.w.id,
            o_wdata         = axi_if.w.data,
            o_wstrb         = axi_if.w.strb,
            o_wlast         = axi_if.w.last,
            o_wvalid        = axi_if.w.valid,
            i_wready        = axi_if.w.ready,

            i_bid           = axi_if.b.id,
            i_bresp         = axi_if.b.resp,
            i_bvalid        = axi_if.b.valid,
            o_bready        = axi_if.b.ready,

            # SRAM interface
            o_tlb_to_ram    = tlb_to_ram,
            i_ram_to_tlb    = ram_to_tlb,

            o_icache_to_ram = icache_to_ram,
            i_ram_to_icache = ram_to_icache,

            o_dcache_to_ram = dcache_to_ram,
            i_ram_to_dcache = ram_to_dcache,

            # DFT
            o_prrst_to_core     = Open(),
            i_testmode        = 0,
        )

        # TLB & Cache SRAMs
        # Magic numbers all from godson_ram_bist.v, don't touch!
        tlb_cen = tlb_to_ram[0] # Active low
        tlb_wen = tlb_to_ram[7] # Active low
        tlb_din = tlb_to_ram[8:(59 + 1)]
        tlb_mem = Memory(52, 32)
        tlb_p = tlb_mem.get_port(write_capable=True, has_re=True)
        self.specials += tlb_mem, tlb_p
        self.comb += [
            tlb_p.re.eq(~tlb_cen & tlb_wen),
            If(tlb_wen, tlb_p.adr.eq(tlb_to_ram[1:(5 + 1)])).Else(tlb_p.adr.eq(tlb_to_ram[60:(64 + 1)])),
            tlb_p.we.eq(~tlb_cen & ~tlb_wen),
            tlb_p.dat_w.eq(tlb_din),
            ram_to_tlb.eq(tlb_p.dat_r),
        ]

        for iway in range(4):
            tag_ena   = ~icache_to_ram[ 361 * iway + 0]
            tag_addra =  icache_to_ram[(361 * iway + 1):(361 * iway + 7 + 1)]
            tag_wea   = ~icache_to_ram[ 361 * iway + 8]
            tag_dina  =  icache_to_ram[(361 * iway + 9):(361 * iway + 40 + 1)]
            tag_douta =  ram_to_icache[(288 * iway + 0):(288 * iway + 31 + 1)]
            tag_mem = Memory(32, 128)
            tag_p = tag_mem.get_port(write_capable=True, has_re=True)
            self.specials += tag_mem, tag_p
            self.comb += [
                tag_p.re.eq(tag_ena & ~tag_wea),
                tag_p.adr.eq(tag_addra),
                tag_p.we.eq(tag_ena & tag_wea),
                tag_p.dat_w.eq(tag_dina),
                tag_douta.eq(tag_p.dat_r),
            ]

            for ibank in range(4):
                data_ena   = ~icache_to_ram[ 361 * iway + 41 + 80 * ibank + 0]
                data_addra =  icache_to_ram[(361 * iway + 41 + 80 * ibank +  1):(361 * iway + 41 + 80 * ibank +  7 + 1)]
                data_wea   = ~icache_to_ram[(361 * iway + 41 + 80 * ibank +  8):(361 * iway + 41 + 80 * ibank + 15 + 1)] # Byte wise
                data_dina  =  icache_to_ram[(361 * iway + 41 + 80 * ibank + 16):(361 * iway + 41 + 80 * ibank + 79 + 1)]
                data_douta =  ram_to_icache[(288 * iway + 32 + 64 * ibank +  0):(288 * iway + 32 + 64 * ibank + 63 + 1)]
                data_mem = Memory(64, 128)
                data_p = data_mem.get_port(write_capable=True, has_re=True, we_granularity=8)
                self.specials += data_mem, data_p
                self.comb += [
                    data_p.re.eq(data_ena & ~data_wea),
                    data_p.adr.eq(data_addra),
                    data_p.we.eq(Replicate(data_ena, 8) & data_wea),
                    data_p.dat_w.eq(data_dina),
                    data_douta.eq(data_p.dat_r),
                ]

        for dway in range(4):
            tag_ena   = ~dcache_to_ram[ 351 * dway + 0]
            tag_addra =  dcache_to_ram[(351 * dway + 1):(351 * dway +  7 + 1)]
            tag_wea   = ~dcache_to_ram[ 351 * dway + 8]
            tag_dina  =  dcache_to_ram[(351 * dway + 9):(351 * dway + 30 + 1)]
            tag_douta =  ram_to_dcache[(278 * dway + 0):(278 * dway + 21 + 1)]
            tag_mem = Memory(22, 128)
            tag_p = tag_mem.get_port(write_capable=True, has_re=True)
            self.specials += tag_mem, tag_p
            self.comb += [
                tag_p.re.eq(tag_ena & ~tag_wea),
                tag_p.adr.eq(tag_addra),
                tag_p.we.eq(tag_ena & tag_wea),
                tag_p.dat_w.eq(tag_dina),
                tag_douta.eq(tag_p.dat_r),
            ]

            for dbank in range(4):
                data_ena   = ~dcache_to_ram[ 351 * dway + 31 + 80 * dbank + 0]
                data_addra =  dcache_to_ram[(351 * dway + 31 + 80 * dbank +  1):(351 * dway + 31 + 80 * dbank +  7 + 1)]
                data_wea   = ~dcache_to_ram[(351 * dway + 31 + 80 * dbank +  8):(351 * dway + 31 + 80 * dbank + 15 + 1)] # Byte wise
                data_dina  =  dcache_to_ram[(351 * dway + 31 + 80 * dbank + 16):(351 * dway + 31 + 80 * dbank + 79 + 1)]
                data_douta =  ram_to_dcache[(278 * dway + 22 + 64 * dbank +  0):(278 * dway + 22 + 64 * dbank + 63 + 1)]
                data_mem = Memory(64, 128)
                data_p = data_mem.get_port(write_capable=True, has_re=True, we_granularity=8)
                self.specials += data_mem, data_p
                self.comb += [
                    data_p.re.eq(data_ena & ~data_wea),
                    data_p.adr.eq(data_addra),
                    data_p.we.eq(Replicate(data_ena, 8) & data_wea),
                    data_p.dat_w.eq(data_dina),
                    data_douta.eq(data_p.dat_r),
                ]

        # Add sources.
        basedir = "cpu_gs232"
        self.platform.add_source_dir(basedir)
        platform.add_verilog_include_path(basedir)

    def add_jtag(self, pads):
        self.cpu_params.update(
            i_EJTAG_TMS  = pads.tms,
            i_EJTAG_TDI  = pads.tdi,
            o_EJTAG_TDO  = pads.tdo,
            i_EJTAG_TRST = pads.ntrst,
            i_EJTAG_TCK  = pads.tck,
        )

    def set_reset_address(self, reset_address):
        # Hardcoded reset address.
        assert reset_address == 0x1fc0_0000
        self.reset_address = reset_address

    def bios_map(self, addr, cached):
        # We can't access beyond KSEG0/1 in BIOS
        assert addr < 0x2000_0000
        if cached:
            return addr + 0x8000_0000
        else:
            return addr + 0xa000_0000

    def do_finalize(self):
        self.specials += Instance("godson_cpu_core", **self.cpu_params)
