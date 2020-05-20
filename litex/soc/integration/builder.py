# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018-2019 Antmicro <www.antmicro.com>
# This file is Copyright (c) 2018 Sergiusz Bazanski <q3k@q3k.org>
# This file is Copyright (c) 2016-2017 Tim 'mithro' Ansell <mithro@mithis.com>
# This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# This file is Copyright (c) 2020 Xiretza <xiretza@xiretza.xyz>
# This file is Copyright (c) 2020 Piotr Esden-Tempski <piotr@esden.net>
# License: BSD


import os
import subprocess
import struct
import shutil

from litex import get_data_mod
from litex.build.tools import write_to_file
from litex.soc.integration import export, soc_core

__all__ = ["soc_software_packages", "soc_directory",
           "Builder", "builder_args", "builder_argdict"]


soc_software_packages = [
    "libcompiler_rt",
    "libbase",
    "liblitedram",
    "libliteeth",
    "liblitespi",
    "liblitesdcard",
    "bios"
]


soc_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _makefile_escape(s):
    return s.replace("\\", "\\\\")


class Builder:
    def __init__(self, soc,
        output_dir       = None,
        gateware_dir     = None,
        software_dir     = None,
        include_dir      = None,
        generated_dir    = None,
        compile_software = True,
        compile_gateware = True,
        csr_json         = None,
        csr_csv          = None,
        csr_svd          = None,
        memory_x         = None,
        bios_options     = None):
        self.soc = soc

        # From Python doc: makedirs() will become confused if the path elements to create include '..'
        self.output_dir    = os.path.abspath(output_dir    or os.path.join("build", soc.platform.name))
        self.gateware_dir  = os.path.abspath(gateware_dir  or os.path.join(self.output_dir,   "gateware"))
        self.software_dir  = os.path.abspath(software_dir  or os.path.join(self.output_dir,   "software"))
        self.include_dir   = os.path.abspath(include_dir   or os.path.join(self.software_dir, "include"))
        self.generated_dir = os.path.abspath(generated_dir or os.path.join(self.include_dir,  "generated"))

        self.compile_software = compile_software
        self.compile_gateware = compile_gateware
        self.csr_csv  = csr_csv
        self.csr_json = csr_json
        self.csr_svd  = csr_svd
        self.memory_x = memory_x
        self.bios_options = bios_options

        self.software_packages = []
        for name in soc_software_packages:
            self.add_software_package(name)

    def add_software_package(self, name, src_dir=None):
        if src_dir is None:
            src_dir = os.path.join(soc_directory, "software", name)
        self.software_packages.append((name, src_dir))

    def _generate_includes(self):
        os.makedirs(self.include_dir, exist_ok=True)
        os.makedirs(self.generated_dir, exist_ok=True)

        if self.soc.cpu_type is not None:
            variables_contents = []
            def define(k, v):
                variables_contents.append("{}={}\n".format(k, _makefile_escape(v)))

            for k, v in export.get_cpu_mak(self.soc.cpu, self.compile_software):
                define(k, v)
            # Distinguish between LiteX and MiSoC.
            define("LITEX", "1")
            # Distinguish between applications running from main RAM and
            # flash for user-provided software packages.
            exec_profiles = {
                "COPY_TO_MAIN_RAM" : "0",
                "EXECUTE_IN_PLACE" : "0"
            }
            if "main_ram" in self.soc.mem_regions.keys():
                exec_profiles["COPY_TO_MAIN_RAM"] = "1"
            else:
                exec_profiles["EXECUTE_IN_PLACE"] = "1"
            for k, v in exec_profiles.items():
                define(k, v)
            define(
                "COMPILER_RT_DIRECTORY",
                get_data_mod("software", "compiler_rt").data_location)
            define("SOC_DIRECTORY", soc_directory)
            variables_contents.append("export BUILDINC_DIRECTORY\n")
            define("BUILDINC_DIRECTORY", self.include_dir)
            for name, src_dir in self.software_packages:
                define(name.upper() + "_DIRECTORY", src_dir)

            if self.bios_options is not None:
                for option in self.bios_options:
                    define(option, "1")

            write_to_file(
                os.path.join(self.generated_dir, "variables.mak"),
                "".join(variables_contents))
            write_to_file(
                os.path.join(self.generated_dir, "output_format.ld"),
                export.get_linker_output_format(self.soc.cpu))
            write_to_file(
                os.path.join(self.generated_dir, "regions.ld"),
                export.get_linker_regions(self.soc.mem_regions))

        write_to_file(
            os.path.join(self.generated_dir, "mem.h"),
            export.get_mem_header(self.soc.mem_regions))
        write_to_file(
            os.path.join(self.generated_dir, "soc.h"),
            export.get_soc_header(self.soc.constants))
        write_to_file(
            os.path.join(self.generated_dir, "csr.h"),
            export.get_csr_header(self.soc.csr_regions,
                                         self.soc.constants)
        )
        write_to_file(
            os.path.join(self.generated_dir, "git.h"),
            export.get_git_header()
        )

        if hasattr(self.soc, "sdram"):
            from litedram.init import get_sdram_phy_c_header
            write_to_file(os.path.join(self.generated_dir, "sdram_phy.h"),
                get_sdram_phy_c_header(
                    self.soc.sdram.controller.settings.phy,
                    self.soc.sdram.controller.settings.timing))

    def _generate_csr_map(self):
        if self.csr_json is not None:
            csr_dir = os.path.dirname(os.path.realpath(self.csr_json))
            os.makedirs(csr_dir, exist_ok=True)
            write_to_file(self.csr_json, export.get_csr_json(self.soc.csr_regions, self.soc.constants, self.soc.mem_regions))

        if self.csr_csv is not None:
            csr_dir = os.path.dirname(os.path.realpath(self.csr_csv))
            os.makedirs(csr_dir, exist_ok=True)
            write_to_file(self.csr_csv, export.get_csr_csv(self.soc.csr_regions, self.soc.constants, self.soc.mem_regions))

        if self.csr_svd is not None:
            svd_dir = os.path.dirname(os.path.realpath(self.csr_svd))
            os.makedirs(svd_dir, exist_ok=True)
            write_to_file(self.csr_svd, export.get_csr_svd(self.soc))

    def _generate_mem_region_map(self):
        if self.memory_x is not None:
            memory_x_dir = os.path.dirname(os.path.realpath(self.memory_x))
            os.makedirs(memory_x_dir, exist_ok=True)
            write_to_file(self.memory_x, export.get_memory_x(self.soc))

    def _prepare_rom_software(self):
        for name, src_dir in self.software_packages:
            dst_dir = os.path.join(self.software_dir, name)
            os.makedirs(dst_dir, exist_ok=True)

    def _generate_rom_software(self, compile_bios=True):
         for name, src_dir in self.software_packages:
            if name == "bios" and not compile_bios:
                pass
            else:
                dst_dir = os.path.join(self.software_dir, name)
                makefile = os.path.join(src_dir, "Makefile")
                if self.compile_software:
                    subprocess.check_call(["make", "-C", dst_dir, "-f", makefile])

    def _initialize_rom_software(self):
        bios_file = os.path.join(self.software_dir, "bios", "bios.bin")
        bios_data = soc_core.get_mem_data(bios_file, self.soc.cpu.endianness)
        self.soc.initialize_rom(bios_data)

    def build(self, **kwargs):
        self.soc.platform.output_dir = self.output_dir
        os.makedirs(self.gateware_dir, exist_ok=True)
        os.makedirs(self.software_dir, exist_ok=True)

        self.soc.finalize()

        self._generate_includes()
        self._generate_csr_map()
        self._generate_mem_region_map()
        if self.soc.cpu_type is not None:
            if self.soc.cpu.use_rom:
                self._prepare_rom_software()
                self._generate_rom_software(not self.soc.integrated_rom_initialized)
                if self.soc.integrated_rom_size and self.compile_software:
                    if not self.soc.integrated_rom_initialized:
                        self._initialize_rom_software()

        if "run" not in kwargs:
            kwargs["run"] = self.compile_gateware
        vns = self.soc.build(build_dir=self.gateware_dir, **kwargs)
        self.soc.do_exit(vns=vns)
        return vns


def builder_args(parser):
    parser.add_argument("--output-dir", default=None,
                        help="base output directory for generated "
                             "source files and binaries (customizable "
                             "with --{gateware,software,include,generated}-dir)")
    parser.add_argument("--gateware-dir", default=None,
                        help="output directory for gateware files")
    parser.add_argument("--software-dir", default=None,
                        help="base output directory for software files")
    parser.add_argument("--include-dir", default=None,
                        help="output directory for header files")
    parser.add_argument("--generated-dir", default=None,
                        help="output directory for various generated files")
    parser.add_argument("--no-compile-software", action="store_true",
                        help="do not compile the software, only generate "
                             "build infrastructure")
    parser.add_argument("--no-compile-gateware", action="store_true",
                        help="do not compile the gateware, only generate "
                             "HDL source files and build scripts")
    parser.add_argument("--csr-csv", default=None,
                        help="store CSR map in CSV format into the "
                             "specified file")
    parser.add_argument("--csr-json", default=None,
                        help="store CSR map in JSON format into the "
                             "specified file")
    parser.add_argument("--csr-svd", default=None,
                        help="store CSR map in SVD format into the "
                             "specified file")
    parser.add_argument("--memory-x", default=None,
                        help="store Mem regions in memory-x format into the "
                             "specified file")


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
    }
