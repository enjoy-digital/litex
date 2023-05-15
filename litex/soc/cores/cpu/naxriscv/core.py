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
    jtag_tap         = False
    jtag_instruction = False

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
        arch = f"rv{NaxRiscv.xlen}ima"
        if NaxRiscv.with_fpu:
            arch += "fd"
        if NaxRiscv.with_rvc:
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
        flags =  f" -march={NaxRiscv.get_arch()} -mabi={NaxRiscv.get_abi()}"
        flags += f" -D__NaxRiscv__"
        flags += f" -DUART_POLLING"
        return flags

    # Reserved Interrupts.
    @property
    def reserved_interrupts(self):
        return {"noirq": 0}

    # Command line configuration arguments.
    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group(title="CPU options")
        cpu_group.add_argument("--scala-file",    action="append",     help="Specify the scala files used to configure NaxRiscv.")
        cpu_group.add_argument("--scala-args",    action="append",     help="Add arguements for the scala run time. Ex : --scala-args 'rvc=true,mmu=false'")
        cpu_group.add_argument("--xlen",          default=32,          help="Specify the RISC-V data width.")
        cpu_group.add_argument("--with-jtag-tap", action="store_true", help="Add a embedded JTAG tap for debugging")
        cpu_group.add_argument("--with-jtag-instruction", action="store_true", help="Add a JTAG instruction port which implement tunneling for debugging (TAP not included)")
        cpu_group.add_argument("--update-repo",   default="recommended", choices=["latest","wipe+latest","recommended","wipe+recommended","no"], help="Specify how the NaxRiscv & SpinalHDL repo should be updated (latest: update to HEAD, recommended: Update to known compatible version, no: Don't update, wipe+*: Do clean&reset before checkout)")
        cpu_group.add_argument("--no-netlist-cache", action="store_true", help="Always (re-)build the netlist")
        cpu_group.add_argument("--with-fpu",      action="store_true", help="Enable the F32/F64 FPU")

    @staticmethod
    def args_read(args):
        print(args)
        NaxRiscv.jtag_tap         = args.with_jtag_tap
        NaxRiscv.jtag_instruction = args.with_jtag_instruction
        NaxRiscv.update_repo      = args.update_repo
        NaxRiscv.no_netlist_cache = args.no_netlist_cache
        NaxRiscv.with_fpu         = args.with_fpu
        if args.scala_file:
            NaxRiscv.scala_files = args.scala_file
        if args.scala_args:
            NaxRiscv.scala_args  = args.scala_args
            print(args.scala_args)
        if args.xlen:
            xlen = int(args.xlen)
            NaxRiscv.xlen                 = xlen
            NaxRiscv.data_width           = xlen
            NaxRiscv.gcc_triple           = CPU_GCC_TRIPLE_RISCV64
            NaxRiscv.linker_output_format = f"elf{xlen}-littleriscv"


    def __init__(self, platform, variant):
        self.platform         = platform
        self.variant          = "standard"
        self.human_name       = self.human_name
        self.reset            = Signal()
        self.interrupt        = Signal(32)
        self.ibus             = ibus = axi.AXILiteInterface(address_width=32, data_width=32)
        self.dbus             = dbus = axi.AXILiteInterface(address_width=32, data_width=32)

        self.periph_buses     = [ibus, dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses     = []           # Memory buses (Connected directly to LiteDRAM).

        # # #

        # CPU Instance.
        self.cpu_params = dict(
            # Clk/Rst.
            i_clk   = ClockSignal("sys"),
            i_reset = ResetSignal("sys") | self.reset,

            # Interrupt.
            i_peripheral_interrupt = self.interrupt, # FIXME: Check what is expected. => interrupt(0) is dummy and should not be used (PLIC stuff), need to reserve interrupt(0)

            # Peripheral Instruction Bus (AXI Lite Slave).
            o_peripheral_ibus_arvalid = ibus.ar.valid,
            i_peripheral_ibus_arready = ibus.ar.ready,
            o_peripheral_ibus_araddr  = ibus.ar.addr,
            o_peripheral_ibus_arprot  = Open(),
            i_peripheral_ibus_rvalid  = ibus.r.valid,
            o_peripheral_ibus_rready  = ibus.r.ready,
            i_peripheral_ibus_rdata   = ibus.r.data,
            i_peripheral_ibus_rresp   = ibus.r.resp,

            # Peripheral Memory Bus (AXI Lite Slave).
            o_peripheral_dbus_awvalid = dbus.aw.valid,
            i_peripheral_dbus_awready = dbus.aw.ready,
            o_peripheral_dbus_awaddr  = dbus.aw.addr,
            o_peripheral_dbus_awprot  = Open(),
            o_peripheral_dbus_wvalid  = dbus.w.valid,
            i_peripheral_dbus_wready  = dbus.w.ready,
            o_peripheral_dbus_wdata   = dbus.w.data,
            o_peripheral_dbus_wstrb   = dbus.w.strb,
            i_peripheral_dbus_bvalid  = dbus.b.valid,
            o_peripheral_dbus_bready  = dbus.b.ready,
            i_peripheral_dbus_bresp   = dbus.b.resp,
            o_peripheral_dbus_arvalid = dbus.ar.valid,
            i_peripheral_dbus_arready = dbus.ar.ready,
            o_peripheral_dbus_araddr  = dbus.ar.addr,
            o_peripheral_dbus_arprot  = Open(),
            i_peripheral_dbus_rvalid  = dbus.r.valid,
            o_peripheral_dbus_rready  = dbus.r.ready,
            i_peripheral_dbus_rdata   = dbus.r.data,
            i_peripheral_dbus_rresp   = dbus.r.resp,
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
        md5_hash.update(str(NaxRiscv.xlen).encode('utf-8'))
        md5_hash.update(str(NaxRiscv.jtag_tap).encode('utf-8'))
        md5_hash.update(str(NaxRiscv.jtag_instruction).encode('utf-8'))
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
    def git_setup(name, dir, repo, branch, hash):
        if not os.path.exists(dir):
            # Clone Repo.
            print(f"Cloning {name} Git repository...")
            subprocess.check_call("git clone {url} {options}".format(
                url     = repo,
                options = dir
            ), shell=True)
            # Use specific SHA1 (Optional).
        print(f"Updating {name} Git repository...")
        os.chdir(os.path.join(dir))
        wipe_cmd = "&& git clean --force -d -x && git reset --hard" if "wipe" in NaxRiscv.update_repo else ""
        checkout_cmd = f"&& git checkout {hash}" if hash is not None else ""
        subprocess.check_call(f"cd {dir} {wipe_cmd} && git checkout {branch} && git pull {checkout_cmd}", shell=True)

    # Netlist Generation.
    @staticmethod
    def generate_netlist(reset_address):
        vdir = get_data_mod("cpu", "naxriscv").data_location
        ndir = os.path.join(vdir, "ext", "NaxRiscv")
        sdir = os.path.join(vdir, "ext", "SpinalHDL")

        if NaxRiscv.update_repo != "no":
            NaxRiscv.git_setup("NaxRiscv", ndir, "https://github.com/SpinalHDL/NaxRiscv.git"  , "main", "57e3bf59" if NaxRiscv.update_repo=="recommended" else None)
            NaxRiscv.git_setup("SpinalHDL", sdir, "https://github.com/SpinalHDL/SpinalHDL.git", "dev" , "8511f126" if NaxRiscv.update_repo=="recommended" else None)

        gen_args = []
        gen_args.append(f"--netlist-name={NaxRiscv.netlist_name}")
        gen_args.append(f"--netlist-directory={vdir}")
        gen_args.append(f"--reset-vector={reset_address}")
        gen_args.append(f"--xlen={NaxRiscv.xlen}")
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
        for file in NaxRiscv.scala_paths:
            gen_args.append(f"--scala-file={file}")
        if(NaxRiscv.with_fpu):
            gen_args.append(f"--scala-args=rvf=true,rvd=true")

        cmd = f"""cd {ndir} && sbt "runMain naxriscv.platform.LitexGen {" ".join(gen_args)}\""""
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
        # On Altera/Intel platforms, use specific implementation.
        from litex.build.altera import AlteraPlatform
        if isinstance(platform, AlteraPlatform):
            ram_filename = "Ram_1w_1rs_Intel.v"
        # On Efinix platforms, use specific implementation.
        from litex.build.efinix import EfinixPlatform
        if isinstance(platform, EfinixPlatform):
            ram_filename = "Ram_1w_1rs_Efinix.v"
        platform.add_source(os.path.join(vdir, ram_filename), "verilog")

        # Add Cluster.
        platform.add_source(os.path.join(vdir,  self.netlist_name + ".v"), "verilog")

    def add_soc_components(self, soc):
        # Set UART/Timer0 CSRs to the ones used by OpenSBI.
        soc.csr.add("uart",   n=2)
        soc.csr.add("timer0", n=3)

        # Add OpenSBI region.
        soc.bus.add_region("opensbi", SoCRegion(origin=self.mem_map["main_ram"] + 0x00f0_0000, size=0x8_0000, cached=True, linker=True))

        # Define ISA.
        soc.add_config("CPU_ISA", NaxRiscv.get_arch())
        soc.add_config("CPU_MMU", {32 : "sv32", 64 : "sv39"}[NaxRiscv.xlen])

        # Add PLIC Bus (AXILite Slave).
        self.plicbus = plicbus  = axi.AXILiteInterface(address_width=32, data_width=32)
        self.cpu_params.update(
            i_peripheral_plic_awvalid = plicbus.aw.valid,
            o_peripheral_plic_awready = plicbus.aw.ready,
            i_peripheral_plic_awaddr  = plicbus.aw.addr,
            i_peripheral_plic_awprot  = Constant(2),
            i_peripheral_plic_wvalid  = plicbus.w.valid,
            o_peripheral_plic_wready  = plicbus.w.ready,
            i_peripheral_plic_wdata   = plicbus.w.data,
            i_peripheral_plic_wstrb   = plicbus.w.strb,
            o_peripheral_plic_bvalid  = plicbus.b.valid,
            i_peripheral_plic_bready  = plicbus.b.ready,
            o_peripheral_plic_bresp   = plicbus.b.resp,
            i_peripheral_plic_arvalid = plicbus.ar.valid,
            o_peripheral_plic_arready = plicbus.ar.ready,
            i_peripheral_plic_araddr  = plicbus.ar.addr,
            i_peripheral_plic_arprot  = Constant(2),
            o_peripheral_plic_rvalid  = plicbus.r.valid,
            i_peripheral_plic_rready  = plicbus.r.ready,
            o_peripheral_plic_rdata   = plicbus.r.data,
            o_peripheral_plic_rresp   = plicbus.r.resp,
        )
        soc.bus.add_slave("plic", self.plicbus, region=SoCRegion(origin=soc.mem_map.get("plic"), size=0x40_0000, cached=False))

        if NaxRiscv.jtag_tap:
            self.jtag_tms = Signal()
            self.jtag_tck = Signal()
            self.jtag_tdi = Signal()
            self.jtag_tdo = Signal()

            self.cpu_params.update(
                i_jtag_tms = self.jtag_tms,
                i_jtag_tck = self.jtag_tck,
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
                i_jtag_instruction_enable  = self.jtag_enable,
                i_jtag_instruction_capture = self.jtag_capture,
                i_jtag_instruction_shift   = self.jtag_shift,
                i_jtag_instruction_update  = self.jtag_update,
                i_jtag_instruction_reset   = self.jtag_reset,
                i_jtag_instruction_tdi     = self.jtag_tdi,
                o_jtag_instruction_tdo     = self.jtag_tdo,
            )

        if NaxRiscv.jtag_instruction or NaxRiscv.jtag_tap:
            # Create PoR Clk Domain for debug_reset.
            self.clock_domains.cd_debug_por = ClockDomain()
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
            self.comb += If(debug_ndmreset_rise, soc.crg.rst.eq(1))

        # Add CLINT Bus (AXILite Slave).
        self.clintbus = clintbus = axi.AXILiteInterface(address_width=32, data_width=32)
        self.cpu_params.update(
            i_peripheral_clint_awvalid = clintbus.aw.valid,
            o_peripheral_clint_awready = clintbus.aw.ready,
            i_peripheral_clint_awaddr  = clintbus.aw.addr,
            i_peripheral_clint_awprot  = Constant(2),
            i_peripheral_clint_wvalid  = clintbus.w.valid,
            o_peripheral_clint_wready  = clintbus.w.ready,
            i_peripheral_clint_wdata   = clintbus.w.data,
            i_peripheral_clint_wstrb   = clintbus.w.strb,
            o_peripheral_clint_bvalid  = clintbus.b.valid,
            i_peripheral_clint_bready  = clintbus.b.ready,
            o_peripheral_clint_bresp   = clintbus.b.resp,
            i_peripheral_clint_arvalid = clintbus.ar.valid,
            o_peripheral_clint_arready = clintbus.ar.ready,
            i_peripheral_clint_araddr  = clintbus.ar.addr,
            i_peripheral_clint_arprot  = Constant(2),
            o_peripheral_clint_rvalid  = clintbus.r.valid,
            i_peripheral_clint_rready  = clintbus.r.ready,
            o_peripheral_clint_rdata   = clintbus.r.data,
            o_peripheral_clint_rresp   = clintbus.r.resp,
        )
        soc.bus.add_slave("clint", clintbus, region=SoCRegion(origin=soc.mem_map.get("clint"), size=0x1_0000, cached=False))
        self.soc = soc # FIXME: Save SoC instance to retrieve the final mem layout on finalization.

    def add_memory_buses(self, address_width, data_width):
        nax_data_width = 64
        nax_burst_size = 64
        assert data_width >= nax_data_width   # FIXME: Only supporting up-conversion for now.
        assert data_width <= nax_burst_size*8 # FIXME: AXIUpConverter doing assumptions on minimal burst_size.

        ibus = axi.AXIInterface(
            data_width    = nax_data_width,
            address_width = 32,
            id_width      = 1,
        )
        dbus = axi.AXIInterface(
            data_width    = nax_data_width,
            address_width = 32,
            id_width      = 4,
        )
        self.memory_buses.append(ibus)
        self.memory_buses.append(dbus)

        self.cpu_params.update(
            # Instruction Memory Bus (Master).
            o_ram_ibus_arvalid = ibus.ar.valid,
            i_ram_ibus_arready = ibus.ar.ready,
            o_ram_ibus_araddr  = ibus.ar.addr,
            o_ram_ibus_arlen   = ibus.ar.len,
            o_ram_ibus_arsize  = ibus.ar.size,
            o_ram_ibus_arburst = ibus.ar.burst,
            i_ram_ibus_rvalid  = ibus.r.valid,
            o_ram_ibus_rready  = ibus.r.ready,
            i_ram_ibus_rdata   = ibus.r.data,
            i_ram_ibus_rresp   = ibus.r.resp,
            i_ram_ibus_rlast   = ibus.r.last,

            # Data Memory Bus (Master).
            o_ram_dbus_awvalid = dbus.aw.valid,
            i_ram_dbus_awready = dbus.aw.ready,
            o_ram_dbus_awaddr  = dbus.aw.addr,
            o_ram_dbus_awid    = dbus.aw.id,
            o_ram_dbus_awlen   = dbus.aw.len,
            o_ram_dbus_awsize  = dbus.aw.size,
            o_ram_dbus_awburst = dbus.aw.burst,
            o_ram_dbus_wvalid  = dbus.w.valid,
            i_ram_dbus_wready  = dbus.w.ready,
            o_ram_dbus_wdata   = dbus.w.data,
            o_ram_dbus_wstrb   = dbus.w.strb,
            o_ram_dbus_wlast   = dbus.w.last,
            i_ram_dbus_bvalid  = dbus.b.valid,
            o_ram_dbus_bready  = dbus.b.ready,
            i_ram_dbus_bid     = dbus.b.id,
            i_ram_dbus_bresp   = dbus.b.resp,
            o_ram_dbus_arvalid = dbus.ar.valid,
            i_ram_dbus_arready = dbus.ar.ready,
            o_ram_dbus_araddr  = dbus.ar.addr,
            o_ram_dbus_arid    = dbus.ar.id,
            o_ram_dbus_arlen   = dbus.ar.len,
            o_ram_dbus_arsize  = dbus.ar.size,
            o_ram_dbus_arburst = dbus.ar.burst,
            i_ram_dbus_rvalid  = dbus.r.valid,
            o_ram_dbus_rready  = dbus.r.ready,
            i_ram_dbus_rdata   = dbus.r.data,
            i_ram_dbus_rid     = dbus.r.id,
            i_ram_dbus_rresp   = dbus.r.resp,
            i_ram_dbus_rlast   = dbus.r.last,
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
        for name, region in self.soc.bus.io_regions.items():
            NaxRiscv.memory_regions.append( (region.origin, region.size, "io", "p") ) # IO is only allowed on the p bus
        for name, region in self.soc.bus.regions.items():
            if region.linker: # remove virtual regions
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
