#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Dolu1990 <charles.papon.90@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess

from migen import *

from litex.gen import *

from litex import get_data_mod

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc import SoCRegion

from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# VexRiscv SMP -------------------------------------------------------------------------------------

class VexRiscvSMP(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "vexriscv"
    human_name           = "VexRiscv SMP"
    variants             = ["standard", "linux"]
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x8000_0000: 0x8000_0000} # Origin, Length.

    # Default parameters.
    cpu_count            = 1
    dcache_size          = 4096
    icache_size          = 4096
    dcache_ways          = 1
    icache_ways          = 1
    coherent_dma         = False
    litedram_width       = 32
    dcache_width         = 32
    icache_width         = 32
    aes_instruction      = False
    expose_time          = False
    out_of_order_decoder = True
    privileged_debug     = False
    wishbone_memory      = False
    wishbone_force_32b   = False
    with_fpu             = False
    cpu_per_fpu          = 4
    with_rvc             = False
    dtlb_size            = 4
    itlb_size            = 4

    # Command line configuration arguments.
    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group(title="CPU options")
        cpu_group.add_argument("--cpu-count",                    default=1,           help="Number of CPU(s) in the cluster.", type=int)
        cpu_group.add_argument("--with-coherent-dma",            action="store_true", help="Enable Coherent DMA Slave interface.")
        cpu_group.add_argument("--without-coherent-dma",         action="store_true", help="Disable Coherent DMA Slave interface.")
        cpu_group.add_argument("--dcache-width",                 default=None,        help="L1 data cache bus width.")
        cpu_group.add_argument("--icache-width",                 default=None,        help="L1 instruction cache bus width.")
        cpu_group.add_argument("--dcache-size",                  default=None,        help="L1 data cache size in byte per CPU.")
        cpu_group.add_argument("--dcache-ways",                  default=None,        help="L1 data cache ways per CPU.")
        cpu_group.add_argument("--icache-size",                  default=None,        help="L1 instruction cache size in byte per CPU.")
        cpu_group.add_argument("--icache-ways",                  default=None,        help="L1 instruction cache ways per CPU")
        cpu_group.add_argument("--aes-instruction",              default=None,        help="Enable AES instruction acceleration.")
        cpu_group.add_argument("--without-out-of-order-decoder", action="store_true", help="Reduce area at cost of peripheral access speed")
        cpu_group.add_argument("--with-wishbone-memory",         action="store_true", help="Disable native LiteDRAM interface")
        cpu_group.add_argument("--with-privileged-debug",        action="store_true", help="Enable official RISC-V debug spec")
        cpu_group.add_argument("--wishbone-force-32b",           action="store_true", help="Force the wishbone bus to be 32 bits")
        cpu_group.add_argument("--with-fpu",                     action="store_true", help="Enable the F32/F64 FPU")
        cpu_group.add_argument("--cpu-per-fpu",                  default="4",         help="Maximal ratio between CPU count and FPU count. Will instanciate as many FPU as necessary.")
        cpu_group.add_argument("--with-rvc",                     action="store_true", help="Enable RISC-V compressed instruction support")
        cpu_group.add_argument("--dtlb-size",                    default=4,           help="Data TLB size.")
        cpu_group.add_argument("--itlb-size",                    default=4,           help="Instruction TLB size.")
        cpu_group.add_argument("--expose-time",                  action="store_true", help="Add CLINT time output.")

    @staticmethod
    def args_read(args):
        VexRiscvSMP.cpu_count = args.cpu_count
        if int(args.cpu_count) != 1:
            VexRiscvSMP.icache_width = 64
            VexRiscvSMP.dcache_width = 64
            VexRiscvSMP.dcache_size  = 8192
            VexRiscvSMP.icache_size  = 8192
            VexRiscvSMP.dcache_ways  = 2
            VexRiscvSMP.icache_ways  = 2
            VexRiscvSMP.coherent_dma = True
        if(args.with_coherent_dma):            VexRiscvSMP.coherent_dma          = bool(True)
        if(args.without_coherent_dma):         VexRiscvSMP.coherent_dma          = bool(False)
        if(args.dcache_width):                 VexRiscvSMP.dcache_width          = int(args.dcache_width)
        if(args.icache_width):                 VexRiscvSMP.icache_width          = int(args.icache_width)
        if(args.dcache_size):                  VexRiscvSMP.dcache_size           = int(args.dcache_size)
        if(args.icache_size):                  VexRiscvSMP.icache_size           = int(args.icache_size)
        if(args.dcache_ways):                  VexRiscvSMP.dcache_ways           = int(args.dcache_ways)
        if(args.icache_ways):                  VexRiscvSMP.icache_ways           = int(args.icache_ways)
        if(args.aes_instruction):              VexRiscvSMP.aes_instruction       = bool(args.aes_instruction)
        if(args.expose_time):                  VexRiscvSMP.expose_time       = bool(args.expose_time)
        if(args.without_out_of_order_decoder): VexRiscvSMP.out_of_order_decoder  = False
        if(args.with_privileged_debug):        VexRiscvSMP.privileged_debug      = True
        if(args.with_wishbone_memory):         VexRiscvSMP.wishbone_memory       = True
        if(args.wishbone_force_32b):           VexRiscvSMP.wishbone_force_32b    = True
        if(args.with_fpu):
            VexRiscvSMP.with_fpu     = True
            VexRiscvSMP.icache_width = 64
            VexRiscvSMP.dcache_width = 64 # Required for F64
        if(args.cpu_per_fpu):
            VexRiscvSMP.cpu_per_fpu = args.cpu_per_fpu
        if(args.with_rvc):
            VexRiscvSMP.with_rvc = True
        if(args.dtlb_size): VexRiscvSMP.dtlb_size = int(args.dtlb_size)
        if(args.itlb_size): VexRiscvSMP.itlb_size = int(args.itlb_size)

    # ABI.
    @staticmethod
    def get_abi():
        abi = "ilp32"
        if VexRiscvSMP.with_fpu:
            abi +="d"
        return abi

    # Arch.
    @staticmethod
    def get_arch():
        arch = "rv32i2p0_ma"
        if VexRiscvSMP.with_fpu:
            arch += "fd"
        if VexRiscvSMP.with_rvc:
            arch += "c"
        return arch

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "rom":      0x0000_0000,
            "sram":     0x1000_0000,
            "main_ram": 0x4000_0000,
            "csr":      0xf000_0000,
            "clint":    0xf001_0000,
            "plic":     0xf0c0_0000,
        }

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  f" -march={VexRiscvSMP.get_arch()} -mabi={VexRiscvSMP.get_abi()}"
        flags += f" -D__vexriscv__"
        flags += f" -DUART_POLLING"
        return flags

    # Reserved Interrupts.
    @property
    def reserved_interrupts(self):
        return {"noirq": 0}

    # Cluster Name Generation.
    @staticmethod
    def generate_cluster_name():
        ldw = f"Ldw{VexRiscvSMP.litedram_width}"
        VexRiscvSMP.cluster_name = f"VexRiscvLitexSmpCluster_" \
        f"Cc{VexRiscvSMP.cpu_count}"    \
        "_" \
        f"Iw{VexRiscvSMP.icache_width}" \
        f"Is{VexRiscvSMP.icache_size}"  \
        f"Iy{VexRiscvSMP.icache_ways}"  \
        "_" \
        f"Dw{VexRiscvSMP.dcache_width}" \
        f"Ds{VexRiscvSMP.dcache_size}"  \
        f"Dy{VexRiscvSMP.dcache_ways}"  \
        "_" \
        f"ITs{VexRiscvSMP.itlb_size}" \
        f"DTs{VexRiscvSMP.dtlb_size}" \
        f"{'_'+ldw if not VexRiscvSMP.wishbone_memory  else ''}" \
        f"{'_Cdma' if VexRiscvSMP.coherent_dma         else ''}" \
        f"{'_Aes'  if VexRiscvSMP.aes_instruction      else ''}" \
        f"{'_Time'  if VexRiscvSMP.expose_time      else ''}" \
        f"{'_Ood'  if VexRiscvSMP.out_of_order_decoder else ''}" \
        f"{'_Wm'   if VexRiscvSMP.wishbone_memory      else ''}" \
        f"{'_Wf32' if VexRiscvSMP.wishbone_force_32b   else ''}" \
        f"{'_Fpu' + str(VexRiscvSMP.cpu_per_fpu)  if VexRiscvSMP.with_fpu else ''}" \
        f"{'_Pd'   if VexRiscvSMP.privileged_debug else ''}" \
        f"{'_Rvc'  if VexRiscvSMP.with_rvc else ''}"

    # Default Configs Generation.
    @staticmethod
    def generate_default_configs():
        # Single cores.
        for data_width in [None, 16, 32, 64, 128]:
            if data_width is None:
                VexRiscvSMP.wishbone_memory = True
            else:
                VexRiscvSMP.wishbone_memory = False
                VexRiscvSMP.litedram_width = data_width
            VexRiscvSMP.icache_width   = 32
            VexRiscvSMP.dcache_width   = 32
            VexRiscvSMP.coherent_dma   = False
            VexRiscvSMP.cpu_count      = 1

            # Low cache amount.
            VexRiscvSMP.dcache_size    = 4096
            VexRiscvSMP.icache_size    = 4096
            VexRiscvSMP.dcache_ways    = 1
            VexRiscvSMP.icache_ways    = 1

            # Without DMA.
            VexRiscvSMP.coherent_dma   = False
            VexRiscvSMP.generate_cluster_name()
            VexRiscvSMP.generate_netlist()

            # With DMA.
            VexRiscvSMP.coherent_dma   = True
            VexRiscvSMP.generate_cluster_name()
            VexRiscvSMP.generate_netlist()

            # High cache amount.
            VexRiscvSMP.dcache_size    = 8192
            VexRiscvSMP.icache_size    = 8192
            VexRiscvSMP.dcache_ways    = 2
            VexRiscvSMP.icache_ways    = 2
            VexRiscvSMP.icache_width   = 32 if data_width is None \
                                              or data_width < 64 else 64
            VexRiscvSMP.dcache_width   = 32 if data_width is None \
                                              or data_width < 64 else 64

            # Without DMA.
            VexRiscvSMP.coherent_dma = False
            VexRiscvSMP.generate_cluster_name()
            VexRiscvSMP.generate_netlist()

            # With DMA.
            VexRiscvSMP.coherent_dma = True
            VexRiscvSMP.generate_cluster_name()
            VexRiscvSMP.generate_netlist()

        # Multi cores.
        for core_count in [2,4]:
            VexRiscvSMP.litedram_width = 128
            VexRiscvSMP.icache_width   = 64
            VexRiscvSMP.dcache_width   = 64
            VexRiscvSMP.dcache_size    = 8192
            VexRiscvSMP.icache_size    = 8192
            VexRiscvSMP.dcache_ways    = 2
            VexRiscvSMP.icache_ways    = 2
            VexRiscvSMP.coherent_dma   = True
            VexRiscvSMP.cpu_count      = core_count
            VexRiscvSMP.generate_cluster_name()
            VexRiscvSMP.generate_netlist()

    # Netlist Generation.
    @staticmethod
    def generate_netlist():
        print(f"Generating cluster netlist")
        vdir = get_data_mod("cpu", "vexriscv_smp").data_location
        gen_args = []
        if(VexRiscvSMP.coherent_dma):
            gen_args.append("--coherent-dma")
        gen_args.append(f"--cpu-count={VexRiscvSMP.cpu_count}")
        gen_args.append(f"--ibus-width={VexRiscvSMP.icache_width}")
        gen_args.append(f"--dbus-width={VexRiscvSMP.dcache_width}")
        gen_args.append(f"--dcache-size={VexRiscvSMP.dcache_size}")
        gen_args.append(f"--icache-size={VexRiscvSMP.icache_size}")
        gen_args.append(f"--dcache-ways={VexRiscvSMP.dcache_ways}")
        gen_args.append(f"--icache-ways={VexRiscvSMP.icache_ways}")
        gen_args.append(f"--litedram-width={VexRiscvSMP.litedram_width}")
        gen_args.append(f"--aes-instruction={VexRiscvSMP.aes_instruction}")
        gen_args.append(f"--expose-time={VexRiscvSMP.expose_time}")
        gen_args.append(f"--out-of-order-decoder={VexRiscvSMP.out_of_order_decoder}")
        gen_args.append(f"--privileged-debug={VexRiscvSMP.privileged_debug}")
        gen_args.append(f"--wishbone-memory={VexRiscvSMP.wishbone_memory}")
        if(VexRiscvSMP.wishbone_force_32b): gen_args.append(f"--wishbone-force-32b={VexRiscvSMP.wishbone_force_32b}")
        gen_args.append(f"--fpu={VexRiscvSMP.with_fpu}")
        gen_args.append(f"--cpu-per-fpu={VexRiscvSMP.cpu_per_fpu}")
        gen_args.append(f"--rvc={VexRiscvSMP.with_rvc}")
        gen_args.append(f"--netlist-name={VexRiscvSMP.cluster_name}")
        gen_args.append(f"--netlist-directory={vdir}")
        gen_args.append(f"--dtlb-size={VexRiscvSMP.dtlb_size}")
        gen_args.append(f"--itlb-size={VexRiscvSMP.itlb_size}")

        cmd = 'cd {path} && sbt "runMain vexriscv.demo.smp.VexRiscvLitexSmpClusterCmdGen {args}"'.format(path=os.path.join(vdir, "ext", "VexRiscv"), args=" ".join(gen_args))
        subprocess.check_call(cmd, shell=True)


    def __init__(self, platform, variant):
        self.platform         = platform
        self.variant          = variant
        self.human_name       = self.human_name + "-" + self.variant.upper()
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
        self.pbus             = pbus = wishbone.Interface(data_width={
            # Always 32-bit when using direct LiteDRAM interfaces.
            False : 32,
            # Else max of I/DCache-width.
            True  : max(VexRiscvSMP.icache_width, VexRiscvSMP.dcache_width),
        }[VexRiscvSMP.wishbone_memory and not VexRiscvSMP.wishbone_force_32b])
        self.periph_buses     = [pbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses     = []     # Memory buses (Connected directly to LiteDRAM).

        # # #

        self.cpu_params = dict(
            # Clk / Rst.
            i_debugCd_external_clk   = ClockSignal(),
            i_debugCd_external_reset = ResetSignal() | self.reset,

            # Interrupts.
            i_interrupts = self.interrupt,

            # JTAG.
            i_jtag_clk          = self.jtag_clk,
            i_debugPort_enable  = self.jtag_enable,
            i_debugPort_capture = self.jtag_capture,
            i_debugPort_shift   = self.jtag_shift,
            i_debugPort_update  = self.jtag_update,
            i_debugPort_reset   = self.jtag_reset,
            i_debugPort_tdi     = self.jtag_tdi,
            o_debugPort_tdo     = self.jtag_tdo,

            # Peripheral Bus (Master).
            o_peripheral_CYC      = pbus.cyc,
            o_peripheral_STB      = pbus.stb,
            i_peripheral_ACK      = pbus.ack,
            o_peripheral_WE       = pbus.we,
            o_peripheral_ADR      = pbus.adr,
            i_peripheral_DAT_MISO = pbus.dat_r,
            o_peripheral_DAT_MOSI = pbus.dat_w,
            o_peripheral_SEL      = pbus.sel,
            i_peripheral_ERR      = pbus.err,
            o_peripheral_CTI      = pbus.cti,
            o_peripheral_BTE      = pbus.bte
        )

        # DMA.
        if VexRiscvSMP.coherent_dma:
            self.dma_bus = dma_bus = wishbone.Interface(data_width=VexRiscvSMP.dcache_width, address_width=32)
            dma_bus_stall   = Signal()
            dma_bus_inhibit = Signal()
            self.cpu_params.update(
                # DMA Bus (Slave).
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

        # expose CLINT time
        if VexRiscvSMP.expose_time:
            self.clint_time = Signal(64)
            self.cpu_params.update(
                o_clint_time    = self.clint_time
            )

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        assert reset_address == 0x0000_0000

    def add_sources(self, platform):
        vdir = get_data_mod("cpu", "vexriscv_smp").data_location
        print(f"VexRiscv cluster : {self.cluster_name}")
        if not os.path.exists(os.path.join(vdir, self.cluster_name + ".v")):
            self.generate_netlist()


        # Add RAM.

        # By default, use Generic RAM implementation.
        ram_filename = "Ram_1w_1rs_Generic.v"
        # On Altera/Intel platforms, use specific implementation.
        from litex.build.altera import AlteraPlatform
        if isinstance(platform, AlteraPlatform):
            ram_filename = "Ram_1w_1rs_Intel.v"
            # define SYNTHESIS verilog name to avoid issues with unsupported
            # functions
            platform.toolchain.additional_qsf_commands.append(
                'set_global_assignment -name VERILOG_MACRO "SYNTHESIS=1"')
        # On Efinix platforms, use specific implementation.
        from litex.build.efinix import EfinixPlatform
        if isinstance(platform, EfinixPlatform):
            ram_filename = "Ram_1w_1rs_Efinix.v"
        platform.add_source(os.path.join(vdir, ram_filename), "verilog")

        # Add Cluster.
        cluster_filename = os.path.join(vdir,  self.cluster_name + ".v")
        def add_synthesis_define(filename):
            """Add SYNTHESIS define to verilog for toolchains requiring it, ex Gowin"""
            synthesis_define = "`define SYNTHESIS\n"
            # Read file.
            with open(filename, "r") as f:
                lines = f.readlines()
            # Modify file.
            with open(filename, "w") as f:
                if lines[0] != synthesis_define:
                    f.write(synthesis_define)
                for line in lines:
                    f.write(line)
        add_synthesis_define(cluster_filename)
        platform.add_source(cluster_filename, "verilog")

    def add_soc_components(self, soc):
        if self.variant == "linux":
            # Set UART/Timer0 CSRs to the ones used by OpenSBI.
            soc.csr.add("uart",   n=2)
            soc.csr.add("timer0", n=3)

            # Add OpenSBI region.
            soc.bus.add_region("opensbi", SoCRegion(origin=self.mem_map["main_ram"] + 0x00f0_0000, size=0x8_0000, cached=True, linker=True))

        # Define number of CPUs
        soc.add_config("CPU_COUNT", VexRiscvSMP.cpu_count)
        soc.add_config("CPU_ISA",   VexRiscvSMP.get_arch())
        soc.add_config("CPU_MMU",   "sv32")

        # Constants for cache so we can add them in the DTS.
        if (VexRiscvSMP.dcache_size > 0):
            soc.add_config("CPU_DCACHE_SIZE", VexRiscvSMP.dcache_size)
            soc.add_config("CPU_DCACHE_WAYS", VexRiscvSMP.dcache_ways)
            soc.add_config("CPU_DCACHE_BLOCK_SIZE", 64) # hardwired?
        if (VexRiscvSMP.icache_size > 0):
            soc.add_config("CPU_ICACHE_SIZE", VexRiscvSMP.icache_size)
            soc.add_config("CPU_ICACHE_WAYS", VexRiscvSMP.icache_ways)
            soc.add_config("CPU_ICACHE_BLOCK_SIZE", 64) # hardwired?
        # Constants for TLB so we can add them in the DTS
        # full associative so only the size is described.
        if (VexRiscvSMP.dtlb_size > 0):
            soc.add_config("CPU_DTLB_SIZE", VexRiscvSMP.dtlb_size)
            soc.add_config("CPU_DTLB_WAYS", VexRiscvSMP.dtlb_size)
        if (VexRiscvSMP.itlb_size > 0):
            soc.add_config("CPU_ITLB_SIZE", VexRiscvSMP.itlb_size)
            soc.add_config("CPU_ITLB_WAYS", VexRiscvSMP.itlb_size)

        # Add PLIC as Bus Slave
        self.plicbus = plicbus  = wishbone.Interface()
        self.cpu_params.update(
            i_plicWishbone_CYC       = plicbus.cyc,
            i_plicWishbone_STB       = plicbus.stb,
            o_plicWishbone_ACK       = plicbus.ack,
            i_plicWishbone_WE        = plicbus.we,
            i_plicWishbone_ADR       = plicbus.adr,
            o_plicWishbone_DAT_MISO  = plicbus.dat_r,
            i_plicWishbone_DAT_MOSI  = plicbus.dat_w
        )
        soc.bus.add_slave("plic", self.plicbus, region=SoCRegion(origin=soc.mem_map.get("plic"), size=0x40_0000, cached=False))

        # Add CLINT as Bus Slave
        self.clintbus = clintbus = wishbone.Interface()
        self.cpu_params.update(
            i_clintWishbone_CYC      = clintbus.cyc,
            i_clintWishbone_STB      = clintbus.stb,
            o_clintWishbone_ACK      = clintbus.ack,
            i_clintWishbone_WE       = clintbus.we,
            i_clintWishbone_ADR      = clintbus.adr,
            o_clintWishbone_DAT_MISO = clintbus.dat_r,
            i_clintWishbone_DAT_MOSI = clintbus.dat_w,
        )
        soc.bus.add_slave("clint", clintbus, region=SoCRegion(origin=soc.mem_map.get("clint"), size=0x1_0000, cached=False))

    def add_memory_buses(self, address_width, data_width):
        VexRiscvSMP.litedram_width = data_width

        from litedram.common import LiteDRAMNativePort
        if(not VexRiscvSMP.wishbone_memory):
            ibus = LiteDRAMNativePort(mode="both", address_width=32, data_width=VexRiscvSMP.litedram_width)
            dbus = LiteDRAMNativePort(mode="both", address_width=32, data_width=VexRiscvSMP.litedram_width)
            self.memory_buses.append(ibus)
            self.memory_buses.append(dbus)
            self.cpu_params.update(
                # Instruction Memory Bus (Master).
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

                # Data Memory Bus (Master).
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

    def do_finalize(self):
        assert hasattr(self, "reset_address")

        # When no Direct Memory Bus, do memory accesses through Wishbone Peripheral Bus.
        if len(self.memory_buses) == 0:
            if VexRiscvSMP.with_fpu and (not VexRiscvSMP.wishbone_memory and not VexRiscvSMP.wishbone_force_32b):
                raise ValueError("No Direct Memory Bus found, please add --with-wishbone-memory or --wishbone-force-32b to your build command.")
            else:
                VexRiscvSMP.wishbone_memory = True

        # Generate cluster name.
        VexRiscvSMP.generate_cluster_name()

        # Do verilog instance.
        self.specials += Instance(self.cluster_name, **self.cpu_params)

        # Add verilog sources
        self.add_sources(self.platform)

