#
# This file is part of LiteX.
#
# Copyright (c) 2015-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017-2018 Tim 'mithro' Ansell <me@mith.ro>
# SPDX-License-Identifier: BSD-2-Clause

import os
import inspect
import importlib

from migen import *

# CPU ----------------------------------------------------------------------------------------------

class CPU(Module):
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

    def __init__(self, *args, **kwargs):
        pass

    def set_reset_address(self, reset_address):
        pass

class CPUNone(CPU):
    variants      = ["standard"]
    data_width    = 32
    endianness    = "little"
    reset_address = 0x00000000
    io_regions    = {0x00000000: 0x100000000} # origin, length
    periph_buses  = []
    memory_buses  = []
    mem_map       = {
        "csr"      : 0x00000000,
        "ethmac"   : 0x00020000, # FIXME: Remove.
        "spiflash" : 0x10000000, # FIXME: Remove.
    }

CPU_GCC_TRIPLE_RISCV64 = (
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

# CPUS ---------------------------------------------------------------------------------------------

def collect_cpus():
    cpus = {
        # None.
        "None"     : CPUNone,
        # External (CPU class provided externally by design/user)
        "external" : None,
    }
    path = os.path.dirname(__file__)

    # Search for CPUs in cpu directory.
    for file in os.listdir(path):

        # Verify that it's a path...
        cpu_path = os.path.join(os.path.dirname(__file__), file)
        if not os.path.isdir(cpu_path):
            continue

        # ... and that core.py is present.
        cpu_core = os.path.join(cpu_path, "core.py")
        if not os.path.exists(cpu_core):
            continue

        # OK, it seems to be a CPU; now get the class and add it to dict.
        cpu        = file
        cpu_module = f"litex.soc.cores.cpu.{cpu}.core"
        for cpu_name, cpu_cls in inspect.getmembers(importlib.import_module(cpu_module), inspect.isclass):
            if cpu.replace("_", "") == cpu_name.lower():
                cpus[cpu] = cpu_cls

    # Return collected CPUs.
    return cpus

CPUS = collect_cpus()
