import os
import subprocess
import struct

from misoc.integration import cpu_interface, sdram_init


# in build order (for dependencies)
misoc_software_packages = [
    "libbase",
    "libcompiler_rt",
    "libdyld",
    "libnet",
    "libunwind",
    "bios"
]


misoc_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Builder:
    def __init__(self, soc, output_dir):
        self.soc = soc
        # From Python doc: makedirs() will become confused if the path
        # elements to create include '..'
        self.output_dir = os.path.abspath(output_dir)

        self.software_packages = []
        for name in misoc_software_packages:
            self.add_software_package(
                name, os.path.join(misoc_directory, "software", name))

    def add_software_package(self, name, src_dir):
        self.software_packages.append((name, src_dir))

    def _generate_includes(self):
        cpu_type = self.soc.cpu_type
        memory_regions = self.soc.get_memory_regions()
        flash_boot_address = getattr(self.soc, "flash_boot_address", None)
        csr_regions = self.soc.get_csr_regions()
        constants = self.soc.get_constants()
        # TODO: cleanup
        sdram_phy_settings = None
        for sdram_phy in "sdrphy", "ddrphy":
            if hasattr(self.soc, sdram_phy):
                sdram_phy_settings = getattr(self.soc, sdram_phy).settings

        buildinc_dir = os.path.join(self.output_dir, "software", "include")
        generated_dir = os.path.join(buildinc_dir, "generated")
        os.makedirs(generated_dir, exist_ok=True)
        with open(os.path.join(generated_dir, "variables.mak"), "w") as f:
            def define(k, v):
                f.write("{}={}\n".format(k, v))
            for k, v in cpu_interface.get_cpu_mak(cpu_type):
                define(k, v)
            define("MISOC_DIRECTORY", misoc_directory)
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

    def _generate_software(self, compile):
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
            if compile:
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

    def build(self, compile_software=True, compile_gateware=True):
        self.soc.finalize()

        if self.soc.integrated_rom_size and not compile_software:
            raise ValueError("Software must be compiled in order to "
                             "intitialize integrated ROM")

        self._generate_includes()
        self._generate_software(compile_software)
        self._initialize_rom()
        self.soc.build(build_dir=os.path.join(self.output_dir, "gateware"),
                       run=compile_gateware)
