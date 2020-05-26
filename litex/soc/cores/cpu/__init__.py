# This file is Copyright (c) 2017-2018 Tim 'mithro' Ansell <me@mith.ro>
# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

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
    reset_address        = 0x00000000
    io_regions           = {0x00000000: 0x100000000} # origin, length
    periph_buses         = []
    memory_buses         = []
    mem_map              = {"csr": 0x00000000}

CPU_GCC_TRIPLE_RISCV32 = (
    "riscv64-unknown-elf",
    "riscv32-unknown-elf",
    "riscv-none-embed",
    "riscv64-linux",
    "riscv-sifive-elf",
    "riscv64-none-elf",
)

CPU_GCC_TRIPLE_RISCV64 = (
    "riscv64-unknown-elf",
    "riscv64-linux",
    "riscv-sifive-elf",
    "riscv64-none-elf",
)

# CPUS ---------------------------------------------------------------------------------------------

from litex.soc.cores.cpu.lm32 import LM32
from litex.soc.cores.cpu.mor1kx import MOR1KX
from litex.soc.cores.cpu.microwatt import Microwatt
from litex.soc.cores.cpu.serv import SERV
from litex.soc.cores.cpu.picorv32 import PicoRV32
from litex.soc.cores.cpu.minerva import Minerva
from litex.soc.cores.cpu.vexriscv import VexRiscv
from litex.soc.cores.cpu.rocket import RocketRV64
from litex.soc.cores.cpu.blackparrot import BlackParrotRV64
from litex.soc.cores.cpu.cv32e40p import CV32E40P

CPUS = {
    # None
    "None"        : CPUNone,

    # LM32
    "lm32"        : LM32,

    # OpenRisc
    "mor1kx"      : MOR1KX,

    # Open Power
    "microwatt"   : Microwatt,

    # RISC-V 32-bit
    "serv"        : SERV,
    "picorv32"    : PicoRV32,
    "minerva"     : Minerva,
    "vexriscv"    : VexRiscv,
    "cv32e40p"    : CV32E40P,

    # RISC-V 64-bit
    "rocket"      : RocketRV64,
    "blackparrot" : BlackParrotRV64,
}
