#
# This file is part of LiteX.
#
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

# Common helpers shared by the LiteX DTS generators (Linux, Zephyr).

import re

# RISC-V -------------------------------------------------------------------------------------------

def get_riscv_cpu_isa_base(cpu_isa):
    return cpu_isa[:5]

def get_riscv_cpu_isa_extensions_by_string(isa):
    VERSION_PATTERN = re.compile(r"\d+p\d+$")

    extensions = set()
    length = len(isa)

    isa = isa.lower()

    if not (isa.startswith("rv64") or isa.startswith("rv32")):
        raise ValueError("ISA string must start with rv32|rv64")

    slices = isa[4:].lower().split('_')

    for slice in slices:
        if not slice.isalnum():
            raise ValueError(f"Extension ${slice} can not be parsed: invalid character")

        if len(slice) == 1 or (slice[0] == 's') or (slice[0] == 'z'):
            match = VERSION_PATTERN.search(slice)
            if not match is None:
                slice = slice[:match.span()[0]]

            extensions.add(slice)

            continue

        match = VERSION_PATTERN.search(slice)
        if not match is None:
            if len(slice[:match.span()[0]]) > 1:
                raise ValueError(f"Invalid extension string ${slice}: version can only be used separately")

            slice = slice[:match.span()[0]]

        if not slice.isalpha():
            raise ValueError(f"Single letter extension string ${slice} should not contain other characters")

        for extension in slice:
            extensions.add(extension)

    return extensions

def get_riscv_cpu_isa_extensions(cpu_isa, cpu_name):
    isa_extensions = get_riscv_cpu_isa_extensions_by_string(cpu_isa)

    # Add rocket-specific extensions.
    if cpu_name == "rocket":
        isa_extensions.update({"zicsr", "zifencei", "zihpm"})

    # Format extensions.
    return ", ".join(f"\"{extension}\"" for extension in sorted(isa_extensions))
