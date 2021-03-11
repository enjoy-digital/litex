#
# This file is part of LiteX.
#
# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018-2019 Antmicro <www.antmicro.com>
# This file is Copyright (c) 2018 Sergiusz Bazanski <q3k@q3k.org>
# This file is Copyright (c) 2016-2017 Tim 'mithro' Ansell <mithro@mithis.com>
# This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# This file is Copyright (c) 2020 Xiretza <xiretza@xiretza.xyz>
# This file is Copyright (c) 2020 Piotr Esden-Tempski <piotr@esden.net>
# SPDX-License-Identifier: BSD-2-Clause


import os
import subprocess
import struct
import shutil

from litex import get_data_mod
from litex.build.tools import write_to_file
from litex.soc.integration import export, soc_core
from litex.soc.cores import cpu

# Helpers ------------------------------------------------------------------------------------------

def _makefile_escape(s):
    return s.replace("\\", "\\\\")

def _create_dir(d):
    os.makedirs(os.path.realpath(d), exist_ok=True)

# Software Packages --------------------------------------------------------------------------------

soc_software_packages = [
    # Compiler-RT.
    "libcompiler_rt",

    # LiteX cores.
    "libbase",

    # LiteX Ecosystem cores.
    "libfatfs",
    "liblitespi",
    "liblitedram",
    "libliteeth",
    "liblitesdcard",
    "liblitesata",

    # BIOS.
    "bios"
]

# Builder ------------------------------------------------------------------------------------------

soc_directory         = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
compiler_rt_directory = get_data_mod("software", "compiler_rt").data_location

class Builder:
    def __init__(self, soc,
        # Directories.
        output_dir       = None,
        gateware_dir     = None,
        software_dir     = None,
        include_dir      = None,
        generated_dir    = None,

        # Compile Options.
        compile_software = True,
        compile_gateware = True,

        # Exports.
        csr_json         = None,
        csr_csv          = None,
        csr_svd          = None,
        memory_x         = None,

        # BIOS Options.
        bios_options     = [],

        # Documentation.
        generate_doc     = False):

        self.soc = soc

        # Directories.
        self.output_dir    = os.path.abspath(output_dir    or os.path.join("build", soc.platform.name))
        self.gateware_dir  = os.path.abspath(gateware_dir  or os.path.join(self.output_dir,   "gateware"))
        self.software_dir  = os.path.abspath(software_dir  or os.path.join(self.output_dir,   "software"))
        self.include_dir   = os.path.abspath(include_dir   or os.path.join(self.software_dir, "include"))
        self.generated_dir = os.path.abspath(generated_dir or os.path.join(self.include_dir,  "generated"))

        # Compile Options.
        self.compile_software = compile_software
        self.compile_gateware = compile_gateware

        # Exports.
        self.csr_csv  = csr_csv
        self.csr_json = csr_json
        self.csr_svd  = csr_svd
        self.memory_x = memory_x

        # BIOS Options.
        self.bios_options = bios_options

        # Documentation
        self.generate_doc = generate_doc

        # List software packages.
        self.software_packages = []
        for name in soc_software_packages:
            self.add_software_package(name)

    def add_software_package(self, name, src_dir=None):
        if src_dir is None:
            src_dir = os.path.join(soc_directory, "software", name)
        self.software_packages.append((name, src_dir))

    def _generate_includes(self):
        # Generate Include/Generated directories.
        _create_dir(self.include_dir)
        _create_dir(self.generated_dir)

        # Generate BIOS files when the SoC uses it.
        with_bios = self.soc.cpu_type not in [None, "zynq7000"]
        if with_bios:

            # Generate Variables to variables.mak.
            variables_contents = []
            def define(k, v):
                variables_contents.append("{}={}".format(k, _makefile_escape(v)))

            # Define the CPU variables.
            for k, v in export.get_cpu_mak(self.soc.cpu, self.compile_software):
                define(k, v)

            # Define the SoC/Compiler-RT/Software/Include directories.
            define("SOC_DIRECTORY",         soc_directory)
            define("COMPILER_RT_DIRECTORY", compiler_rt_directory)
            variables_contents.append("export BUILDINC_DIRECTORY")
            define("BUILDINC_DIRECTORY", self.include_dir)
            for name, src_dir in self.software_packages:
                define(name.upper() + "_DIRECTORY", src_dir)

            # Define the BIOS Options.
            for bios_option in self.bios_options:
                assert bios_option in ["TERM_NO_HIST", "TERM_MINI", "TERM_NO_COMPLETE"]
                define(bios_option, "1")

            # Write to variables.mak.
            write_to_file(os.path.join(self.generated_dir, "variables.mak"), "\n".join(variables_contents))

            # Generate Output Format to output_format.ld.
            output_format_contents = export.get_linker_output_format(self.soc.cpu)
            write_to_file(os.path.join(self.generated_dir, "output_format.ld"), output_format_contents)

            # Generate Memory Regions to regions.ld.
            regions_contents = export.get_linker_regions(self.soc.mem_regions)
            write_to_file(os.path.join(self.generated_dir, "regions.ld"), regions_contents)

        # Generate Memory Regions to mem.h.
        mem_contents = export.get_mem_header(self.soc.mem_regions)
        write_to_file(os.path.join(self.generated_dir, "mem.h"), mem_contents)

        # Generate Memory Regions to memory.x if specified.
        if self.memory_x is not None:
            memory_x_contents = export.get_memory_x(self.soc)
            write_to_file(os.path.realpath(self.memory_x), memory_x_contents)

        # Generate SoC Config/Constants to soc.h.
        soc_contents = export.get_soc_header(self.soc.constants)
        write_to_file(os.path.join(self.generated_dir, "soc.h"), soc_contents)

        # Generate CSR registers definitions/access functions to csr.h.
        csr_contents = export.get_csr_header(
            regions   = self.soc.csr_regions,
            constants = self.soc.constants,
            csr_base  = self.soc.mem_regions['csr'].origin)
        write_to_file(os.path.join(self.generated_dir, "csr.h"), csr_contents)

        # Generate Git SHA1 of tools to git.h
        git_contents = export.get_git_header()
        write_to_file(os.path.join(self.generated_dir, "git.h"), git_contents)

        # Generate LiteDRAM C header to sdram_phy.h when the SoC use it.
        if hasattr(self.soc, "sdram"):
            from litedram.init import get_sdram_phy_c_header
            sdram_contents = get_sdram_phy_c_header(
                self.soc.sdram.controller.settings.phy,
                self.soc.sdram.controller.settings.timing)
            write_to_file(os.path.join(self.generated_dir, "sdram_phy.h"), sdram_contents)

    def _generate_csr_map(self):
        # JSON Export.
        if self.csr_json is not None:
            csr_json_contents = export.get_csr_json(
                csr_regions = self.soc.csr_regions,
                constants   = self.soc.constants,
                mem_regions = self.soc.mem_regions)
            write_to_file(os.path.realpath(self.csr_json), csr_json_contents)

        # CSV Export.
        if self.csr_csv is not None:
            csr_csv_contents = export.get_csr_csv(
                csr_regions = self.soc.csr_regions,
                constants   = self.soc.constants,
                mem_regions = self.soc.mem_regions)
            write_to_file(os.path.realpath(self.csr_csv), csr_csv_contents)

        # SVD Export.
        if self.csr_svd is not None:
            csr_svd_contents = export.get_csr_svd(self.soc)
            write_to_file(os.path.realpath(self.csr_svd), csr_svd_contents)

    def _prepare_rom_software(self):
        # Create directories for all software packages.
        for name, src_dir in self.software_packages:
            _create_dir(os.path.join(self.software_dir, name))

    def _generate_rom_software(self, compile_bios=True):
        # Compile all software packages.
         for name, src_dir in self.software_packages:
            # Skip BIOS compilation when disabled.
            if name == "bios" and not compile_bios:
                continue
            # Compile software package.
            dst_dir  = os.path.join(self.software_dir, name)
            makefile = os.path.join(src_dir, "Makefile")
            if self.compile_software:
                subprocess.check_call(["make", "-C", dst_dir, "-f", makefile])

    def _initialize_rom_software(self):
        # Get BIOS data from compiled BIOS binary.
        bios_file = os.path.join(self.software_dir, "bios", "bios.bin")
        bios_data = soc_core.get_mem_data(bios_file, self.soc.cpu.endianness)

        # Initialize SoC with with BIOS data.
        self.soc.initialize_rom(bios_data)

    def build(self, **kwargs):
        # Pass Output Directory to Platform.
        self.soc.platform.output_dir = self.output_dir

        # Create Gateware/Software directories.
        _create_dir(self.gateware_dir)
        _create_dir(self.software_dir)

        # Finalize the SoC.
        self.soc.finalize()

        # Generate Software Includes/Files.
        self._generate_includes()

        # Export SoC Mapping.
        self._generate_csr_map()

        # Compile the BIOS when the SoC uses it.
        if self.soc.cpu_type is not None:
            if self.soc.cpu.use_rom:
                # Prepare/Generate ROM software.
                self._prepare_rom_software()
                self._generate_rom_software(not self.soc.integrated_rom_initialized)

                # Initialize ROM.
                if self.soc.integrated_rom_size and self.compile_software:
                    if not self.soc.integrated_rom_initialized:
                        self._initialize_rom_software()

        # Translate compile_gateware to run.
        if "run" not in kwargs:
            kwargs["run"] = self.compile_gateware

        # Build SoC and pass Verilog Name Space to do_exit.
        vns = self.soc.build(build_dir=self.gateware_dir, **kwargs)
        self.soc.do_exit(vns=vns)

        # Generate SoC Documentation.
        if self.generate_doc:
            from litex.soc.doc import generate_docs
            doc_dir = os.path.join(self.output_dir, "doc")
            generate_docs(self.soc, doc_dir)
            os.system(f"sphinx-build -M html {doc_dir} {doc_dir}/_build")

        return vns

# Builder Arguments --------------------------------------------------------------------------------

def builder_args(parser):
    parser.add_argument("--output-dir",          default=None,        help="Base Output directory (customizable with --{gateware,software,include,generated}-dir).")
    parser.add_argument("--gateware-dir",        default=None,        help="Output directory for Gateware files.")
    parser.add_argument("--software-dir",        default=None,        help="Output directory for Software files.")
    parser.add_argument("--include-dir",         default=None,        help="Output directory for Header files.")
    parser.add_argument("--generated-dir",       default=None,        help="Output directory for Generated files.")
    parser.add_argument("--no-compile-software", action="store_true", help="Disable Software compilation.")
    parser.add_argument("--no-compile-gateware", action="store_true", help="Disable Gateware compilation.")
    parser.add_argument("--csr-csv",             default=None,        help="Write SoC mapping to the specified CSV file.")
    parser.add_argument("--csr-json",            default=None,        help="Write SoC mapping to the specified JSON file.")
    parser.add_argument("--csr-svd",             default=None,        help="Write SoC mapping to the specified SVD file.")
    parser.add_argument("--memory-x",            default=None,        help="Write SoC Memory Regions to the specified Memory-X file.")
    parser.add_argument("--doc",                 action="store_true", help="Generate SoC Documentation.")


def builder_argdict(args):
    return {
        "output_dir":       args.output_dir,
        "gateware_dir":     args.gateware_dir,
        "software_dir":     args.software_dir,
        "include_dir":      args.include_dir,
        "generated_dir":    args.generated_dir,
        "compile_software": not args.no_compile_software,
        "compile_gateware": not args.no_compile_gateware,
        "csr_csv":          args.csr_csv,
        "csr_json":         args.csr_json,
        "csr_svd":          args.csr_svd,
        "memory_x":         args.memory_x,
        "generate_doc":     args.doc,
    }
