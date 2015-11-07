import os
import subprocess
import struct

from litex.soc.integration import cpu_interface, soc_sdram, sdram_init


__all__ = ["soc_software_packages", "soc_directory",
           "Builder", "builder_args", "builder_argdict"]


# in build order (for dependencies)
soc_software_packages = [
    "libbase",
    "libcompiler_rt",
    "libdyld",
    "libnet",
    "libunwind",
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
            self.add_software_package(
                name, os.path.join(soc_directory, "software", name))

    def add_software_package(self, name, src_dir):
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
        with open(os.path.join(generated_dir, "variables.mak"), "w") as f:
            def define(k, v):
                f.write("{}={}\n".format(k, _makefile_escape(v)))
            for k, v in cpu_interface.get_cpu_mak(cpu_type):
                define(k, v)
            define("SOC_DIRECTORY", soc_directory)
            define("BUILDINC_DIRECTORY", buildinc_dir)
            for name, src_dir in self.software_packages:
                define(name.upper() + "_DIRECTORY", src_dir)

        with open(os.path.join(generated_dir, "output_format.ld"), "w") as f:
            f.write(cpu_interface.get_linker_output_format(cpu_type))
        with open(os.path.join(generated_dir, "regions.ld"), "w") as f:
            f.write(cpu_interface.get_linker_regions(memory_regions))

        with open(os.path.join(generated_dir, "mem.h"), "w") as f:
            f.write(cpu_interface.get_mem_header(memory_regions, flash_boot_address))
        with open(os.path.join(generated_dir, "csr.h"), "w") as f:
            f.write(cpu_interface.get_csr_header(csr_regions, constants))

        if sdram_phy_settings is not None:
            with open(os.path.join(generated_dir, "sdram_phy.h"), "w") as f:
                f.write(sdram_init.get_sdram_phy_header(sdram_phy_settings))

        if self.csr_csv is not None:
            with open(self.csr_csv, "w") as f:
                f.write(cpu_interface.get_csr_csv(csr_regions))

    def _generate_software(self):
        for name, src_dir in self.software_packages:
            dst_dir = os.path.join(self.output_dir, "software", name)
            os.makedirs(dst_dir, exist_ok=True)
            src = os.path.join(src_dir, "Makefile")
            dst = os.path.join(dst_dir, "Makefile")
            try:
                os.remove(dst)
            except FileNotFoundError:
                pass
            os.symlink(src, dst)
            if self.compile_software:
                subprocess.check_call(["make", "-C", dst_dir])

    def _initialize_rom(self):
        bios_file = os.path.join(self.output_dir, "software", "bios",
                                 "bios.bin")
        if self.soc.integrated_rom_size:
            with open(bios_file, "rb") as boot_file:
                boot_data = []
                while True:
                    w = boot_file.read(4)
                    if not w:
                        break
                    boot_data.append(struct.unpack(">I", w)[0])
            self.soc.initialize_rom(boot_data)

    def build(self):
        self.soc.finalize()

        if self.soc.integrated_rom_size and not self.compile_software:
            raise ValueError("Software must be compiled in order to "
                             "intitialize integrated ROM")

        self._generate_includes()
        self._generate_software()
        self._initialize_rom()
        if self.gateware_toolchain_path is None:
            kwargs = dict()
        else:
            kwargs = {"toolchain_path": self.gateware_toolchain_path}
        self.soc.build(build_dir=os.path.join(self.output_dir, "gateware"),
                       run=self.compile_gateware, **kwargs)


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
