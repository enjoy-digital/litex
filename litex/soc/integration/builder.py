import os
import subprocess
import struct
import shutil

from litex.build.tools import write_to_file
from litex.soc.integration import cpu_interface, soc_sdram, sdram_init


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
    def __init__(self, soc, output_dir=None,
                 compile_software=True, compile_gateware=True,
                 gateware_toolchain_path=None,
                 csr_csv=None):
        self.soc = soc
        if output_dir is None:
            output_dir = "soc_{}_{}".format(
                soc.__class__.__name__.lower(),
                soc.platform.name)
        # From Python doc: makedirs() will become confused if the path
        # elements to create include '..'
        self.output_dir = os.path.abspath(output_dir)
        self.compile_software = compile_software
        self.compile_gateware = compile_gateware
        self.gateware_toolchain_path = gateware_toolchain_path
        self.csr_csv = csr_csv

        self.software_packages = []
        for name in soc_software_packages:
            self.add_software_package(name)

    def add_software_package(self, name, src_dir=None):
        if src_dir is None:
            src_dir = os.path.join(soc_directory, "software", name)
        self.software_packages.append((name, src_dir))

    def _generate_includes(self):
        cpu_type = self.soc.cpu_type
        memory_regions = self.soc.get_memory_regions()
        flash_boot_address = getattr(self.soc, "flash_boot_address", None)
        csr_regions = self.soc.get_csr_regions()
        constants = self.soc.get_constants()
        if isinstance(self.soc, soc_sdram.SoCSDRAM) and self.soc._sdram_phy:
            sdram_phy_settings = self.soc._sdram_phy[0].settings
        else:
            sdram_phy_settings = None

        buildinc_dir = os.path.join(self.output_dir, "software", "include")
        generated_dir = os.path.join(buildinc_dir, "generated")
        os.makedirs(generated_dir, exist_ok=True)

        variables_contents = []
        def define(k, v):
            variables_contents.append("{}={}\n".format(k, _makefile_escape(v)))
        for k, v in cpu_interface.get_cpu_mak(cpu_type):
            define(k, v)
        define("SOC_DIRECTORY", soc_directory)
        variables_contents.append("export BUILDINC_DIRECTORY\n")
        define("BUILDINC_DIRECTORY", buildinc_dir)
        for name, src_dir in self.software_packages:
            define(name.upper() + "_DIRECTORY", src_dir)
        write_to_file(
            os.path.join(generated_dir, "variables.mak"),
            "".join(variables_contents))

        write_to_file(
            os.path.join(generated_dir, "output_format.ld"),
            cpu_interface.get_linker_output_format(cpu_type))
        write_to_file(
            os.path.join(generated_dir, "regions.ld"),
            cpu_interface.get_linker_regions(memory_regions))

        write_to_file(
            os.path.join(generated_dir, "mem.h"),
            cpu_interface.get_mem_header(memory_regions, flash_boot_address))
        write_to_file(
            os.path.join(generated_dir, "csr.h"),
            cpu_interface.get_csr_header(csr_regions, constants))

        if sdram_phy_settings is not None:
            write_to_file(
                os.path.join(generated_dir, "sdram_phy.h"),
                sdram_init.get_sdram_phy_header(sdram_phy_settings))

    def _generate_csr_csv(self):
        memory_regions = self.soc.get_memory_regions()
        csr_regions = self.soc.get_csr_regions()
        constants = self.soc.get_constants()

        csr_dir = os.path.dirname(self.csr_csv)
        os.makedirs(csr_dir, exist_ok=True)
        write_to_file(
            self.csr_csv,
            cpu_interface.get_csr_csv(csr_regions, constants, memory_regions))

    def _prepare_software(self):
        for name, src_dir in self.software_packages:
            dst_dir = os.path.join(self.output_dir, "software", name)
            os.makedirs(dst_dir, exist_ok=True)

    def _generate_software(self, compile_bios=True):
         for name, src_dir in self.software_packages:
            if name == "bios" and not compile_bios:
                pass
            else:
                dst_dir = os.path.join(self.output_dir, "software", name)
                makefile = os.path.join(src_dir, "Makefile")
                if self.compile_software:
                    subprocess.check_call(["make", "-C", dst_dir, "-f", makefile])

    def _initialize_rom(self):
        bios_file = os.path.join(self.output_dir, "software", "bios",
                                 "bios.bin")
        endianness =  cpu_interface.cpu_endianness[self.soc.cpu_type]
        with open(bios_file, "rb") as boot_file:
            boot_data = []
            while True:
                w = boot_file.read(4)
                if not w:
                    break
                if endianness == 'little':
                    boot_data.append(struct.unpack("<I", w)[0])
                else:
                    boot_data.append(struct.unpack(">I", w)[0])
        self.soc.initialize_rom(boot_data)

    def build(self, toolchain_path=None, **kwargs):
        self.soc.finalize()

        os.makedirs(self.output_dir, exist_ok=True)

        if self.soc.cpu_type is not None:
            self._prepare_software()
            self._generate_includes()
            self._generate_software(not self.soc.integrated_rom_initialized)
            if self.soc.integrated_rom_size and self.compile_software:
                if not self.soc.integrated_rom_initialized:
                    self._initialize_rom()

        if self.csr_csv is not None:
            self._generate_csr_csv()

        if self.gateware_toolchain_path is not None:
            toolchain_path = self.gateware_toolchain_path

        if 'run' not in kwargs:
            kwargs['run'] = self.compile_gateware
        vns = self.soc.build(build_dir=os.path.join(self.output_dir, "gateware"),
                             toolchain_path=toolchain_path, **kwargs)
        return vns


def builder_args(parser):
    parser.add_argument("--output-dir", default=None,
                        help="output directory for generated "
                             "source files and binaries")
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


def builder_argdict(args):
    return {
        "output_dir": args.output_dir,
        "compile_software": not args.no_compile_software,
        "compile_gateware": not args.no_compile_gateware,
        "gateware_toolchain_path": args.gateware_toolchain_path,
        "csr_csv": args.csr_csv
    }
