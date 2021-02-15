#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017-2018 Tim 'mithro' Ansell <me@mith.ro>
# SPDX-License-Identifier: BSD-2-Clause

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
    mem_map              = {}
    io_regions           = {}
    use_rom              = False

    def __init__(self, *args, **kwargs):
        pass

class CPUNone(CPU):
    variants             = ["standard"]
    data_width           = 32
    endianness           = "little"
    reset_address        = 0x00000000
    io_regions           = {0x00000000: 0x100000000} # origin, length
    periph_buses         = []
    memory_buses         = []
    mem_map              = {"csr": 0x00000000}

CPU_GCC_TRIPLE_RISCV32 = (
    "riscv64-unknown-elf",
    "riscv64-unknown-linux-gnu",
    "riscv32-unknown-elf",
    "riscv32-unknown-linux-gnu",
    "riscv64-elf",
    "riscv32-elf",
    "riscv-none-embed",
    "riscv64-linux",
    "riscv64-linux-gnu",
    "riscv-sifive-elf",
    "riscv64-none-elf",
)

CPU_GCC_TRIPLE_RISCV64 = (
    "riscv64-unknown-elf",
    "riscv64-unknown-linux-gnu",
    "riscv64-elf",
    "riscv64-linux",
    "riscv64-linux-gnu",
    "riscv-sifive-elf",
    "riscv64-none-elf",
)

# CPUS ---------------------------------------------------------------------------------------------

# LM32
from litex.soc.cores.cpu.lm32 import LM32

# OpenRisc
from litex.soc.cores.cpu.mor1kx import MOR1KX

# OpenPower
from litex.soc.cores.cpu.microwatt import Microwatt

# RISC-V (32-bit)
from litex.soc.cores.cpu.serv import SERV
from litex.soc.cores.cpu.picorv32 import PicoRV32
from litex.soc.cores.cpu.minerva import Minerva
from litex.soc.cores.cpu.vexriscv import VexRiscv
from litex.soc.cores.cpu.vexriscv_smp import VexRiscvSMP
from litex.soc.cores.cpu.ibex import Ibex
from litex.soc.cores.cpu.cv32e40p import CV32E40P

# RISC-V (64-bit)
from litex.soc.cores.cpu.rocket import RocketRV64
from litex.soc.cores.cpu.blackparrot import BlackParrotRV64

# Zynq
from litex.soc.cores.cpu.zynq7000 import Zynq7000


CPUS = {
    # None
    "None"        : CPUNone,

    # External (CPU class provided externally by design/user)
    "external"    : None,

    # LM32
    "lm32"        : LM32,

    # OpenRisc
    "mor1kx"      : MOR1KX,

    # OpenPower
    "microwatt"   : Microwatt,

    # RISC-V (32-bit)
    "serv"        : SERV,
    "picorv32"    : PicoRV32,
    "minerva"     : Minerva,
    "vexriscv"    : VexRiscv,
    "vexriscv_smp": VexRiscvSMP,
    "ibex"        : Ibex,
    "cv32e40p"    : CV32E40P,

    # RISC-V (64-bit)
    "rocket"      : RocketRV64,
    "blackparrot" : BlackParrotRV64,

    # Zynq
    "zynq7000"    : Zynq7000,
}
