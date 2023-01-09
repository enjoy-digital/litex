#
# This file is part of LiteX.
#
# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018-2019 Antmicro <www.antmicro.com>
# This file is Copyright (c) 2018 Sergiusz Bazanski <q3k@q3k.org>
# This file is Copyright (c) 2016-2017 Tim 'mithro' Ansell <mithro@mithis.com>
# This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# This file is Copyright (c) 2020 Xiretza <xiretza@xiretza.xyz>
# This file is Copyright (c) 2020 Piotr Esden-Tempski <piotr@esden.net>
# SPDX-License-Identifier: BSD-2-Clause


import os
import argparse
import subprocess
import struct
import shutil

from packaging.version import Version

from litex import get_data_mod
from litex.gen import colorer

from litex.build.tools import write_to_file

from litex.soc.cores import cpu
from litex.soc.integration import export, soc_core

# Helpers ------------------------------------------------------------------------------------------

def _makefile_escape(s):
    return s.replace("\\", "\\\\")

def _create_dir(d, remove_if_exists=False):
    dir_path = os.path.realpath(d)
    if remove_if_exists and os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path, exist_ok=True)

# Software Packages --------------------------------------------------------------------------------

soc_software_packages = [
    # picolibc
    "libc",

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
]

# Builder ------------------------------------------------------------------------------------------

soc_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class Builder:
    def __init__(self, soc,
        # Directories.
        output_dir       = None,
        gateware_dir     = None,
        software_dir     = None,
        include_dir      = None,
        generated_dir    = None,

        # Compilation.
        compile_software = True,
        compile_gateware = True,
        build_backend    = "litex",

        # Exports.
        csr_json         = None,
        csr_csv          = None,
        csr_svd          = None,
        memory_x         = None,

        # BIOS.
        bios_lto         = False,
        bios_console     = "full",

        # Documentation.
        generate_doc     = False):

        self.soc = soc

        # Directories.
        self.output_dir    = os.path.abspath(output_dir    or os.path.join("build", soc.platform.name))
        self.gateware_dir  = os.path.abspath(gateware_dir  or os.path.join(self.output_dir,   "gateware"))
        self.software_dir  = os.path.abspath(software_dir  or os.path.join(self.output_dir,   "software"))
        self.include_dir   = os.path.abspath(include_dir   or os.path.join(self.software_dir, "include"))
        self.generated_dir = os.path.abspath(generated_dir or os.path.join(self.include_dir,  "generated"))

        # Compilation.
        self.compile_software = compile_software
        self.compile_gateware = compile_gateware
        self.build_backend    = build_backend

        # Exports.
        self.csr_csv  = csr_csv
        self.csr_json = csr_json
        self.csr_svd  = csr_svd
        self.memory_x = memory_x

        # BIOS.
        self.bios_lto     = bios_lto
        self.bios_console = bios_console

        # Documentation.
        self.generate_doc = generate_doc

        # Software packages and libraries.
        self.software_packages  = []
        self.software_libraries = []
        for name in soc_software_packages:
            self.add_software_package(name)
            self.add_software_library(name)

    def add_software_package(self, name, src_dir=None):
        if src_dir is None:
            src_dir = os.path.join(soc_directory, "software", name)
        self.software_packages.append((name, src_dir))

    def add_software_library(self, name):
        self.software_libraries.append(name)

    def _get_variables_contents(self):
        # Helper.
        variables_contents = []
        def define(k, v):
            k = k.replace("-", "_")
            try:
                variables_contents.append("{}={}".format(k, _makefile_escape(v)))
            except AttributeError as e:
                print(colorer(f"problem with {k}:", 'red'))
                raise e

        # Define packages and libraries.
        define("PACKAGES",     " ".join(name for name, src_dir in self.software_packages))
        define("PACKAGE_DIRS", " ".join(src_dir for name, src_dir in self.software_packages))
        define("LIBS",         " ".join(self.software_libraries))

        # Define CPU variables.
        for k, v in export.get_cpu_mak(self.soc.cpu, self.compile_software):
            define(k, v)

        # Define SoC/Picolibc/Compiler-RT/Software/Include directories.
        picolibc_directory    = get_data_mod("software", "picolibc").data_location
        compiler_rt_directory = get_data_mod("software", "compiler_rt").data_location

        define("SOC_DIRECTORY",         soc_directory)
        define("PICOLIBC_DIRECTORY",    picolibc_directory)
        define("COMPILER_RT_DIRECTORY", compiler_rt_directory)
        variables_contents.append("export BUILDINC_DIRECTORY")
        define("BUILDINC_DIRECTORY", self.include_dir)
        for name, src_dir in self.software_packages:
            define(name.upper() + "_DIRECTORY", src_dir)

        # Define BIOS variables.
        define("LTO", f"{self.bios_lto:d}")
        assert self.bios_console in ["full", "no-history", "no-autocomplete", "lite", "disable"]
        define(f"BIOS_CONSOLE_{self.bios_console.upper()}", "1")

        return "\n".join(variables_contents)

    def _generate_includes(self, with_bios=True):
        # Generate Include/Generated directories.
        _create_dir(self.include_dir)
        _create_dir(self.generated_dir)

        # Generate BIOS files when the SoC uses it.
        if with_bios:
            # Generate Variables to variables.mak.
            variables_contents = self._get_variables_contents()
            write_to_file(os.path.join(self.generated_dir, "variables.mak"), variables_contents)

            # Generate Output Format to output_format.ld.
            output_format_contents = export.get_linker_output_format(self.soc.cpu)
            write_to_file(os.path.join(self.generated_dir, "output_format.ld"), output_format_contents)

            # Generate Memory Regions to regions.ld.
            regions_contents = export.get_linker_regions(self.soc.mem_regions)
            write_to_file(os.path.join(self.generated_dir, "regions.ld"), regions_contents)

        # Collect / Generate I2C config and init table.
        from litex.soc.cores.bitbang import collect_i2c_info
        i2c_devs, i2c_init = collect_i2c_info(self.soc)
        if i2c_devs:
            i2c_info = export.get_i2c_header((i2c_devs, i2c_init))
            write_to_file(os.path.join(self.generated_dir, "i2c.h"), i2c_info)

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
            csr_base  = self.soc.mem_regions["csr"].origin)
        write_to_file(os.path.join(self.generated_dir, "csr.h"), csr_contents)

        # Generate Git SHA1 of tools to git.h
        git_contents = export.get_git_header()
        write_to_file(os.path.join(self.generated_dir, "git.h"), git_contents)

        # Generate LiteDRAM C header to sdram_phy.h when the SoC use it
        if hasattr(self.soc, "sdram"):
            from litedram.init import get_sdram_phy_c_header
            sdram_contents = get_sdram_phy_c_header(
                self.soc.sdram.controller.settings.phy,
                self.soc.sdram.controller.settings.timing,
                self.soc.sdram.controller.settings.geom)
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

    def _check_meson(self):
        # Check Meson install/version.
        meson_present   = (shutil.which("meson") is not None)
        meson_req = '0.59'
        if meson_present:
            meson_version = subprocess.check_output(["meson", "-v"]).decode("utf-8")
            if not Version(meson_version) >= Version(meson_req):
                msg = f"Meson version to old. Found: {meson_version}. Required: {meson_req}.\n"
                msg += "Try updating with:\n"
                msg += "- pip3 install -U meson.\n"
                raise OSError(msg)
        else:
            msg = "Unable to find valid Meson build system, please install it with:\n"
            msg += "- pip3 install meson.\n"
            raise OSError(msg)

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
        bios_data = soc_core.get_mem_data(bios_file,
            data_width = self.soc.bus.data_width,
            endianness = self.soc.cpu.endianness,
        )

        # Initialize SoC with with BIOS data.
        self.soc.initialize_rom(bios_data)

    def build(self, **kwargs):
        # Pass Output Directory to Platform.
        self.soc.platform.output_dir = self.output_dir

        # Check if BIOS is used and add software package if so.
        with_bios = self.soc.cpu_type is not None
        if with_bios:
            self.add_software_package("bios")

        # Create Gateware directory.
        _create_dir(self.gateware_dir)

        # Copy Sources to Gateware directory (Optional).
        for i, (f, language, library, *copy) in enumerate(self.soc.platform.sources):
            if len(copy) and copy[0]:
                shutil.copy(f, self.gateware_dir)
                f = os.path.basename(f)
            self.soc.platform.sources[i] = (f, language, library)

        # Create Software directory.
        # First check if software needs a full re-build and remove software dir if so.
        if with_bios:
            software_full_rebuild  = False
            software_variables_mak = os.path.join(self.generated_dir, "variables.mak")
            if self.compile_software and os.path.exists(software_variables_mak):
                old_variables_contents = open(software_variables_mak).read()
                new_variables_contents = self._get_variables_contents()
                software_full_rebuild  = (old_variables_contents != new_variables_contents)
            _create_dir(self.software_dir, remove_if_exists=software_full_rebuild)

        # Finalize the SoC.
        self.soc.finalize()

        # Generate Software Includes/Files.
        self._generate_includes(with_bios=with_bios)

        # Export SoC Mapping.
        self._generate_csr_map()

        # Compile the BIOS when the SoC uses it.
        if self.soc.cpu_type is not None:
            if self.soc.cpu.use_rom:
                # Prepare/Generate ROM software.
                use_bios = (
                    # BIOS compilation enabled.
                    self.compile_software and
                    # ROM contents has not already been initialized.
                    (not self.soc.integrated_rom_initialized)
                )
                if use_bios:
                    self.soc.check_bios_requirements()
                    self._check_meson()
                self._prepare_rom_software()
                self._generate_rom_software(compile_bios=use_bios)

                # Initialize ROM.
                if use_bios and self.soc.integrated_rom_size:
                    self._initialize_rom_software()

        # Translate compile_gateware to run.
        if "run" not in kwargs:
            kwargs["run"] = self.compile_gateware

        kwargs["build_backend"] = self.build_backend

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

    def get_bios_filename(self):
         return os.path.join(self.software_dir, "bios", "bios.bin")

    def get_bitstream_filename(self, mode="sram", ext=None):
        assert mode in ["sram", "flash"]
        if ext is None:
            ext = {
                "sram"  : self.soc.platform.bitstream_ext,
                "flash" : ".bin" # FIXME.
            }[mode]
        return os.path.join(self.gateware_dir, self.soc.get_build_name() + ext)

# Builder Arguments --------------------------------------------------------------------------------

def builder_args(parser):
    parser.formatter_class = lambda prog: argparse.ArgumentDefaultsHelpFormatter(prog, max_help_position=10, width=120)
    builder_group = parser.add_argument_group(title="Builder options")
    builder_group.add_argument("--output-dir",          default=None,        help="Base Output directory.")
    builder_group.add_argument("--gateware-dir",        default=None,        help="Output directory for Gateware files.")
    builder_group.add_argument("--software-dir",        default=None,        help="Output directory for Software files.")
    builder_group.add_argument("--include-dir",         default=None,        help="Output directory for Header files.")
    builder_group.add_argument("--generated-dir",       default=None,        help="Output directory for Generated files.")
    builder_group.add_argument("--build-backend",       default="litex",     help="Select build backend: litex or edalize.")
    builder_group.add_argument("--no-compile",          action="store_true", help="Disable Software and Gateware compilation.")
    builder_group.add_argument("--no-compile-software", action="store_true", help="Disable Software compilation only.")
    builder_group.add_argument("--no-compile-gateware", action="store_true", help="Disable Gateware compilation only.")
    builder_group.add_argument("--csr-csv",             default=None,        help="Write SoC mapping to the specified CSV file.")
    builder_group.add_argument("--csr-json",            default=None,        help="Write SoC mapping to the specified JSON file.")
    builder_group.add_argument("--csr-svd",             default=None,        help="Write SoC mapping to the specified SVD file.")
    builder_group.add_argument("--memory-x",            default=None,        help="Write SoC Memory Regions to the specified Memory-X file.")
    builder_group.add_argument("--doc",                 action="store_true", help="Generate SoC Documentation.")
    bios_group = parser.add_argument_group(title="BIOS options") # FIXME: Move?
    bios_group.add_argument("--bios-lto",     action="store_true", help="Enable BIOS LTO (Link Time Optimization) compilation.")
    bios_group.add_argument("--bios-console", default="full"  ,    help="Select BIOS console config.", choices=["full", "no-history", "no-autocomplete", "lite", "disable"])

def builder_argdict(args):
    return {
        "output_dir"       : args.output_dir,
        "gateware_dir"     : args.gateware_dir,
        "software_dir"     : args.software_dir,
        "include_dir"      : args.include_dir,
        "generated_dir"    : args.generated_dir,
        "build_backend"    : args.build_backend,
        "compile_software" : (not args.no_compile) and (not args.no_compile_software),
        "compile_gateware" : (not args.no_compile) and (not args.no_compile_gateware),
        "csr_csv"          : args.csr_csv,
        "csr_json"         : args.csr_json,
        "csr_svd"          : args.csr_svd,
        "memory_x"         : args.memory_x,
        "generate_doc"     : args.doc,
        "bios_lto"         : args.bios_lto,
        "bios_console"     : args.bios_console,
    }
