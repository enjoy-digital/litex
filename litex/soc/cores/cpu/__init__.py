#
# This file is part of LiteX.
#
# Copyright (c) 2015-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017-2018 Tim 'mithro' Ansell <me@mith.ro>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import inspect
import importlib
import logging

from migen import *

from litex.gen import *

# CPU (Generic) ------------------------------------------------------------------------------------

class CPU(LiteXModule):
    category                 = None
    family                   = None
    name                     = "None"
    data_width               = None
    endianness               = None
    gcc_triple               = None
    gcc_flags                = None
    clang_triple             = None
    clang_flags              = None
    linker_output_format     = None
    interrupts               = {}
    mem_map                  = {"csr": 0x82000000}
    io_regions               = {}
    use_rom                  = False
    csr_decode               = True
    reset_address_check      = True
    integrated_rom_supported = True

    def __init__(self, *args, **kwargs):
        pass

    def set_reset_address(self, reset_address):
        pass # pass must be overloaded (if required)

    def bios_map(self, addr, cached):
        return addr

    def enable_reset_address_check(self):
        self.reset_address_check = True

    def disable_reset_address_check(self):
        self.reset_address_check = False

# CPU None (Used for SoC without a CPU) ------------------------------------------------------------

class CPUNone(CPU):
    variants                 = ["standard"]
    endianness               = "little"
    reset_address            = 0x00000000
    reset_address_check      = False
    periph_buses             = []
    memory_buses             = []
    mem_map                  = {
        "csr"      : 0x0000_0000,
        "ethmac"   : 0x0002_0000, # FIXME: Remove.
        "spiflash" : 0x1000_0000, # FIXME: Remove.
    }
    integrated_rom_supported = False

    def __init__(self, data_width=32, addr_width=32):
        self.io_regions = {0: int(2**float(addr_width))} # origin, length
        self.data_width = data_width

# CPUs GCC Triples ---------------------------------------------------------------------------------

CPU_GCC_TRIPLE_RISCV64 = (
    "riscv64-pc-linux-musl",
    "riscv64-unknown-elf",
    "riscv64-unknown-linux-gnu",
    "riscv64-elf",
    "riscv64-linux",
    "riscv64-linux-gnu",
    "riscv-sifive-elf",
    "riscv64-none-elf",
)

CPU_GCC_TRIPLE_RISCV32 = CPU_GCC_TRIPLE_RISCV64 + (
    "riscv32-pc-linux-musl",
    "riscv32-unknown-elf",
    "riscv32-unknown-linux-gnu",
    "riscv32-elf",
    "riscv32-linux",
    "riscv32-linux-gnu",
    "riscv32-none-elf",
    "riscv-none-embed",
    "riscv-none-elf",
)

CPU_GCC_TRIPLE_MIPS = (
    "mipsel-linux-gnu",
    "mipsel-linux-musl",
    "mipsel-linux-musln32sf",
    "mipsel-linux-muslsf",
    "mips-unknown-elf",
    "mips-sde-elf",
    "mips-mti-elf",
    "mips-img-elf",
    "mips-linux-musl",
    "mips-linux-musln32sf",
    "mips-linux-muslsf",
    "mips64-linux-musl",
    "mips64-linux-musln32",
    "mips64-linux-musln32sf",
    "mips64-linux-muslsf",
    "mips64el-linux-musl",
    "mips64el-linux-musln32",
    "mips64el-linux-musln32sf",
    "mips64el-linux-muslsf",
    "mips-linux-gnu",
    "mips64-linux-gnu",
    "mips64-linux-gnuabi64",
    "mips64el-linux-gnu",
    "mips64el-linux-gnuabi64",
    "mipsisa32r6-linux-gnu",
    "mipsisa32r6el-linux-gnu",
    "mipsisa64r6-linux-gnuabi64",
    "mipsisa64r6el-linux-gnuabi64",
)

# CPUs Collection ----------------------------------------------------------------------------------

def collect_cpus():
    logger = logging.getLogger("CPU")
    cpus  = {"None" : CPUNone, None: CPUNone}
    paths = [
        # Add litex.soc.cores.cpu path.
        os.path.dirname(__file__),
        # Add execution path.
        os.getcwd()
    ]

    def import_cpu_module(path, cpu):
        sys.path.append(path)
        try:
            return importlib.import_module(cpu)
        finally:
            if sys.path and sys.path[-1] == path:
                sys.path.pop()
            else:
                sys.path.remove(path)

    # Search for CPUs in paths.
    for path in paths:
        for file in os.listdir(path):

            # Verify that it's a path...
            cpu_path = os.path.join(path, file)
            if not os.path.isdir(cpu_path):
                continue

            # ... and that core.py is present.
            cpu_core = os.path.join(cpu_path, "core.py")
            if not os.path.exists(cpu_core):
                continue

            # OK, it seems to be a CPU; now get the class and add it to dict.
            cpu = file
            try:
                cpu_module = import_cpu_module(path, cpu)
            except Exception as e:
                logger.warning("Skipping CPU '%s' (import failed): %s", cpu, e)
                continue
            for cpu_name, cpu_cls in inspect.getmembers(cpu_module, inspect.isclass):
                if cpu_name.lower() in [cpu, cpu.replace("_", "")]:
                    if cpu in cpus:
                        logger.warning("CPU '%s' already registered, overriding with %s.", cpu, cpu_path)
                    cpus[cpu] = cpu_cls

    # Return collected CPUs.
    return cpus

CPUS = collect_cpus()
