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

class CPUNone(CPU):
    data_width           = 32
    reset_address        = 0x00000000
    io_regions           = {0x00000000: 0xf0000000} # origin, length

# CPUS ---------------------------------------------------------------------------------------------

from litex.soc.cores.cpu.lm32 import LM32
from litex.soc.cores.cpu.mor1kx import MOR1KX
from litex.soc.cores.cpu.picorv32 import PicoRV32
from litex.soc.cores.cpu.vexriscv import VexRiscv
from litex.soc.cores.cpu.minerva import Minerva
from litex.soc.cores.cpu.rocket import RocketRV64
from litex.soc.cores.cpu.microwatt import Microwatt

CPUS = {
    "lm32"       : LM32,
    "mor1kx"     : MOR1KX,
    "picorv32"   : PicoRV32,
    "vexriscv"   : VexRiscv,
    "minerva"    : Minerva,
    "rocket"     : RocketRV64,
    "microwatt"  : Microwatt,
}

# CPU Variants/Extensions Definition ---------------------------------------------------------------

CPU_VARIANTS = {
    # "official name": ["alias 1", "alias 2"],
    "minimal" : ["min",],
    "lite" : ["light", "zephyr", "nuttx"],
    "standard": [None, "std"],
    "full": [],
    "linux" : [],
    "linuxd" : [],
    "linuxq" : [],
}
CPU_VARIANTS_EXTENSIONS = ["debug", "no-dsp"]


class InvalidCPUVariantError(ValueError):
    def __init__(self, variant):
        msg = """\
Invalid cpu_variant value: {}

Possible Values:
""".format(variant)
        for k, v in CPU_VARIANTS.items():
            msg += " - {} (aliases: {})\n".format(k, ", ".join(str(s) for s in v))
        ValueError.__init__(self, msg)


class InvalidCPUExtensionError(ValueError):
    def __init__(self, variant):
        msg = """\
Invalid extension in cpu_variant value: {}

Possible Values:
""".format(variant)
        for e in CPU_VARIANTS_EXTENSIONS:
            msg += " - {}\n".format(e)
        ValueError.__init__(self, msg)

# CPU Variants/Extensions Check/Format -------------------------------------------------------------

def check_format_cpu_variant(variant):
	# Support the old style which used underscore for separator
    if variant is None:
        variant = "standard"
    variant = variant.replace('_', '+')

    # Check for valid CPU variants.
    processor, *extensions = variant.split('+')
    for k, v in CPU_VARIANTS.items():
        if processor not in [k,]+v:
            continue
        _variant = k
        break
    else:
        raise InvalidCPUVariantError(variant)

    # Check for valid CPU extensions.
    for extension in sorted(extensions):
        if extension not in CPU_VARIANTS_EXTENSIONS:
            raise InvalidCPUExtensionError(variant)
        _variant += "+"+extension

    return _variant
