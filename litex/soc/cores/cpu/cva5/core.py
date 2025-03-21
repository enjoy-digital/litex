#
# This file is part of LiteX.
#
# Copyright (c) 2022 Eric Matthews <eric.charles.matthews@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex import get_data_mod

from litex.gen import *

from litex.soc.interconnect import wishbone
from litex.soc.interconnect import axi
from litex.soc.interconnect.csr import *
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32
from litex.soc.integration.soc import SoCRegion

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["minimal", "standard","standard+atomic","standard+atomic+float+double"]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                        /------------ Base ISA
    #                        |    /------- Hardware Multiply + Divide
    #                        |    |/----- Atomics
    #                        |    ||/---- Compressed ISA
    #                        |    |||/--- Single-Precision Floating-Point
    #                        |    ||||/-- Double-Precision Floating-Point
    #                        i    macfd
    "minimal"  : "-march=rv32i2p0   -mabi=ilp32 ",
    "standard" : "-march=rv32i2p0_m -mabi=ilp32 ",
    "standard+atomic" : "-march=rv32i2p0_ma -mabi=ilp32 ",
    "standard+atomic+float+double" : "-march=rv32i2p0_mafd -mabi=ilp32 ",
}

# CVA5 ----------------------------------------------------------------------------------------------

class CVA5(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "cva5"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x80000000: 0x80000000} # origin, length
    plic_base            = 0xf800_0000
    clint_base           = 0xf001_0000
    cpu_count           = 1
    bus_type             = "wishbone" #either wishbone or axi
    cpu_variant          = "Linux" #either linux or default



    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group(title="CPU options")
        cpu_group.add_argument("--cpu-count",                    default=1,            help="Number of CPU(s) in the cluster.", type=int)
        cpu_group.add_argument("--clint-base",                   default="0xf0010000", help="CLINT base address.")
        cpu_group.add_argument("--plic-base",                    default="0xf800_0000", help="PLIC base address.")
        cpu_group.add_argument("--bus-type",                    default="wishbone", help="Bus type can be either wishbone or axi")
        cpu_group.add_argument("--variant",                    default="Linux", help="The CPU type for now it has the linux type")#TODO add other configs

    @staticmethod
    def args_read(args):
        CVA5.cpu_count = args.cpu_count
        CVA5.bus_type = args.bus_type
        CVA5.cpu_variant = args.variant
        if(args.clint_base): CVA5.clint_base = int(args.clint_base, 16)
        if(args.plic_base):  CVA5.plic_base  = int(args.plic_base, 16)



    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "rom":            0x0000_0000,
            "sram":           0x0100_0000,
            "main_ram":       0x4000_0000,
            "csr":            0xf000_0000,
        }
    
    # GCC Flags.
    @property
    def gcc_flags(self):
        flags = GCC_FLAGS[self.variant]
        if(CVA5.cpu_variant=="Linux"):
            flags += "-D__riscv_plic__"
        else:
            flags += "-D__cva5__"
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.human_name   = f"CVA5-{variant.upper()}"
        self.reset        = Signal()
        self.interrupt    = Signal(2)
        self.periph_buses = [] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = [] # Memory buses (Connected directly to LiteDRAM).
        self.reset        = Signal()

        # CPU Instance.
        self.cpu_params = dict(
            # Configuration.           
            p_RESET_VEC      = 0,
            p_NON_CACHABLE_L = 0x80000000, # FIXME: Use io_regions.
            p_NON_CACHABLE_H = 0xFFFFFFFF, # FIXME: Use io_regions.
            p_NUM_CORES      = CVA5.cpu_count,
            p_AXI = 0 if CVA5.bus_type == "wishbone" else 1,

            # Clk/Rst.
            i_clk = ClockSignal("sys"),
            i_rst = ResetSignal("sys") | self.reset,
        )

        if(CVA5.bus_type == "wishbone"):
            self.idbus = idbus = wishbone.Interface(data_width=32, address_width=32, addressing="word")
            self.periph_buses.append(idbus)
            self.cpu_params.update(
                o_idbus_adr   = idbus.adr,
                o_idbus_dat_w = idbus.dat_w,
                o_idbus_sel   = idbus.sel,
                o_idbus_cyc   = idbus.cyc,
                o_idbus_stb   = idbus.stb,
                o_idbus_we    = idbus.we,
                o_idbus_cti   = idbus.cti,
                o_idbus_bte   = idbus.bte,
                i_idbus_dat_r = idbus.dat_r,
                i_idbus_ack   = idbus.ack,
                i_idbus_err   = idbus.err,
            )
        else:
            self.axi_if = axi_if = axi.AXIInterface(data_width=32, address_width=32, id_width=4)
            self.periph_buses.append(axi_if)

            self.cpu_params.update(
                # AXI read address channel
                i_m_axi_arready  = axi_if.ar.ready,
                o_m_axi_arvalid  = axi_if.ar.valid,
                o_m_axi_araddr   = axi_if.ar.addr,
                o_m_axi_arlen    = axi_if.ar.len,
                o_m_axi_arsize   = axi_if.ar.size,
                o_m_axi_arburst  = axi_if.ar.burst,
                o_m_axi_arcache  = axi_if.ar.cache,
                o_m_axi_arid     = axi_if.ar.id,

                # AXI read data channel
                o_m_axi_rready   = axi_if.r.ready,
                i_m_axi_rvalid   = axi_if.r.valid,
                i_m_axi_rdata    = axi_if.r.data,
                i_m_axi_rresp    = axi_if.r.resp,
                i_m_axi_rlast    = axi_if.r.last,
                i_m_axi_rid      = axi_if.r.id,

                # AXI write address channel
                i_m_axi_awready  = axi_if.aw.ready,
                o_m_axi_awvalid  = axi_if.aw.valid,
                o_m_axi_awaddr   = axi_if.aw.addr,
                o_m_axi_awlen    = axi_if.aw.len,
                o_m_axi_awsize   = axi_if.aw.size,
                o_m_axi_awburst  = axi_if.aw.burst,
                o_m_axi_awcache  = axi_if.aw.cache,
                o_m_axi_awid     = axi_if.aw.id,

                # AXI write data channel
                i_m_axi_wready   = axi_if.w.ready,
                o_m_axi_wvalid   = axi_if.w.valid,
                o_m_axi_wdata    = axi_if.w.data,
                o_m_axi_wstrb    = axi_if.w.strb,
                o_m_axi_wlast    = axi_if.w.last,

                # AXI write response channel
                o_m_axi_bready   = axi_if.b.ready,
                i_m_axi_bvalid   = axi_if.b.valid,
                i_m_axi_bresp    = axi_if.b.resp,
                i_m_axi_bid      = axi_if.b.id,
            )
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        self.cpu_params.update(p_RESET_VEC=reset_address)

    @staticmethod
    def add_sources(platform):
        cva5_path = get_data_mod("cpu", "cva5").data_location
        with open(os.path.join(cva5_path, "tools/compile_order"), "r") as f:
            for line in f:
                if line.strip() != '':
                    platform.add_source(os.path.join(cva5_path, line.strip()))
        platform.add_source(os.path.join(cva5_path, "examples/litex/litex_wrapper.sv"))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("litex_wrapper", **self.cpu_params)

    def add_soc_components(self, soc):
        soc.csr.add("sdram", n=1)
        soc.csr.add("uart", n=2)
        soc.csr.add("timer0", n=3)
        soc.csr.add("supervisor", n=4)

        # PLIC
        seip = Signal(int(self.cpu_params["p_NUM_CORES"]))
        meip = Signal(int(self.cpu_params["p_NUM_CORES"]))
        eip = Signal(2*int(self.cpu_params["p_NUM_CORES"]))
        es = Signal(2, reset=0)

        if(CVA5.cpu_variant == "Linux"):
            if(CVA5.bus_type == "wishbone"):
                self.plicbus = plicbus = wishbone.Interface(data_width=32, address_width=32, addressing="word")
                self.specials += Instance("plic_wrapper",
                    p_NUM_SOURCES = 1,
                    p_NUM_TARGETS = 2*int(self.cpu_params["p_NUM_CORES"]),
                    p_PRIORITY_W = 8,
                    p_REG_STAGE = 1,
                    p_AXI = 0,
                    i_clk = ClockSignal("sys"),
                    i_rst = ResetSignal("sys"),
                    i_irq_srcs = self.interrupt,
                    i_edge_sensitive = es,
                    o_eip = eip,
                    i_wb_cyc = plicbus.cyc,
                    i_wb_stb = plicbus.stb,
                    i_wb_we = plicbus.we,
                    i_wb_adr = plicbus.adr,
                    i_wb_dat_i = plicbus.dat_w,
                    o_wb_dat_o = plicbus.dat_r,
                    o_wb_ack = plicbus.ack,
                )
            else:
                self.plicbus = plicbus = axi.AXIInterface(data_width=32, address_width=32, id_width=4)
                self.specials += Instance("plic_wrapper",
                    p_NUM_SOURCES = 1,
                    p_NUM_TARGETS = 2*int(self.cpu_params["p_NUM_CORES"]),
                    p_PRIORITY_W = 8,
                    p_REG_STAGE = 1,
                    p_AXI = 1,
                    i_clk = ClockSignal("sys"),
                    i_rst = ResetSignal("sys"),
                    i_irq_srcs = self.interrupt,
                    i_edge_sensitive = es,
                    o_eip = eip,
                    i_s_axi_awvalid = plicbus.aw.valid,
                    i_s_axi_awaddr = plicbus.aw.addr,
                    i_s_axi_wvalid = plicbus.w.valid,
                    i_s_axi_wdata = plicbus.w.data,
                    i_s_axi_bready = plicbus.b.ready,
                    i_s_axi_arvalid = plicbus.ar.valid,
                    i_s_axi_araddr = plicbus.ar.addr,
                    i_s_axi_rready = plicbus.r.ready,
                    o_s_axi_awready = plicbus.aw.ready,
                    o_s_axi_wready = plicbus.w.ready,
                    o_s_axi_bvalid = plicbus.b.valid,
                    o_s_axi_arready = plicbus.ar.ready,
                    o_s_axi_rvalid = plicbus.r.valid,
                    o_s_axi_rdata = plicbus.r.data
                )

            self.comb += [
                meip.eq(Cat(*[eip[i*2] for i in range(int(self.cpu_params["p_NUM_CORES"]))])),
                seip.eq(Cat(*[eip[i*2 + 1] for i in range(int(self.cpu_params["p_NUM_CORES"]))]))
            ]

            self.cpu_params.update(
                i_seip = seip,
                i_meip = meip
            )
            soc.bus.add_slave("plic", self.plicbus, region=SoCRegion(origin=self.plic_base, size=0x40_0000, cached=False))
        else:
            self.cpu_params.update(
                i_meip = self.interrupt[0]
            )



        # CLINT
        if(CVA5.cpu_variant == "Linux"):
            mtime = Signal(64)
            msip = Signal(int(self.cpu_params["p_NUM_CORES"]))
            mtip = Signal(int(self.cpu_params["p_NUM_CORES"]))
            if(CVA5.bus_type == "wishbone"):
                self.clintbus = clintbus = wishbone.Interface(data_width=32, address_width=32, addressing="word")
                self.specials += Instance("clint_wrapper",
                    p_NUM_CORES = int(self.cpu_params["p_NUM_CORES"]),
                    p_AXI = 0,
                    i_clk = ClockSignal("sys"),
                    i_rst = ResetSignal("sys"),
                    o_mtip = mtip,
                    o_msip = msip,
                    o_mtime  = mtime,
                    i_wb_cyc = clintbus.cyc,
                    i_wb_stb = clintbus.stb,
                    i_wb_we = clintbus.we,
                    i_wb_adr = clintbus.adr,
                    i_wb_dat_i = clintbus.dat_w,
                    o_wb_dat_o = clintbus.dat_r,
                    o_wb_ack = clintbus.ack,
                )
            else:
                self.clintbus = clintbus = axi.AXIInterface(data_width=32, address_width=32, id_width=4)
                self.specials += Instance("clint_wrapper",
                    p_NUM_CORES = int(self.cpu_params["p_NUM_CORES"]),
                    p_AXI = 1,
                    i_clk = ClockSignal("sys"),
                    i_rst = ResetSignal("sys"),
                    o_mtip = mtip,
                    o_msip = msip,
                    o_mtime  = mtime,
                    i_s_axi_awvalid = clintbus.aw.valid,
                    i_s_axi_awaddr = clintbus.aw.addr,
                    i_s_axi_wvalid = clintbus.w.valid,
                    i_s_axi_wdata = clintbus.w.data,
                    i_s_axi_bready = clintbus.b.ready,
                    i_s_axi_arvalid = clintbus.ar.valid,
                    i_s_axi_araddr = clintbus.ar.addr,
                    i_s_axi_rready = clintbus.r.ready,
                    o_s_axi_awready = clintbus.aw.ready,
                    o_s_axi_wready = clintbus.w.ready,
                    o_s_axi_bvalid = clintbus.b.valid,
                    o_s_axi_arready = clintbus.ar.ready,
                    o_s_axi_rvalid = clintbus.r.valid,
                    o_s_axi_rdata = clintbus.r.data
                )
            self.cpu_params.update(
                i_mtime = mtime,
                i_msip = msip,
                i_mtip = mtip
            )
            soc.bus.add_slave("clint", clintbus, region=SoCRegion(origin=self.clint_base, size=0x1_0000, cached=False))
        else:
            self.cpu_params.update(
                i_mtip = self.interrupt[1]
            )

