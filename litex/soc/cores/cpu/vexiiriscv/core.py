#
# This file is part of LiteX.
#
# Copyright (c) 2020-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020-2022 Dolu1990 <charles.papon.90@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import hashlib
import subprocess
import re

from migen import *

from litex.build.efinix.efinity import EfinityToolchain
from litex.gen import *

from litex import get_data_mod
from litex.soc.cores.cpu.naxriscv import NaxRiscv

from litex.soc.interconnect import axi
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc import SoCRegion

from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32, CPU_GCC_TRIPLE_RISCV64

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard", "cached", "linux", "debian"]

# VexiiRiscv -----------------------------------------------------------------------------------------

class VexiiRiscv(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "vexiiriscv"
    human_name           = "VexiiRiscv"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x8000_0000: 0x8000_0000} # Origin, Length.

    # Default parameters.
    netlist_name     = None
    xlen             = 32
    internal_bus_width = 32
    litedram_width   = 32
    l2_bytes         = 0
    l2_ways          = 4
    l2_self_flush    = None
    with_rvc         = False
    with_rvm         = False
    with_rvf         = False
    with_rvd         = False
    with_rva         = False
    with_rvcbom      = False
    with_dma         = False
    with_axi3        = False
    with_opensbi     = False
    jtag_tap         = False
    jtag_instruction = False
    with_cpu_clk     = False
    vexii_video      = []
    vexii_macsg      = []
    vexii_args       = ""


    # ABI.
    @staticmethod
    def get_abi():
        abi = "lp64" if VexiiRiscv.xlen == 64 else "ilp32"
        if VexiiRiscv.with_rvd:
            abi +="d"
        elif VexiiRiscv.with_rvf:
            abi +="f"
        return abi

    # Arch.
    @staticmethod
    def get_arch():
        arch = f"rv{VexiiRiscv.xlen}i2p0_"
        if VexiiRiscv.with_rvm:
            arch += "m"
        if VexiiRiscv.with_rva:
            arch += "a"
        if VexiiRiscv.with_rvf:
            arch += "f"
        if VexiiRiscv.with_rvd:
            arch += "d"
        if VexiiRiscv.with_rvc:
            arch += "c"
        if VexiiRiscv.with_rvcbom:
            arch += "zicbom"
        # arch += "zicntr"
        # arch += "zicsr"
        # arch += "zifencei"
        # arch += "zihpm"
        # arch += "sscofpmf"
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
        flags =  f" -march={VexiiRiscv.get_arch()} -mabi={VexiiRiscv.get_abi()}"
        flags += f" -D__VexiiRiscv__"
        flags += f" -D__riscv_plic__"
        if VexiiRiscv.with_rvcbom:
            flags += f" -D__riscv_zicbom__"
        return flags

    # Reserved Interrupts.
    @property
    def reserved_interrupts(self):
        return {"noirq": 0}

    # Command line configuration arguments.
    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group(title="CPU options")

        cpu_group.add_argument("--vexii-args",            default="",            help="Specify the CPU configuration")
        # cpu_group.add_argument("--xlen",                  default=32,            help="Specify the RISC-V data width.")
        cpu_group.add_argument("--cpu-count",             default=1,             help="How many VexiiRiscv CPU.")
        cpu_group.add_argument("--with-coherent-dma",     action="store_true",   help="Enable coherent DMA accesses.")
        cpu_group.add_argument("--with-jtag-tap",         action="store_true",   help="Add a embedded JTAG tap for debugging.")
        cpu_group.add_argument("--with-jtag-instruction", action="store_true",   help="Add a JTAG instruction port which implement tunneling for debugging (TAP not included).")
        cpu_group.add_argument("--update-repo",           default="recommended", choices=["latest","wipe+latest","recommended","wipe+recommended","no"], help="Specify how the VexiiRiscv & SpinalHDL repo should be updated (latest: update to HEAD, recommended: Update to known compatible version, no: Don't update, wipe+*: Do clean&reset before checkout)")
        cpu_group.add_argument("--no-netlist-cache",      action="store_true",   help="Always (re-)build the netlist.")
        cpu_group.add_argument("--with-cpu-clk",          action="store_true",   help="The CPUs will use a decoupled clock")
        # cpu_group.add_argument("--with-fpu",              action="store_true",   help="Enable the F32/F64 FPU.")
        # cpu_group.add_argument("--with-rvc",              action="store_true",   help="Enable the Compress ISA extension.")
        cpu_group.add_argument("--l2-bytes",              default=0,             help="VexiiRiscv L2 bytes, default 128 KB.")
        cpu_group.add_argument("--l2-ways",               default=0,             help="VexiiRiscv L2 ways, default 8.")
        cpu_group.add_argument("--l2-self-flush",         default=None,          help="VexiiRiscv L2 ways will self flush on from,to,cycles")
        cpu_group.add_argument("--with-axi3",             action="store_true",   help="mbus will be axi3 instead of axi4")
        cpu_group.add_argument("--vexii-video",           action="append",  default=[], help="Add the memory coherent video controller")
        cpu_group.add_argument("--vexii-macsg",           action="append",  default=[], help="Add the memory coherent ethernet mac")




    @staticmethod
    def args_read(args):
        print(args)

        vdir = get_data_mod("cpu", "vexiiriscv").data_location
        ndir = os.path.join(vdir, "ext", "VexiiRiscv")

        NaxRiscv.git_setup("VexiiRiscv", ndir, "https://github.com/SpinalHDL/VexiiRiscv.git", "dev", "79c9d26e", args.update_repo)

        if not args.cpu_variant:
            args.cpu_variant = "standard"

        VexiiRiscv.vexii_args += " --with-mul --with-div --allow-bypass-from=0 --performance-counters=0"
        VexiiRiscv.vexii_args += " --fetch-l1 --fetch-l1-ways=2"
        VexiiRiscv.vexii_args += " --lsu-l1 --lsu-l1-ways=2  --with-lsu-bypass"
        VexiiRiscv.vexii_args += " --relaxed-branch"

        if args.cpu_variant in ["linux", "debian"]:
            VexiiRiscv.with_opensbi = True
            VexiiRiscv.vexii_args += " --with-rva --with-supervisor"
            VexiiRiscv.vexii_args += " --fetch-l1-ways=4 --fetch-l1-mem-data-width-min=64"
            VexiiRiscv.vexii_args += " --lsu-l1-ways=4 --lsu-l1-mem-data-width-min=64"

        if args.cpu_variant in ["debian"]:
            VexiiRiscv.vexii_args += " --xlen=64 --with-rvc --with-rvf --with-rvd --fma-reduced-accuracy --fpu-ignore-subnormal"

        if args.cpu_variant in ["linux", "debian"]:
            VexiiRiscv.vexii_args += " --with-btb --with-ras --with-gshare"



        VexiiRiscv.jtag_tap         = args.with_jtag_tap
        VexiiRiscv.jtag_instruction = args.with_jtag_instruction
        VexiiRiscv.with_dma         = args.with_coherent_dma
        VexiiRiscv.with_axi3        = args.with_axi3
        VexiiRiscv.update_repo      = args.update_repo
        VexiiRiscv.no_netlist_cache = args.no_netlist_cache
        VexiiRiscv.vexii_args      += " " + args.vexii_args

        md5_hash = hashlib.md5()
        md5_hash.update(VexiiRiscv.vexii_args.encode('utf-8'))
        vexii_args_hash = md5_hash.hexdigest()
        ppath = os.path.join(vdir, str(vexii_args_hash) + ".py")
        if VexiiRiscv.no_netlist_cache or not os.path.exists(ppath):
            cmd = f"""cd {ndir} && sbt "runMain vexiiriscv.soc.litex.PythonArgsGen {VexiiRiscv.vexii_args} --python-file={str(ppath)}\""""
            subprocess.check_call(cmd, shell=True)
        # Loads variables like VexiiRiscv.with_rvm, that set the RISC-V extensions.
        with open(ppath) as file:
            exec(file.read())

        if VexiiRiscv.xlen == 64:
            VexiiRiscv.gcc_triple           = CPU_GCC_TRIPLE_RISCV64
        VexiiRiscv.linker_output_format = f"elf{VexiiRiscv.xlen}-littleriscv"
        if args.cpu_count:
            VexiiRiscv.cpu_count = args.cpu_count
        if args.l2_bytes:
            VexiiRiscv.l2_bytes = args.l2_bytes
        VexiiRiscv.with_cpu_clk = args.with_cpu_clk
        if args.l2_ways:
            VexiiRiscv.l2_ways = args.l2_ways
        if args.l2_self_flush:
            VexiiRiscv.l2_self_flush = args.l2_self_flush
        VexiiRiscv.vexii_video = args.vexii_video
        VexiiRiscv.vexii_macsg = args.vexii_macsg


    def __init__(self, platform, variant):
        self.platform         = platform
        self.variant          = "standard"
        self.reset            = Signal()
        self.interrupt        = Signal(32)
        self.pbus             = pbus = axi.AXILiteInterface(address_width=32, data_width=32)

        self.periph_buses     = [pbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses     = []           # Memory buses (Connected directly to LiteDRAM).

        # # #

        self.tracer_valid = Signal()
        self.tracer_payload = Signal(8)

        # CPU Instance.
        self.cpu_params = dict(
            # Clk/Rst.
            i_litex_clk   = ClockSignal("sys"),
            i_litex_reset = ResetSignal("sys") | self.reset,

            o_debug=self.tracer_payload,

            # Patcher/Tracer.
            # o_patcher_tracer_valid   = self.tracer_valid,
            # o_patcher_tracer_payload = self.tracer_payload,

            # Interrupt.
            i_peripheral_externalInterrupts_port = self.interrupt,

            # Peripheral Memory Bus (AXI Lite Slave).
            o_pBus_awvalid = pbus.aw.valid,
            i_pBus_awready = pbus.aw.ready,
            o_pBus_awaddr  = pbus.aw.addr,
            o_pBus_awprot  = Open(),
            o_pBus_wvalid  = pbus.w.valid,
            i_pBus_wready  = pbus.w.ready,
            o_pBus_wdata   = pbus.w.data,
            o_pBus_wstrb   = pbus.w.strb,
            i_pBus_bvalid  = pbus.b.valid,
            o_pBus_bready  = pbus.b.ready,
            i_pBus_bresp   = pbus.b.resp,
            o_pBus_arvalid = pbus.ar.valid,
            i_pBus_arready = pbus.ar.ready,
            o_pBus_araddr  = pbus.ar.addr,
            o_pBus_arprot  = Open(),
            i_pBus_rvalid  = pbus.r.valid,
            o_pBus_rready  = pbus.r.ready,
            i_pBus_rdata   = pbus.r.data,
            i_pBus_rresp   = pbus.r.resp,
        )

        if VexiiRiscv.with_cpu_clk:
            self.cpu_clk = Signal()
            self.cpu_params.update(
                i_cpu_clk = self.cpu_clk
            )

        if VexiiRiscv.with_dma:
            self.dma_bus = dma_bus = axi.AXIInterface(data_width=VexiiRiscv.internal_bus_width, address_width=32, id_width=4)

            self.cpu_params.update(
                # DMA Bus.
                # --------
                # AW Channel.
                o_dma_bus_awready = dma_bus.aw.ready,
                i_dma_bus_awvalid = dma_bus.aw.valid,
                i_dma_bus_awid    = dma_bus.aw.id,
                i_dma_bus_awaddr  = dma_bus.aw.addr,
                i_dma_bus_awlen   = dma_bus.aw.len,
                i_dma_bus_awsize  = dma_bus.aw.size,
                i_dma_bus_awburst = dma_bus.aw.burst,
                i_dma_bus_awlock  = dma_bus.aw.lock,
                i_dma_bus_awcache = dma_bus.aw.cache,
                i_dma_bus_awprot  = dma_bus.aw.prot,
                i_dma_bus_awqos   = dma_bus.aw.qos,

                # W Channel.
                o_dma_bus_wready  = dma_bus.w.ready,
                i_dma_bus_wvalid  = dma_bus.w.valid,
                i_dma_bus_wdata   = dma_bus.w.data,
                i_dma_bus_wstrb   = dma_bus.w.strb,
                i_dma_bus_wlast   = dma_bus.w.last,

                # B Channel.
                i_dma_bus_bready  = dma_bus.b.ready,
                o_dma_bus_bvalid  = dma_bus.b.valid,
                o_dma_bus_bid     = dma_bus.b.id,
                o_dma_bus_bresp   = dma_bus.b.resp,

                # AR Channel.
                o_dma_bus_arready = dma_bus.ar.ready,
                i_dma_bus_arvalid = dma_bus.ar.valid,
                i_dma_bus_arid    = dma_bus.ar.id,
                i_dma_bus_araddr  = dma_bus.ar.addr,
                i_dma_bus_arlen   = dma_bus.ar.len,
                i_dma_bus_arsize  = dma_bus.ar.size,
                i_dma_bus_arburst = dma_bus.ar.burst,
                i_dma_bus_arlock  = dma_bus.ar.lock,
                i_dma_bus_arcache = dma_bus.ar.cache,
                i_dma_bus_arprot  = dma_bus.ar.prot,
                i_dma_bus_arqos   = dma_bus.ar.qos,

                # R Channel.
                i_dma_bus_rready  = dma_bus.r.ready,
                o_dma_bus_rvalid  = dma_bus.r.valid,
                o_dma_bus_rid     = dma_bus.r.id,
                o_dma_bus_rdata   = dma_bus.r.data,
                o_dma_bus_rresp   = dma_bus.r.resp,
                o_dma_bus_rlast   = dma_bus.r.last,
            )

        for video in VexiiRiscv.vexii_video:
            args = {}
            for i, val in enumerate(video.split(",")):
                name, value = val.split("=")
                args.update({name: value})
            name = args["name"]
            clk = Signal()
            hsync = Signal()
            vsync = Signal()
            color_en = Signal()
            color = Signal(16)
            setattr(self, name + "_clk", clk)
            setattr(self, name + "_hsync", hsync)
            setattr(self, name + "_vsync", vsync)
            setattr(self, name + "_color_en", color_en)
            setattr(self, name + "_color", color)
            self.cpu_params["o_" + name + "_clk"] = clk
            self.cpu_params["o_" + name + "_hSync"] = hsync
            self.cpu_params["o_" + name + "_vSync"] = vsync
            self.cpu_params["o_" + name + "_colorEn"] = color_en
            self.cpu_params["o_" + name + "_color"] = color

        def add_io(direction, prefix, name, width):
            composed = prefix + "_" + name
            sig = Signal(width, name = composed)
            setattr(self, composed, sig)
            self.cpu_params[direction + "_" + composed] = sig

        for macsg in VexiiRiscv.vexii_macsg:
            args = {}
            for i, val in enumerate(macsg.split(",")):
                name, value = val.split("=")
                args.update({name: value})
            name = args["name"]
            add_io("i", name, "tx_ref_clk", 1)
            add_io("o", name, "tx_ctl", 2)
            add_io("o", name, "tx_d", 8)
            add_io("o", name, "tx_clk", 2)

            add_io("i", name, "rx_ctl", 2)
            add_io("i", name, "rx_d", 8)
            add_io("i", name, "rx_clk", 1)





    def set_reset_address(self, reset_address):
        VexiiRiscv.reset_address = reset_address
        VexiiRiscv.vexii_args += f" --reset-vector {reset_address}"

    # Cluster Name Generation.
    @staticmethod
    def generate_netlist_name():
        md5_hash = hashlib.md5()
        md5_hash.update(str(VexiiRiscv.reset_address).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.litedram_width).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.xlen).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.cpu_count).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.l2_bytes).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.with_cpu_clk).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.l2_ways).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.l2_self_flush).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.jtag_tap).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.jtag_instruction).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.with_dma).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.with_axi3).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.memory_regions).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.vexii_args).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.vexii_video).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.vexii_macsg).encode('utf-8'))
        md5_hash.update(str(VexiiRiscv.with_opensbi).encode('utf-8'))

        # md5_hash.update(str(VexiiRiscv.internal_bus_width).encode('utf-8'))


        digest = md5_hash.hexdigest()
        VexiiRiscv.netlist_name = "VexiiRiscvLitex_" + digest

    # Netlist Generation.
    @staticmethod
    def generate_netlist():
        vdir = get_data_mod("cpu", "vexiiriscv").data_location
        ndir = os.path.join(vdir, "ext", "VexiiRiscv")
        sdir = os.path.join(vdir, "ext", "SpinalHDL")

        gen_args = []
        gen_args.append(f"--netlist-name={VexiiRiscv.netlist_name}")
        gen_args.append(f"--netlist-directory={vdir}")
        gen_args.append(VexiiRiscv.vexii_args)
        gen_args.append(f"--cpu-count={VexiiRiscv.cpu_count}")
        gen_args.append(f"--l2-bytes={VexiiRiscv.l2_bytes}")
        if VexiiRiscv.with_cpu_clk:
            gen_args.append("--with-cpu-clk")
        gen_args.append(f"--l2-ways={VexiiRiscv.l2_ways}")
        if VexiiRiscv.l2_self_flush:
            gen_args.append(f"--l2-self-flush={VexiiRiscv.l2_self_flush}")
        gen_args.append(f"--litedram-width={VexiiRiscv.litedram_width}")
        # gen_args.append(f"--internal_bus_width={VexiiRiscv.internal_bus_width}")
        for region in VexiiRiscv.memory_regions:
            gen_args.append(f"--memory-region={region[0]},{region[1]},{region[2]},{region[3]}")
        if(VexiiRiscv.jtag_tap) :
            gen_args.append(f"--with-jtag-tap")
        if(VexiiRiscv.jtag_instruction) :
            gen_args.append(f"--with-jtag-instruction")
        if(VexiiRiscv.with_dma) :
            gen_args.append(f"--with-dma")
        if(VexiiRiscv.with_axi3) :
            gen_args.append(f"--with-axi3")
        for arg in VexiiRiscv.vexii_video:
            gen_args.append(f"--video {arg}")
        for arg in VexiiRiscv.vexii_macsg:
            gen_args.append(f"--mac-sg {arg}")


        cmd = f"""cd {ndir} && sbt "runMain vexiiriscv.soc.litex.SocGen {" ".join(gen_args)}\""""
        print("VexiiRiscv generation command :")
        print(cmd)
        subprocess.check_call(cmd, shell=True)


    def add_sources(self, platform):
        vdir = get_data_mod("cpu", "vexiiriscv").data_location
        print(f"VexiiRiscv netlist : {self.netlist_name}")

        if VexiiRiscv.no_netlist_cache or not os.path.exists(os.path.join(vdir, self.netlist_name + ".v")):
            self.generate_netlist()

        # Add RAM.
        # By default, use Generic RAM implementation.
        ram_filename = "Ram_1w_1rs_Generic.v"
        lutram_filename = "Ram_1w_1ra_Generic.v"
        # On Altera/Intel platforms, use specific implementation.
        from litex.build.altera import AlteraPlatform
        if isinstance(platform, AlteraPlatform):
            ram_filename = "Ram_1w_1rs_Intel.v"
        # On Efinix platforms, use specific implementation.
        from litex.build.efinix import EfinixPlatform
        if isinstance(platform, EfinixPlatform):
            ram_filename = "Ram_1w_1rs_Efinix.v"
        platform.add_source(os.path.join(vdir, ram_filename), "verilog")
        platform.add_source(os.path.join(vdir, lutram_filename), "verilog")

        # Add Cluster.
        platform.add_source(os.path.join(vdir,  self.netlist_name + ".v"), "verilog")

    def add_soc_components(self, soc):
        # Set Human-name.
        self.human_name = f"{self.human_name} ({VexiiRiscv.get_arch()})"

        if VexiiRiscv.with_opensbi:
            # Set UART/Timer0 CSRs to the ones used by OpenSBI.
            soc.csr.add("uart",   n=2)
            soc.csr.add("timer0", n=3)

            # Add OpenSBI region.
            soc.bus.add_region("opensbi", SoCRegion(origin=self.mem_map["main_ram"] + 0x00f0_0000, size=0x8_0000, cached=True, linker=True))

        # Define ISA.
        soc.add_config("CPU_COUNT", VexiiRiscv.cpu_count)
        soc.add_config("CPU_ISA", VexiiRiscv.get_arch())
        soc.add_config("CPU_MMU", {32 : "sv32", 64 : "sv39"}[VexiiRiscv.xlen])

        soc.bus.add_region("plic",  SoCRegion(origin=soc.mem_map.get("plic"),  size=0x40_0000, cached=False,  linker=True))
        soc.bus.add_region("clint", SoCRegion(origin=soc.mem_map.get("clint"), size= 0x1_0000, cached=False,  linker=True))

        if VexiiRiscv.jtag_tap:
            self.jtag_tms = Signal()
            self.jtag_clk = Signal()
            self.jtag_tdi = Signal()
            self.jtag_tdo = Signal()

            self.cpu_params.update(
                i_debug_tap_jtag_tms = self.jtag_tms,
                i_debug_tap_jtag_tck = self.jtag_clk,
                i_debug_tap_jtag_tdi = self.jtag_tdi,
                o_debug_tap_jtag_tdo = self.jtag_tdo,
            )

        if VexiiRiscv.jtag_instruction:
            self.jtag_clk     = Signal()
            self.jtag_enable  = Signal()
            self.jtag_capture = Signal()
            self.jtag_shift   = Signal()
            self.jtag_update  = Signal()
            self.jtag_reset   = Signal()
            self.jtag_tdo     = Signal()
            self.jtag_tdi     = Signal()
            self.cpu_params.update(
                i_debug_tck                             = self.jtag_clk,
                i_debug_instruction_instruction_enable  = self.jtag_enable,
                i_debug_instruction_instruction_capture = self.jtag_capture,
                i_debug_instruction_instruction_shift   = self.jtag_shift,
                i_debug_instruction_instruction_update  = self.jtag_update,
                i_debug_instruction_instruction_reset   = self.jtag_reset,
                i_debug_instruction_instruction_tdi     = self.jtag_tdi,
                o_debug_instruction_instruction_tdo     = self.jtag_tdo,
            )

        if VexiiRiscv.jtag_instruction or VexiiRiscv.jtag_tap:
            # Create PoR Clk Domain for debug_reset.
            self.cd_debug_por = ClockDomain()
            self.comb += self.cd_debug_por.clk.eq(ClockSignal("sys"))

            # Create PoR debug_reset.
            debug_reset = Signal(reset=1)
            self.sync.debug_por += debug_reset.eq(0)

            # Debug resets.
            debug_ndmreset      = Signal()
            debug_ndmreset_last = Signal()
            debug_ndmreset_rise = Signal() # debug_ndmreset_rise is necessary because the PLL which generate the clock will be reseted aswell, so we need to sneak in a single cycle reset :(
            self.cpu_params.update(
                i_debugReset        = debug_reset,
                o_debug_dm_ndmreset = debug_ndmreset,
            )

            # Reset SoC's CRG when debug_ndmreset rising edge.
            self.sync.debug_por += debug_ndmreset_last.eq(debug_ndmreset)
            self.comb += debug_ndmreset_rise.eq(debug_ndmreset & ~debug_ndmreset_last)
            if soc.get_build_name() == "sim":
                self.comb += If(debug_ndmreset_rise, soc.crg.cd_sys.rst.eq(1))
            else:
                if hasattr(soc.crg.pll, "locked") and isinstance(self.platform.toolchain, EfinityToolchain):
                    self.comb += If(debug_ndmreset, soc.crg.pll.locked.eq(0))
                elif hasattr(soc.crg, "rst"):
                    self.comb += If(debug_ndmreset_rise, soc.crg.rst.eq(1))
                else:
                    raise Exception("Pll has no reset ?")

        self.soc_bus = soc.bus # FIXME: Save SoC Bus instance to retrieve the final mem layout on finalization.

    def add_memory_buses(self, address_width, data_width):
        VexiiRiscv.litedram_width = data_width

        mbus = axi.AXIInterface(
            data_width    = VexiiRiscv.litedram_width,
            address_width = 32,
            id_width      = 8,
            version       = "axi3" if VexiiRiscv.with_axi3 else "axi4"
        )
        self.mBus_awallStrb = Signal()
        self.memory_buses.append(mbus)

        self.comb += mbus.aw.cache.eq(0xF)
        self.comb += mbus.aw.lock.eq(0)
        self.comb += mbus.aw.prot.eq(1)
        self.comb += mbus.aw.qos.eq(0)
        #self.comb += mbus.aw.region.eq(0)

        self.comb += mbus.ar.cache.eq(0xF)
        self.comb += mbus.ar.lock.eq(0)
        self.comb += mbus.ar.prot.eq(1)
        self.comb += mbus.ar.qos.eq(0)
        #self.comb += mbus.ar.region.eq(0)

        self.cpu_params.update(
            # Memory Bus (Master).
            # --------------------
            # AW Channel.
            o_mBus_awvalid   = mbus.aw.valid,
            i_mBus_awready   = mbus.aw.ready,
            o_mBus_awaddr    = mbus.aw.addr,
            o_mBus_awid      = mbus.aw.id,
            o_mBus_awlen     = mbus.aw.len,
            o_mBus_awsize    = mbus.aw.size,
            o_mBus_awburst   = mbus.aw.burst,
            o_mBus_awallStrb = self.mBus_awallStrb,
            # W Channel.
            o_mBus_wvalid    = mbus.w.valid,
            i_mBus_wready    = mbus.w.ready,
            o_mBus_wdata     = mbus.w.data,
            o_mBus_wstrb     = mbus.w.strb,
            o_mBus_wlast     = mbus.w.last,
            # B Channel.
            i_mBus_bvalid    = mbus.b.valid,
            o_mBus_bready    = mbus.b.ready,
            i_mBus_bid       = mbus.b.id,
            i_mBus_bresp     = mbus.b.resp,
            # AR Channel.
            o_mBus_arvalid   = mbus.ar.valid,
            i_mBus_arready   = mbus.ar.ready,
            o_mBus_araddr    = mbus.ar.addr,
            o_mBus_arid      = mbus.ar.id,
            o_mBus_arlen     = mbus.ar.len,
            o_mBus_arsize    = mbus.ar.size,
            o_mBus_arburst   = mbus.ar.burst,
            # R Channel.
            i_mBus_rvalid    = mbus.r.valid,
            o_mBus_rready    = mbus.r.ready,
            i_mBus_rdata     = mbus.r.data,
            i_mBus_rid       = mbus.r.id,
            i_mBus_rresp     = mbus.r.resp,
            i_mBus_rlast     = mbus.r.last,
        )

        if VexiiRiscv.with_axi3:
            self.cpu_params.update(
                o_mBus_wid=mbus.w.id
            )

    def add_jtag(self, pads):
        self.comb += [
            self.jtag_tms.eq(pads.tms),
            self.jtag_clk.eq(pads.tck),
            self.jtag_tdi.eq(pads.tdi),
            pads.tdo.eq(self.jtag_tdo),
        ]

    def do_finalize(self):
        assert hasattr(self, "reset_address")

        # Generate memory map from CPU perspective
        # vexiiriscv modes:
        # r,w,x,c  : readable, writeable, executable, caching allowed
        # io       : IO region (Implies P bus, preserve memory order, no dcache)
        # vexiiriscv bus:
        # p        : peripheral
        # m        : memory
        VexiiRiscv.memory_regions = []
        # for name, region in self.soc_bus.io_regions.items():
        #     VexiiRiscv.memory_regions.append( (region.origin, region.size, "io", "p") ) # IO is only allowed on the p bus
        for name, region in self.soc_bus.regions.items():
            if region.linker: # Remove virtual regions.
                continue
            if len(self.memory_buses) and name == 'main_ram': # m bus
                bus = "m"
            else:
                bus = "p"
            mode = region.mode
            mode += "c" if region.cached else ""
            VexiiRiscv.memory_regions.append( (region.origin, region.size, mode, bus) )

        from litex.build.efinix import EfinixPlatform
        if isinstance(self.platform, EfinixPlatform):
            VexiiRiscv.vexii_args = "--mmu-sync-read " + VexiiRiscv.vexii_args

        self.generate_netlist_name()

        # Do verilog instance.
        self.specials += Instance(self.netlist_name, **self.cpu_params)

        # Add verilog sources.
        self.add_sources(self.platform)
