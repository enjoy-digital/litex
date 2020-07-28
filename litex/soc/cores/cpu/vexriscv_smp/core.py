# This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 Dolu1990 <charles.papon.90@gmail.com>
# License: BSD

import os
from os import path

from litex import get_data_mod
from migen import *

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import *
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

import os


CPU_VARIANTS = {
    "linux":    "VexRiscv",
}

class Open(Signal): pass

class VexRiscvSMP(CPU):
    name                 = "vexriscv"
    human_name           = "VexRiscv SMP"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x80000000: 0x80000000} # origin, length

    cpu_count   = 1
    dcache_size = 8192
    icache_size = 8192
    dcache_ways = 2
    icache_ways = 2
    coherent_dma   = False
    litedram_width = 128
    dbus_width     = 64
    ibus_width     = 64

    @staticmethod
    def args_fill(parser):
        parser.add_argument("--cpu-count",   default=1,    help="")
        parser.add_argument("--dcache-size", default=8192, help="")
        parser.add_argument("--dcache-ways", default=2,    help="")
        parser.add_argument("--icache-size", default=8192, help="")
        parser.add_argument("--icache-ways", default=2,    help="")


    @staticmethod
    def args_read(args):
        VexRiscvSMP.cpu_count   = args.cpu_count
        VexRiscvSMP.dcache_size = args.dcache_size
        VexRiscvSMP.icache_size = args.icache_size
        VexRiscvSMP.dcache_ways = args.dcache_ways
        VexRiscvSMP.icache_ways = args.icache_ways

    @property
    def mem_map(self):
        return {
            "rom":          0x00000000,
            "sram":         0x10000000,
            "main_ram":     0x40000000,
            "csr":          0xf0000000,
            "clint":        0xf0010000,
        }

    @property
    def gcc_flags(self):
        flags =  " -march=rv32ima     -mabi=ilp32"
        flags += " -D__vexriscv__"
        flags += " -DUART_POLLING"
        return flags

    @staticmethod
    def generate_cluster_name():
        VexRiscvSMP.cluster_name     = f"VexRiscvLitexSmpCluster_Cc{VexRiscvSMP.cpu_count}_Iw{VexRiscvSMP.ibus_width}Is{VexRiscvSMP.icache_size}Iy{VexRiscvSMP.icache_ways}_Dw{VexRiscvSMP.dbus_width}Ds{VexRiscvSMP.dcache_size}Dy{VexRiscvSMP.dcache_ways}_Ldw{VexRiscvSMP.litedram_width}{'_Cdma' if VexRiscvSMP.coherent_dma else ''}"

    @staticmethod
    def generate_default_configs():
        VexRiscvSMP.ibus_width     = 64
        VexRiscvSMP.dbus_width     = 64
        VexRiscvSMP.dcache_size    = 8192
        VexRiscvSMP.icache_size    = 8192
        VexRiscvSMP.dcache_ways    = 2
        VexRiscvSMP.icache_ways    = 2
        VexRiscvSMP.litedram_width = 128

        VexRiscvSMP.coherent_dma   = True
        for core_count in [1,2,4]:
            VexRiscvSMP.cpu_count      = core_count
            VexRiscvSMP.generate_cluster_name()
            VexRiscvSMP.generate_netlist()

        VexRiscvSMP.coherent_dma   = False
        for core_count in [1]:
            VexRiscvSMP.cpu_count      = core_count
            VexRiscvSMP.generate_cluster_name()
            VexRiscvSMP.generate_netlist()


    @staticmethod
    def generate_netlist():
        print(f"Generating cluster netlist")
        vdir = get_data_mod("cpu", "vexriscv_smp").data_location

        gen_args = []
        if(VexRiscvSMP.coherent_dma) : gen_args.append("--coherent-dma")
        gen_args.append(f"--cpu-count={VexRiscvSMP.cpu_count}")
        gen_args.append(f"--ibus-width={VexRiscvSMP.ibus_width}")
        gen_args.append(f"--dbus-width={VexRiscvSMP.dbus_width}")
        gen_args.append(f"--dcache-size={VexRiscvSMP.dcache_size}")
        gen_args.append(f"--icache-size={VexRiscvSMP.icache_size}")
        gen_args.append(f"--dcache-ways={VexRiscvSMP.dcache_ways}")
        gen_args.append(f"--icache-ways={VexRiscvSMP.icache_ways}")
        gen_args.append(f"--litedram-width={VexRiscvSMP.litedram_width}")
        gen_args.append(f"--netlist-name={VexRiscvSMP.cluster_name}")
        gen_args.append(f"--netlist-directory={vdir}")

        cmd = 'cd {path} && sbt "runMain vexriscv.demo.smp.VexRiscvLitexSmpClusterCmdGen {args}"'.format(path=os.path.join(vdir, "ext", "VexRiscv"), args=" ".join(gen_args))
        os.system(cmd)

    def __init__(self, platform, variant):
        self.platform         = platform
        self.variant          = "standard"
        self.human_name       = self.human_name + "-" + variant.upper()
        self.reset            = Signal()
        self.jtag_clk         = Signal()
        self.jtag_enable      = Signal()
        self.jtag_capture     = Signal()
        self.jtag_shift       = Signal()
        self.jtag_update      = Signal()
        self.jtag_reset       = Signal()
        self.jtag_tdo         = Signal()
        self.jtag_tdi         = Signal()
        self.interrupt        = Signal(32)
        self.pbus             = pbus    = wishbone.Interface()
        self.cbus             = cbus    = wishbone.Interface()
        self.plicbus          = plicbus = wishbone.Interface()

        self.periph_buses     = [pbus]
        self.memory_buses     = [] # Added dynamically

        VexRiscvSMP.generate_cluster_name()

        # # #
        self.cpu_params = dict(
            # Clk / Rst
            i_debugCd_external_clk   = ClockSignal(),
            i_debugCd_external_reset = ResetSignal() | self.reset,

            # Interrupts
            i_interrupts             = self.interrupt,

            # JTAG
            i_jtag_clk               = self.jtag_clk,
            i_debugPort_enable       = self.jtag_enable,
            i_debugPort_capture      = self.jtag_capture,
            i_debugPort_shift        = self.jtag_shift,
            i_debugPort_update       = self.jtag_update,
            i_debugPort_reset        = self.jtag_reset,
            i_debugPort_tdi          = self.jtag_tdi,
            o_debugPort_tdo          = self.jtag_tdo,

            # Peripheral Bus (Master)
            o_peripheral_CYC         = pbus.cyc,
            o_peripheral_STB         = pbus.stb,
            i_peripheral_ACK         = pbus.ack,
            o_peripheral_WE          = pbus.we,
            o_peripheral_ADR         = pbus.adr,
            i_peripheral_DAT_MISO    = pbus.dat_r,
            o_peripheral_DAT_MOSI    = pbus.dat_w,
            o_peripheral_SEL         = pbus.sel,
            i_peripheral_ERR         = pbus.err,
            o_peripheral_CTI         = pbus.cti,
            o_peripheral_BTE         = pbus.bte,

            # CLINT Bus (Slave)
            i_clintWishbone_CYC      = cbus.cyc,
            i_clintWishbone_STB      = cbus.stb,
            o_clintWishbone_ACK      = cbus.ack,
            i_clintWishbone_WE       = cbus.we,
            i_clintWishbone_ADR      = cbus.adr,
            o_clintWishbone_DAT_MISO = cbus.dat_r,
            i_clintWishbone_DAT_MOSI = cbus.dat_w,

            # PLIC Bus (Slave)
            i_plicWishbone_CYC       = plicbus.cyc,
            i_plicWishbone_STB       = plicbus.stb,
            o_plicWishbone_ACK       = plicbus.ack,
            i_plicWishbone_WE        = plicbus.we,
            i_plicWishbone_ADR       = plicbus.adr,
            o_plicWishbone_DAT_MISO  = plicbus.dat_r,
            i_plicWishbone_DAT_MOSI  = plicbus.dat_w
        )

        if self.coherent_dma:
            self.dma_bus = dma_bus = wishbone.Interface(data_width=64)

            dma_bus_stall   = Signal()
            dma_bus_inhibit = Signal()

            self.cpu_params.update(
                i_dma_wishbone_CYC      = dma_bus.cyc,
                i_dma_wishbone_STB      = dma_bus.stb & ~dma_bus_inhibit,
                o_dma_wishbone_ACK      = dma_bus.ack,
                i_dma_wishbone_WE       = dma_bus.we,
                i_dma_wishbone_SEL      = dma_bus.sel,
                i_dma_wishbone_ADR      = dma_bus.adr,
                o_dma_wishbone_DAT_MISO = dma_bus.dat_r,
                i_dma_wishbone_DAT_MOSI = dma_bus.dat_w,
                o_dma_wishbone_STALL    = dma_bus_stall
            )

            self.sync += [
                If(dma_bus.stb & dma_bus.cyc & ~dma_bus_stall,
                    dma_bus_inhibit.eq(1),
                ),
                If(dma_bus.ack,
                   dma_bus_inhibit.eq(0)
                )
            ]

        from litedram.common import LiteDRAMNativePort
        if "mp" in variant:
            ncpus = int(variant[-2]) # FIXME
            for n in range(ncpus):
                ibus = LiteDRAMNativePort(mode="both", address_width=32, data_width=128)
                dbus = LiteDRAMNativePort(mode="both", address_width=32, data_width=128)
                self.memory_buses.append(ibus)
                self.memory_buses.append(dbus)
                self.cpu_params.update({
                    # Instruction Memory Bus (Master)
                    "o_io_iMem_{}_cmd_valid".format(n)          : ibus.cmd.valid,
                    "i_io_iMem_{}_cmd_ready".format(n)          : ibus.cmd.ready,
                    "o_io_iMem_{}_cmd_payload_we".format(n)     : ibus.cmd.we,
                    "o_io_iMem_{}_cmd_payload_addr".format(n)   : ibus.cmd.addr,
                    "o_io_iMem_{}_wdata_valid".format(n)        : ibus.wdata.valid,
                    "i_io_iMem_{}_wdata_ready".format(n)        : ibus.wdata.ready,
                    "o_io_iMem_{}_wdata_payload_data".format(n) : ibus.wdata.data,
                    "o_io_iMem_{}_wdata_payload_we".format(n)   : ibus.wdata.we,
                    "i_io_iMem_{}_rdata_valid".format(n)        : ibus.rdata.valid,
                    "o_io_iMem_{}_rdata_ready".format(n)        : ibus.rdata.ready,
                    "i_io_iMem_{}_rdata_payload_data".format(n) : ibus.rdata.data,

                    # Data Memory Bus (Master)
                    "o_io_dMem_{}_cmd_valid".format(n)          : dbus.cmd.valid,
                    "i_io_dMem_{}_cmd_ready".format(n)          : dbus.cmd.ready,
                    "o_io_dMem_{}_cmd_payload_we".format(n)     : dbus.cmd.we,
                    "o_io_dMem_{}_cmd_payload_addr".format(n)   : dbus.cmd.addr,
                    "o_io_dMem_{}_wdata_valid".format(n)        : dbus.wdata.valid,
                    "i_io_dMem_{}_wdata_ready".format(n)        : dbus.wdata.ready,
                    "o_io_dMem_{}_wdata_payload_data".format(n) : dbus.wdata.data,
                    "o_io_dMem_{}_wdata_payload_we".format(n)   : dbus.wdata.we,
                    "i_io_dMem_{}_rdata_valid".format(n)        : dbus.rdata.valid,
                    "o_io_dMem_{}_rdata_ready".format(n)        : dbus.rdata.ready,
                    "i_io_dMem_{}_rdata_payload_data".format(n) : dbus.rdata.data,
                })
        else:
            ibus = LiteDRAMNativePort(mode="both", address_width=32, data_width=128)
            dbus = LiteDRAMNativePort(mode="both", address_width=32, data_width=128)
            self.memory_buses.append(ibus)
            self.memory_buses.append(dbus)
            self.cpu_params.update(
                # Instruction Memory Bus (Master)
                o_iBridge_dram_cmd_valid          = ibus.cmd.valid,
                i_iBridge_dram_cmd_ready          = ibus.cmd.ready,
                o_iBridge_dram_cmd_payload_we     = ibus.cmd.we,
                o_iBridge_dram_cmd_payload_addr   = ibus.cmd.addr,
                o_iBridge_dram_wdata_valid        = ibus.wdata.valid,
                i_iBridge_dram_wdata_ready        = ibus.wdata.ready,
                o_iBridge_dram_wdata_payload_data = ibus.wdata.data,
                o_iBridge_dram_wdata_payload_we   = ibus.wdata.we,
                i_iBridge_dram_rdata_valid        = ibus.rdata.valid,
                o_iBridge_dram_rdata_ready        = ibus.rdata.ready,
                i_iBridge_dram_rdata_payload_data = ibus.rdata.data,

                # Data Memory Bus (Master)
                o_dBridge_dram_cmd_valid          = dbus.cmd.valid,
                i_dBridge_dram_cmd_ready          = dbus.cmd.ready,
                o_dBridge_dram_cmd_payload_we     = dbus.cmd.we,
                o_dBridge_dram_cmd_payload_addr   = dbus.cmd.addr,
                o_dBridge_dram_wdata_valid        = dbus.wdata.valid,
                i_dBridge_dram_wdata_ready        = dbus.wdata.ready,
                o_dBridge_dram_wdata_payload_data = dbus.wdata.data,
                o_dBridge_dram_wdata_payload_we   = dbus.wdata.we,
                i_dBridge_dram_rdata_valid        = dbus.rdata.valid,
                o_dBridge_dram_rdata_ready        = dbus.rdata.ready,
                i_dBridge_dram_rdata_payload_data = dbus.rdata.data,
            )

        # Add verilog sources
        self.add_sources(platform, variant)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        assert reset_address == 0x00000000

    def add_sources(self, platform, variant):
        vdir = get_data_mod("cpu", "vexriscv_smp").data_location
        print(f"VexRiscv cluster : {self.cluster_name}")
        if not path.exists(os.path.join(vdir, self.cluster_name + ".v")):
            self.generate_netlist()

        platform.add_source(os.path.join(vdir, "RamXilinx.v"), "verilog")
        platform.add_source(os.path.join(vdir,  self.cluster_name + ".v"), "verilog")

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance(self.cluster_name, **self.cpu_params)
