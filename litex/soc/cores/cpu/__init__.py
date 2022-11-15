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

from migen import *

# CPU (Generic) ------------------------------------------------------------------------------------

class CPU(Module):
    category             = None
    family               = None
    name                 = None
    data_width           = None
    endianness           = None
    gcc_triple           = None
    gcc_flags            = None
    clang_triple         = None
    clang_flags          = None
    linker_output_format = None
    interrupts           = {}
    mem_map              = {"csr": 0x82000000}
    io_regions           = {}
    use_rom              = False
    csr_decode           = True
    reset_address_check  = True

    def __init__(self, *args, **kwargs):
        pass

    def set_reset_address(self, reset_address):
        pass # pass must be overloaded (if required)

    def enable_reset_address_check(self):
        self.reset_address_check = True

    def disable_reset_address_check(self):
        self.reset_address_check = False

# CPU None (Used for SoC without a CPU) ------------------------------------------------------------

class CPUNone(CPU):
    variants            = ["standard"]
    data_width          = 32
    endianness          = "little"
    reset_address       = 0x00000000
    reset_address_check = False
    io_regions          = {0x0000_0000: 0x1_0000_0000} # origin, length
    periph_buses        = []
    memory_buses        = []
    mem_map             = {
        "csr"      : 0x0000_0000,
        "ethmac"   : 0x0002_0000, # FIXME: Remove.
        "spiflash" : 0x1000_0000, # FIXME: Remove.
    }

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
    "riscv32-unknown-elf",
    "riscv32-unknown-linux-gnu",
    "riscv32-elf",
    "riscv-none-embed",
    "riscv-none-elf",
)

# CPUs Collection ----------------------------------------------------------------------------------

def collect_cpus():
    cpus  = {"None" : CPUNone}
    paths = [
        # Add litex.soc.cores.cpu path.
        os.path.dirname(__file__),
        # Add execution path.
        os.getcwd()
    ]

    exec_dir = os.getcwd()

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
            sys.path.append(path)
            for cpu_name, cpu_cls in inspect.getmembers(importlib.import_module(cpu), inspect.isclass):
                if cpu_name.lower() in [cpu, cpu.replace("_", "")]:
                    cpus[cpu] = cpu_cls

    # Return collected CPUs.
    return cpus

CPUS = collect_cpus()
