#
# This file is part of LiteX.
#
# Copyright (c) 2020-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020-2022 Dolu1990 <charles.papon.90@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import hashlib
import subprocess

from migen import *

from litex.gen import *

from litex import get_data_mod

from litex.soc.interconnect import axi
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc import SoCRegion

from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32, CPU_GCC_TRIPLE_RISCV64

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = {
    "standard": "NaxRiscv",
}

# NaxRiscv -----------------------------------------------------------------------------------------

class NaxRiscv(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "naxriscv"
    human_name           = "NaxRiscv"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x8000_0000: 0x8000_0000} # Origin, Length.

    # Default parameters.
    with_fpu         = False
    with_rvc         = False
    scala_args       = []
    scala_files      = ["gen.scala"]
    netlist_name     = None
    scala_paths      = []
    xlen             = 32
    cpu_count        = 1
    jtag_tap         = False
    jtag_instruction = False
    with_dma         = False
    litedram_width   = 32
    l2_bytes        = 128*1024
    l2_ways         = 8

    # ABI.
    @staticmethod
    def get_abi():
        abi = "lp64" if NaxRiscv.xlen == 64 else "ilp32"
        if NaxRiscv.with_fpu:
            abi +="d"
        return abi

    # Arch.
    @staticmethod
    def get_arch():
        arch = f"rv{NaxRiscv.xlen}i2p0_ma"
        if NaxRiscv.with_fpu:
            arch += "fd"
        if NaxRiscv.with_rvc:
            arch += "c"
        return arch

    # Memory Mapping.
    @property
    def mem_map(self): # TODO
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
        flags =  f" -march={NaxRiscv.get_arch()} -mabi={NaxRiscv.get_abi()}"
        flags += f" -D__NaxRiscv__"
        flags += f" -D__riscv_plic__"
        return flags

    # Reserved Interrupts.
    @property
    def reserved_interrupts(self):
        return {"noirq": 0}

    # Command line configuration arguments.
    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group(title="CPU options")
        cpu_group.add_argument("--scala-file",            action="append",       help="Specify the scala files used to configure NaxRiscv.")
        cpu_group.add_argument("--scala-args",            action="append",       help="Add arguements for the scala run time. Ex : --scala-args 'rvc=true,mmu=false'")
        cpu_group.add_argument("--xlen",                  default=32,            help="Specify the RISC-V data width.")
        cpu_group.add_argument("--cpu-count",             default=1,             help="How many NaxRiscv CPU.")
        cpu_group.add_argument("--with-coherent-dma",     action="store_true",   help="Enable coherent DMA accesses.")
        cpu_group.add_argument("--with-jtag-tap",         action="store_true",   help="Add a embedded JTAG tap for debugging.")
        cpu_group.add_argument("--with-jtag-instruction", action="store_true",   help="Add a JTAG instruction port which implement tunneling for debugging (TAP not included).")
        cpu_group.add_argument("--update-repo",           default="recommended", choices=["latest","wipe+latest","recommended","wipe+recommended","no"], help="Specify how the NaxRiscv & SpinalHDL repo should be updated (latest: update to HEAD, recommended: Update to known compatible version, no: Don't update, wipe+*: Do clean&reset before checkout)")
        cpu_group.add_argument("--no-netlist-cache",      action="store_true",   help="Always (re-)build the netlist.")
        cpu_group.add_argument("--with-fpu",              action="store_true",   help="Enable the F32/F64 FPU.")
        cpu_group.add_argument("--with-rvc",              action="store_true",   help="Enable the Compress ISA extension.")
        cpu_group.add_argument("--l2-bytes",              default=128*1024,      help="NaxRiscv L2 bytes, default 128 KB.")
        cpu_group.add_argument("--l2-ways",               default=8,             help="NaxRiscv L2 ways, default 8.")

    @staticmethod
    def args_read(args):
        print(args)
        NaxRiscv.jtag_tap         = args.with_jtag_tap
        NaxRiscv.jtag_instruction = args.with_jtag_instruction
        NaxRiscv.with_dma         = args.with_coherent_dma
        NaxRiscv.update_repo      = args.update_repo
        NaxRiscv.no_netlist_cache = args.no_netlist_cache
        NaxRiscv.with_fpu         = args.with_fpu
        NaxRiscv.with_rvc         = args.with_rvc
        if args.scala_file:
            NaxRiscv.scala_files = args.scala_file
        if args.scala_args:
            NaxRiscv.scala_args  = args.scala_args
            print(args.scala_args)
        if args.xlen:
            xlen = int(args.xlen)
            NaxRiscv.xlen                 = xlen
            NaxRiscv.data_width           = xlen
            NaxRiscv.gcc_triple           = CPU_GCC_TRIPLE_RISCV64 if xlen == 64 else CPU_GCC_TRIPLE_RISCV32
            NaxRiscv.linker_output_format = f"elf{xlen}-littleriscv"
        if args.cpu_count:
            NaxRiscv.cpu_count = int(args.cpu_count)
        if args.l2_bytes:
            NaxRiscv.l2_bytes = int(args.l2_bytes)
        if args.l2_ways:
            NaxRiscv.l2_ways = int(args.l2_ways)


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
            i_socClk     = ClockSignal("sys"),
            i_asyncReset = ResetSignal("sys") | self.reset,

            # Patcher/Tracer.
            o_patcher_tracer_valid   = self.tracer_valid,
            o_patcher_tracer_payload = self.tracer_payload,

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

        if NaxRiscv.with_dma:
            self.dma_bus = dma_bus = axi.AXIInterface(data_width=64, address_width=32, id_width=4)

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

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address

    @staticmethod
    def find_scala_files():
        vdir = get_data_mod("cpu", "naxriscv").data_location
        for file in NaxRiscv.scala_files:
            if os.path.exists(file):
                NaxRiscv.scala_paths.append(os.path.abspath(file))
            else:
                path = os.path.join(vdir, "configs", file)
                if os.path.exists(path):
                    NaxRiscv.scala_paths.append(path)
                else:
                    raise Exception(f"Can't find NaxRiscv's {file}")

    # Cluster Name Generation.
    @staticmethod
    def generate_netlist_name(reset_address):
        md5_hash = hashlib.md5()
        md5_hash.update(str(reset_address).encode('utf-8'))
        md5_hash.update(str(NaxRiscv.litedram_width).encode('utf-8'))
        md5_hash.update(str(NaxRiscv.xlen).encode('utf-8'))
        md5_hash.update(str(NaxRiscv.cpu_count).encode('utf-8'))
        md5_hash.update(str(NaxRiscv.l2_bytes).encode('utf-8'))
        md5_hash.update(str(NaxRiscv.l2_ways).encode('utf-8'))
        md5_hash.update(str(NaxRiscv.jtag_tap).encode('utf-8'))
        md5_hash.update(str(NaxRiscv.jtag_instruction).encode('utf-8'))
        md5_hash.update(str(NaxRiscv.with_dma).encode('utf-8'))
        md5_hash.update(str(NaxRiscv.memory_regions).encode('utf-8'))
        for args in NaxRiscv.scala_args:
            md5_hash.update(args.encode('utf-8'))
        for file in NaxRiscv.scala_paths:
            a_file = open(file, "rb")
            content = a_file.read()
            md5_hash.update(content)

        digest = md5_hash.hexdigest()
        NaxRiscv.netlist_name = "NaxRiscvLitex_" + digest


    @staticmethod
    def git_setup(name, dir, repo, branch, hash, update):
        if update == "no":
            return
        if "recommended" not in update:
            hash = ""
        if not os.path.exists(dir):
            # Clone Repo.
            print(f"Cloning {name} Git repository...")
            subprocess.check_call("git clone {url} {options} --recursive".format(
                url     = repo,
                options = dir
            ), shell=True)
            # Use specific SHA1 (Optional).
        print(f"Updating {name} Git repository...")
        cwd = os.getcwd()
        os.chdir(os.path.join(dir))
        wipe_cmd = "&& git clean --force -d -x && git reset --hard" if "wipe" in update else ""
        checkout_cmd = f"&& git checkout {hash} && git submodule update --init --recursive" if hash is not None else ""
        subprocess.check_call(f"cd {dir} {wipe_cmd} && git checkout {branch} && git pull --recurse-submodules {checkout_cmd}", shell=True)
        os.chdir(cwd)

    # Netlist Generation.
    @staticmethod
    def generate_netlist(reset_address):
        vdir = get_data_mod("cpu", "naxriscv").data_location
        ndir = os.path.join(vdir, "ext", "NaxRiscv")

        NaxRiscv.git_setup("NaxRiscv", ndir, "https://github.com/SpinalHDL/NaxRiscv.git", "main", "ba63ee6d", NaxRiscv.update_repo)

        gen_args = []
        gen_args.append(f"--netlist-name={NaxRiscv.netlist_name}")
        gen_args.append(f"--netlist-directory={vdir}")
        gen_args.append(f"--reset-vector={reset_address}")
        gen_args.append(f"--xlen={NaxRiscv.xlen}")
        gen_args.append(f"--cpu-count={NaxRiscv.cpu_count}")
        gen_args.append(f"--l2-bytes={NaxRiscv.l2_bytes}")
        gen_args.append(f"--l2-ways={NaxRiscv.l2_ways}")
        gen_args.append(f"--litedram-width={NaxRiscv.litedram_width}")
        for region in NaxRiscv.memory_regions:
            gen_args.append(f"--memory-region={region[0]},{region[1]},{region[2]},{region[3]}")
        for args in NaxRiscv.scala_args:
            gen_args.append(f"--scala-args={args}")
        if(NaxRiscv.jtag_tap) :
            gen_args.append(f"--with-jtag-tap")
        if(NaxRiscv.jtag_instruction) :
            gen_args.append(f"--with-jtag-instruction")
        if(NaxRiscv.jtag_tap or NaxRiscv.jtag_instruction):
            gen_args.append(f"--with-debug")
        if(NaxRiscv.with_dma) :
            gen_args.append(f"--with-dma")
        for file in NaxRiscv.scala_paths:
            gen_args.append(f"--scala-file={file}")
        if(NaxRiscv.with_fpu):
            gen_args.append(f"--scala-args=rvf=true,rvd=true")
        if(NaxRiscv.with_rvc):
            gen_args.append(f"--scala-args=rvc=true")

        cmd = f"""cd {ndir} && sbt "runMain naxriscv.platform.litex.NaxGen {" ".join(gen_args)}\""""
        print("NaxRiscv generation command :")
        print(cmd)
        subprocess.check_call(cmd, shell=True)


    def add_sources(self, platform):
        vdir = get_data_mod("cpu", "naxriscv").data_location
        print(f"NaxRiscv netlist : {self.netlist_name}")

        if NaxRiscv.no_netlist_cache or not os.path.exists(os.path.join(vdir, self.netlist_name + ".v")):
            self.generate_netlist(self.reset_address)

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
        self.human_name = f"{self.human_name} {self.xlen}-bit"

        # Set UART/Timer0 CSRs to the ones used by OpenSBI.
        soc.csr.add("uart",   n=2)
        soc.csr.add("timer0", n=3)

        # Add OpenSBI region.
        soc.bus.add_region("opensbi", SoCRegion(origin=self.mem_map["main_ram"] + 0x00f0_0000, size=0x8_0000, cached=True, linker=True))

        # Define ISA.
        soc.add_config("CPU_COUNT", NaxRiscv.cpu_count)
        soc.add_config("CPU_ISA", NaxRiscv.get_arch())
        soc.add_config("CPU_MMU", {32 : "sv32", 64 : "sv39"}[NaxRiscv.xlen])

        # Constants for cache so we can add them in the DTS.
        soc.add_config("CPU_DCACHE_SIZE", 16384)
        soc.add_config("CPU_DCACHE_WAYS", 4)
        soc.add_config("CPU_DCACHE_BLOCK_SIZE", 64) # hardwired?
        soc.add_config("CPU_ICACHE_SIZE", 16384)
        soc.add_config("CPU_ICACHE_WAYS", 4)
        soc.add_config("CPU_ICACHE_BLOCK_SIZE", 64) # hardwired?
        if NaxRiscv.l2_bytes > 0:
            soc.add_config("CPU_L2CACHE_SIZE", NaxRiscv.l2_bytes)
            soc.add_config("CPU_L2CACHE_WAYS", NaxRiscv.l2_ways)
            soc.add_config("CPU_L2CACHE_BLOCK_SIZE", 64) # hardwired?

        soc.bus.add_region("plic",  SoCRegion(origin=soc.mem_map.get("plic"),  size=0x40_0000, cached=False,  linker=True))
        soc.bus.add_region("clint", SoCRegion(origin=soc.mem_map.get("clint"), size= 0x1_0000, cached=False,  linker=True))

        if NaxRiscv.jtag_tap:
            self.jtag_tms = Signal()
            self.jtag_clk = Signal()
            self.jtag_tdi = Signal()
            self.jtag_tdo = Signal()

            self.cpu_params.update(
                i_jtag_tms = self.jtag_tms,
                i_jtag_tck = self.jtag_clk,
                i_jtag_tdi = self.jtag_tdi,
                o_jtag_tdo = self.jtag_tdo,
            )

        if NaxRiscv.jtag_instruction:
            self.jtag_clk     = Signal()
            self.jtag_enable  = Signal()
            self.jtag_capture = Signal()
            self.jtag_shift   = Signal()
            self.jtag_update  = Signal()
            self.jtag_reset   = Signal()
            self.jtag_tdo     = Signal()
            self.jtag_tdi     = Signal()

            self.cpu_params.update(
                i_jtag_instruction_clk     = self.jtag_clk,
                i_jtag_instruction_instruction_enable  = self.jtag_enable,
                i_jtag_instruction_instruction_capture = self.jtag_capture,
                i_jtag_instruction_instruction_shift   = self.jtag_shift,
                i_jtag_instruction_instruction_update  = self.jtag_update,
                i_jtag_instruction_instruction_reset   = self.jtag_reset,
                i_jtag_instruction_instruction_tdi     = self.jtag_tdi,
                o_jtag_instruction_instruction_tdo     = self.jtag_tdo,
            )

        if NaxRiscv.jtag_instruction or NaxRiscv.jtag_tap:
            # Create PoR Clk Domain for debug_reset.
            self.cd_debug_por = ClockDomain()
            self.comb += self.cd_debug_por.clk.eq(ClockSignal("sys"))

            # Create PoR debug_reset.
            debug_reset = Signal(reset=1)
            self.sync.debug_por += debug_reset.eq(0)

            # Debug resets.
            debug_ndmreset      = Signal()
            debug_ndmreset_last = Signal()
            debug_ndmreset_rise = Signal()
            self.cpu_params.update(
                i_debug_reset    = debug_reset,
                o_debug_ndmreset = debug_ndmreset,
            )

            # Reset SoC's CRG when debug_ndmreset rising edge.
            self.sync.debug_por += debug_ndmreset_last.eq(debug_ndmreset)
            self.comb += debug_ndmreset_rise.eq(debug_ndmreset & ~debug_ndmreset_last)
            if soc.get_build_name() == "sim":
                self.comb += If(debug_ndmreset_rise, soc.crg.cd_sys.rst.eq(1))
            else:
                self.comb += If(debug_ndmreset_rise, soc.crg.rst.eq(1))

        self.soc_bus = soc.bus # FIXME: Save SoC Bus instance to retrieve the final mem layout on finalization.

    def add_jtag(self, pads):
        self.comb += [
            self.jtag_tms.eq(pads.tms),
            self.jtag_clk.eq(pads.tck),
            self.jtag_tdi.eq(pads.tdi),
            pads.tdo.eq(self.jtag_tdo),
        ]

    def add_memory_buses(self, address_width, data_width):
        NaxRiscv.litedram_width = data_width
        nax_data_width = 64
        nax_burst_size = 64
        assert data_width >= nax_data_width   # FIXME: Only supporting up-conversion for now.
        assert data_width <= nax_burst_size*8 # FIXME: AXIUpConverter doing assumptions on minimal burst_size.

        mbus = axi.AXIInterface(
            data_width    = NaxRiscv.litedram_width,
            address_width = 32,
            id_width      = 8, #TODO
        )
        self.memory_buses.append(mbus)

        self.comb += mbus.aw.cache.eq(0xF)
        self.comb += mbus.aw.lock.eq(0)
        self.comb += mbus.aw.prot.eq(1)
        self.comb += mbus.aw.qos.eq(0)

        self.comb += mbus.ar.cache.eq(0xF)
        self.comb += mbus.ar.lock.eq(0)
        self.comb += mbus.ar.prot.eq(1)
        self.comb += mbus.ar.qos.eq(0)

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
            o_mBus_awallStrb = Open(),
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

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.find_scala_files()

        # Generate memory map from CPU perspective
        # naxriscv modes:
        # r,w,x,c  : readable, writeable, executable, caching allowed
        # io       : IO region (Implies P bus, preserve memory order, no dcache)
        # naxriscv bus:
        # p        : peripheral
        # m        : memory
        NaxRiscv.memory_regions = []
        for name, region in self.soc_bus.io_regions.items():
            NaxRiscv.memory_regions.append( (region.origin, region.size, "io", "p") ) # IO is only allowed on the p bus
        for name, region in self.soc_bus.regions.items():
            if region.linker: # Remove virtual regions.
                continue
            if len(self.memory_buses) and name == 'main_ram': # m bus
                bus = "m"
            else:
                bus = "p"
            mode = region.mode
            mode += "c" if region.cached else ""
            NaxRiscv.memory_regions.append( (region.origin, region.size, mode, bus) )

        self.generate_netlist_name(self.reset_address)

        # Do verilog instance.
        self.specials += Instance(self.netlist_name, **self.cpu_params)

        # Add verilog sources.
        self.add_sources(self.platform)
