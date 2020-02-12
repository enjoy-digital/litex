# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Mateusz Holenko <mholenko@antmicro.com>
# This file is Copyright (c) 2018 Peter Gielda <pgielda@antmicro.com>
# This file is Copyright (c) 2018 Sergiusz Bazanski <q3k@q3k.org>
# This file is Copyright (c) 2016-2017 Tim 'mithro' Ansell <mithro@mithis.com>
# This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# This file is Copyright (c) 2020 Xiretza <xiretza@xiretza.xyz>
# License: BSD


import os
import subprocess
import struct
import shutil

from litex.build.tools import write_to_file
from litex.soc.integration import cpu_interface, soc_core

__all__ = ["soc_software_packages", "soc_directory",
           "Builder", "builder_args", "builder_argdict"]


soc_software_packages = [
    "libcompiler_rt",
    "libbase",
    "libnet",
    "bios"
]


soc_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _makefile_escape(s):
    return s.replace("\\", "\\\\")


class Builder:
    def __init__(self, soc,
        output_dir              = None,
        gateware_dir            = None,
        software_dir            = None,
        include_dir             = None,
        generated_dir           = None,
        compile_software        = True,
        compile_gateware        = True,
        gateware_toolchain_path = None,
        csr_json                = None,
        csr_csv                 = None):
        self.soc = soc

        # From Python doc: makedirs() will become confused if the path
        # elements to create include '..'
        self.output_dir    = os.path.abspath(output_dir    or "soc_{}_{}".format(soc.__class__.__name__.lower(), soc.platform.name))
        self.gateware_dir  = os.path.abspath(gateware_dir  or os.path.join(self.output_dir,   "gateware"))
        self.software_dir  = os.path.abspath(software_dir  or os.path.join(self.output_dir,   "software"))
        self.include_dir   = os.path.abspath(include_dir   or os.path.join(self.software_dir, "include"))
        self.generated_dir = os.path.abspath(generated_dir or os.path.join(self.include_dir,  "generated"))

        self.compile_software = compile_software
        self.compile_gateware = compile_gateware
        self.gateware_toolchain_path = gateware_toolchain_path
        self.csr_csv = csr_csv
        self.csr_json = csr_json

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

            for k, v in cpu_interface.get_cpu_mak(self.soc.cpu, self.compile_software):
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
            define("SOC_DIRECTORY", soc_directory)
            variables_contents.append("export BUILDINC_DIRECTORY\n")
            define("BUILDINC_DIRECTORY", self.include_dir)
            for name, src_dir in self.software_packages:
                define(name.upper() + "_DIRECTORY", src_dir)

            write_to_file(
                os.path.join(self.generated_dir, "variables.mak"),
                "".join(variables_contents))
            write_to_file(
                os.path.join(self.generated_dir, "output_format.ld"),
                cpu_interface.get_linker_output_format(self.soc.cpu))
            write_to_file(
                os.path.join(self.generated_dir, "regions.ld"),
                cpu_interface.get_linker_regions(self.soc.mem_regions))

        write_to_file(
            os.path.join(self.generated_dir, "mem.h"),
            cpu_interface.get_mem_header(self.soc.mem_regions))
        write_to_file(
            os.path.join(self.generated_dir, "soc.h"),
            cpu_interface.get_soc_header(self.soc.constants))
        write_to_file(
            os.path.join(self.generated_dir, "csr.h"),
            cpu_interface.get_csr_header(self.soc.csr_regions,
                                         self.soc.constants)
        )
        write_to_file(
            os.path.join(self.generated_dir, "git.h"),
            cpu_interface.get_git_header()
        )

        if hasattr(self.soc, "sdram"):
            from litedram.init import get_sdram_phy_c_header
            write_to_file(os.path.join(self.generated_dir, "sdram_phy.h"),
                get_sdram_phy_c_header(
                    self.soc.sdram.controller.settings.phy,
                    self.soc.sdram.controller.settings.timing))

    def _generate_csr_map(self, csr_json=None, csr_csv=None):
        if csr_json is not None:
            csr_dir = os.path.dirname(os.path.realpath(csr_json))
            os.makedirs(csr_dir, exist_ok=True)
            write_to_file(csr_json, cpu_interface.get_csr_json(self.soc.csr_regions, self.soc.constants, self.soc.mem_regions))

        if csr_csv is not None:
            csr_dir = os.path.dirname(os.path.realpath(csr_csv))
            os.makedirs(csr_dir, exist_ok=True)
            write_to_file(csr_csv, cpu_interface.get_csr_csv(self.soc.csr_regions, self.soc.constants, self.soc.mem_regions))

    def _prepare_software(self):
        for name, src_dir in self.software_packages:
            dst_dir = os.path.join(self.software_dir, name)
            os.makedirs(dst_dir, exist_ok=True)

    def _generate_software(self, compile_bios=True):
         for name, src_dir in self.software_packages:
            if name == "bios" and not compile_bios:
                pass
            else:
                dst_dir = os.path.join(self.software_dir, name)
                makefile = os.path.join(src_dir, "Makefile")
                if self.compile_software:
                    subprocess.check_call(["make", "-C", dst_dir, "-f", makefile])

    def _initialize_rom(self):
        bios_file = os.path.join(self.software_dir, "bios", "bios.bin")
        bios_data = soc_core.get_mem_data(bios_file, self.soc.cpu.endianness)
        self.soc.initialize_rom(bios_data)

    def build(self, toolchain_path=None, **kwargs):
        self.soc.platform.output_dir = self.output_dir
        os.makedirs(self.gateware_dir, exist_ok=True)
        os.makedirs(self.software_dir, exist_ok=True)

        self.soc.finalize()

        self._generate_includes()
        if self.soc.cpu_type is not None:
            self._prepare_software()
            self._generate_software(not self.soc.integrated_rom_initialized)
            if self.soc.integrated_rom_size and self.compile_software:
                if not self.soc.integrated_rom_initialized:
                    self._initialize_rom()

        self._generate_csr_map(self.csr_json, self.csr_csv)

        if self.gateware_toolchain_path is not None:
            toolchain_path = self.gateware_toolchain_path

        if "run" not in kwargs:
            kwargs["run"] = self.compile_gateware
        vns = self.soc.build(build_dir=self.gateware_dir,
                             toolchain_path=toolchain_path, **kwargs)
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
    parser.add_argument("--gateware-toolchain-path", default=None,
                        help="set gateware toolchain (ISE, Quartus, etc.) "
                             "installation path")
    parser.add_argument("--csr-csv", default=None,
                        help="store CSR map in CSV format into the "
                             "specified file")
    parser.add_argument("--csr-json", default=None,
                        help="store CSR map in JSON format into the "
                             "specified file")


def builder_argdict(args):
    return {
        "output_dir": args.output_dir,
        "gateware_dir": args.gateware_dir,
        "software_dir": args.software_dir,
        "include_dir": args.include_dir,
        "generated_dir": args.generated_dir,
        "compile_software": not args.no_compile_software,
        "compile_gateware": not args.no_compile_gateware,
        "gateware_toolchain_path": args.gateware_toolchain_path,
        "csr_csv": args.csr_csv,
        "csr_json": args.csr_json,
    }
