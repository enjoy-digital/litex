#
# This file is part of LiteX.
#
# Copyright (c) 2020-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020-2022 Dolu1990 <charles.papon.90@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause
import hashlib
import os
import subprocess
from os import path

from migen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.interconnect import axi
from litex.soc.interconnect.csr import *
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

import os

class Open(Signal): pass

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = {
    "standard": "NaxRiscv",
}

# NaxRiscv -----------------------------------------------------------------------------------------

class NaxRiscv(CPU):
    family               = "riscv"
    name                 = "naxriscv"
    human_name           = "NaxRiscv"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x80000000: 0x80000000} # Origin, Length.

    # Default parameters.
    with_fpu             = False
    with_rvc             = False
    scala_files          = ["misc.scala", "fetch.scala", "frontend.scala", "branch_predictor_std.scala", "lsu.scala", "eu_2alu_1share.scala"]
    netlist_name         = None
    scala_paths          = []

    # ABI.
    @staticmethod
    def get_abi():
        abi = "ilp32"
        if NaxRiscv.with_fpu:
            abi +="d"
        return abi

    # Arch.
    @staticmethod
    def get_arch():
        arch = "rv32ima"
        if NaxRiscv.with_fpu:
            arch += "fd"
        if NaxRiscv.with_rvc:
            arch += "c"
        return arch

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "rom":      0x00000000,
            "sram":     0x10000000,
            "main_ram": 0x40000000,
            "csr":      0xf0000000,
            "clint":    0xf0010000,
            "plic":     0xf0c00000,
        }

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  f" -march={NaxRiscv.get_arch()} -mabi={NaxRiscv.get_abi()}"
        flags += f" -D__NaxRiscv__"
        flags += f" -DUART_POLLING"
        return flags


    # Command line configuration arguments.
    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group("cpu")
        cpu_group.add_argument("--scala-file", action='append', help="Specify the scala files used to configure NaxRiscv")

    @staticmethod
    def args_read(args):
        print(args)
        if args.scala_file:
            NaxRiscv.scala_files = args.scala_file


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
        for file in NaxRiscv.scala_paths:
            a_file = open(file, "rb")
            content = a_file.read()
            md5_hash.update(content)

        digest = md5_hash.hexdigest()
        NaxRiscv.netlist_name = "NaxRiscvLitex_" + digest


    @staticmethod
    def git_setup(name, dir, repo, hash):
        if not os.path.exists(dir):
            # Clone Repo.
            print(f"Cloning {name} Git repository...")
            subprocess.check_call("git clone {url} {options}".format(
                url     = repo,
                options = dir
            ), shell=True)
            # Use specific SHA1 (Optional).
        os.chdir(os.path.join(dir))
        os.system(f"cd {dir} && git checkout main && git pull && git checkout {hash}")

    # Netlist Generation.
    @staticmethod
    def generate_netlist(reset_address):
        vdir = get_data_mod("cpu", "naxriscv").data_location
        ndir = os.path.join(vdir, "ext", "NaxRiscv")
        sdir = os.path.join(vdir, "ext", "SpinalHDL")

        NaxRiscv.git_setup("NaxRiscv", ndir, "https://github.com/SpinalHDL/NaxRiscv.git",   "51c9c751")
        NaxRiscv.git_setup("SpinalHDL", sdir, "https://github.com/SpinalHDL/SpinalHDL.git", "2ff1f4d7")

        gen_args = []
        gen_args.append(f"--netlist-name={NaxRiscv.netlist_name}")
        gen_args.append(f"--netlist-directory={vdir}")
        gen_args.append(f"--reset-vector={reset_address}")
        for file in NaxRiscv.scala_paths:
            gen_args.append(f"--scala-file={file}")

        cmd = f"""cd {ndir} && sbt "runMain naxriscv.platform.LitexGen {" ".join(gen_args)}\""""
        print("NaxRiscv generation command :")
        print(cmd)
        if os.system(cmd) != 0:
            raise OSError('Failed to run sbt')


    def add_sources(self, platform):
        vdir = get_data_mod("cpu", "naxriscv").data_location
        print(f"NaxRiscv netlist : {self.netlist_name}")
        if not path.exists(os.path.join(vdir, self.netlist_name + ".v")):
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

    def add_soc_components(self, soc, soc_region_cls):
        soc.csr.add("uart",   n=2)
        soc.csr.add("timer0", n=3)

        # Define ISA.
        soc.add_constant("CPU_ISA", NaxRiscv.get_arch())

        # Add PLIC Bus (Wishbone Slave).
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
        soc.bus.add_slave("plic", self.plicbus, region=soc_region_cls(origin=soc.mem_map.get("plic"), size=0x400000, cached=False))

        # Add CLINT Bus (Wishbone Slave).
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
        soc.bus.add_slave("clint", clintbus, region=soc_region_cls(origin=soc.mem_map.get("clint"), size=0x10000, cached=False))

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
        self.generate_netlist_name(self.reset_address)

        # Do verilog instance.
        self.specials += Instance(self.netlist_name, **self.cpu_params)

        # Add verilog sources
        self.add_sources(self.platform)
