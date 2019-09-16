# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 Dolu1990 <charles.papon.90@gmail.com>
# This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
# This file is Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
# This file is Copyright (c) 2019 Mateusz Holenko <mholenko@antmicro.com>
# This file is Copyright (c) 2013 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2018 Sean Cross <sean@xobs.io>
# This file is Copyright (c) 2018 Sergiusz Bazanski <q3k@q3k.org>
# This file is Copyright (c) 2018-2016 Tim 'mithro' Ansell <me@mith.ro>
# This file is Copyright (c) 2015 whitequark <whitequark@whitequark.org>
# This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# License: BSD

import os
import json
from shutil import which
from sysconfig import get_platform

from migen import *

from litex.soc.interconnect.csr import CSRStatus

from litex.build.tools import generated_banner

# FIXME: use OrderedDict for constants?
def get_constant(name, constants):
    for n, v in constants:
        if n == name:
            return v
    return None

def get_cpu_mak(cpu, compile_software):
    # select between clang and gcc
    clang = os.getenv("CLANG", "")
    if clang != "":
        clang = bool(int(clang))
    else:
        clang = None
    if not hasattr(cpu, "clang_triple"):
        if clang:
            raise ValueError(cpu.name + "not supported with clang.")
        else:
            clang = False
    else:
        # Default to gcc unless told otherwise
        if clang is None:
            clang = False
    assert isinstance(clang, bool)
    if clang:
        triple = cpu.clang_triple
        flags = cpu.clang_flags
    else:
        triple = cpu.gcc_triple
        flags = cpu.gcc_flags

    # select triple when more than one
    def select_triple(triple):
        r = None
        if not isinstance(triple, tuple):
            triple = (triple,)
        p = get_platform()
        for i in range(len(triple)):
            t = triple[i]
            # use native toolchain if host and target platforms are the same
            if t == 'riscv64-unknown-elf' and p == 'linux-riscv64':
                r = '--native--'
                break
            if which(t+"-gcc"):
                r = t
                break
        if r is None:
            if not compile_software:
                return "--not-found--"
            msg = "Unable to find any of the cross compilation toolchains:\n"
            for i in range(len(triple)):
                msg += "- " + triple[i] + "\n"
            raise OSError(msg)
        return r

    # return informations
    return [
        ("TRIPLE", select_triple(triple)),
        ("CPU", cpu.name),
        ("CPUFLAGS", flags),
        ("CPUENDIANNESS", cpu.endianness),
        ("CLANG", str(int(clang)))
    ]


def get_linker_output_format(cpu):
    return "OUTPUT_FORMAT(\"" + cpu.linker_output_format + "\")\n"


def get_linker_regions(regions):
    r = "MEMORY {\n"
    for name, origin, length in regions:
        r += "\t{} : ORIGIN = 0x{:08x}, LENGTH = 0x{:08x}\n".format(name, origin, length)
    r += "}\n"
    return r


def get_mem_header(regions, flash_boot_address, shadow_base):
    r = generated_banner("//")
    r += "#ifndef __GENERATED_MEM_H\n#define __GENERATED_MEM_H\n\n"
    for name, base, size in regions:
        r += "#define {name}_BASE 0x{base:08x}L\n#define {name}_SIZE 0x{size:08x}\n\n".format(name=name.upper(), base=base, size=size)
    if flash_boot_address is not None:
        r += "#define FLASH_BOOT_ADDRESS 0x{:08x}L\n\n".format(flash_boot_address)
    if shadow_base is not None:
        r += "#define SHADOW_BASE 0x{:08x}L\n\n".format(shadow_base)
    r += "#endif\n"
    return r


def _get_rw_functions_c(reg_name, reg_base, nwords, busword, alignment, read_only, with_access_functions):
    r = ""

    r += "#define CSR_"+reg_name.upper()+"_ADDR "+hex(reg_base)+"L\n"
    r += "#define CSR_"+reg_name.upper()+"_SIZE "+str(nwords)+"\n"

    size = nwords*busword
    if size > 64:
        return r
    elif size > 32:
        ctype = "unsigned long long int"
    elif size > 16:
        ctype = "unsigned int"
    elif size > 8:
        ctype = "unsigned short int"
    else:
        ctype = "unsigned char"

    if with_access_functions:
        r += "static inline "+ctype+" "+reg_name+"_read(void) {\n"
        if size > 1:
            r += "\t"+ctype+" r = csr_readl("+hex(reg_base)+"L);\n"
            for byte in range(1, nwords):
                r += "\tr <<= "+str(busword)+";\n\tr |= csr_readl("+hex(reg_base+alignment//8*byte)+"L);\n"
            r += "\treturn r;\n}\n"
        else:
            r += "\treturn csr_readl("+hex(reg_base)+"L);\n}\n"

        if not read_only:
            r += "static inline void "+reg_name+"_write("+ctype+" value) {\n"
            for word in range(nwords):
                shift = (nwords-word-1)*busword
                if shift:
                    value_shifted = "value >> "+str(shift)
                else:
                    value_shifted = "value"
                r += "\tcsr_writel("+value_shifted+", "+hex(reg_base+alignment//8*word)+"L);\n"
            r += "}\n"
    return r


def get_csr_header(regions, constants, with_access_functions=True, with_shadow_base=True, shadow_base=0x80000000):
    alignment = get_constant("CONFIG_CSR_ALIGNMENT", constants)
    r = generated_banner("//")
    r += "#ifndef __GENERATED_CSR_H\n#define __GENERATED_CSR_H\n"
    if with_access_functions:
        r += "#include <stdint.h>\n"
        r += "#ifdef CSR_ACCESSORS_DEFINED\n"
        r += "extern void csr_writeb(uint8_t value, unsigned long addr);\n"
        r += "extern uint8_t csr_readb(unsigned long addr);\n"
        r += "extern void csr_writew(uint16_t value, unsigned long addr);\n"
        r += "extern uint16_t csr_readw(unsigned long addr);\n"
        r += "extern void csr_writel(uint32_t value, unsigned long addr);\n"
        r += "extern uint32_t csr_readl(unsigned long addr);\n"
        r += "#else /* ! CSR_ACCESSORS_DEFINED */\n"
        r += "#include <hw/common.h>\n"
        r += "#endif /* ! CSR_ACCESSORS_DEFINED */\n"
    for name, origin, busword, obj in regions:
        if not with_shadow_base:
            origin &= (~shadow_base)
        r += "\n/* "+name+" */\n"
        r += "#define CSR_"+name.upper()+"_BASE "+hex(origin)+"L\n"
        if not isinstance(obj, Memory):
            for csr in obj:
                nr = (csr.size + busword - 1)//busword
                r += _get_rw_functions_c(name + "_" + csr.name, origin, nr, busword, alignment,
                    isinstance(csr, CSRStatus), with_access_functions)
                origin += alignment//8*nr
                if hasattr(csr, "fields"):
                    for field in csr.fields.fields:
                        r += "#define CSR_"+name.upper()+"_"+csr.name.upper()+"_"+field.name.upper()+"_OFFSET "+str(field.offset)+"\n"
                        r += "#define CSR_"+name.upper()+"_"+csr.name.upper()+"_"+field.name.upper()+"_SIZE "+str(field.size)+"\n"

    r += "\n/* constants */\n"
    for name, value in constants:
        if value is None:
            r += "#define "+name+"\n"
            continue
        if isinstance(value, str):
            value = "\"" + value + "\""
            ctype = "const char *"
        else:
            value = str(value)
            ctype = "int"
        r += "#define "+name+" "+value+"\n"
        if with_access_functions:
            r += "static inline "+ctype+" "+name.lower()+"_read(void) {\n"
            r += "\treturn "+value+";\n}\n"

    r += "\n#endif\n"
    return r

def get_csr_json(csr_regions=[], constants=[], memory_regions=[]):
    alignment = 32 if constants is None else get_constant("CONFIG_CSR_ALIGNMENT", constants)

    d = {
        "csr_bases":     {},
        "csr_registers": {},
        "constants":     {},
        "memories":      {},
    }

    for name, origin, busword, obj in csr_regions:
        d["csr_bases"][name] = origin
        if not isinstance(obj, Memory):
            for csr in obj:
                size = (csr.size + busword - 1)//busword
                d["csr_registers"][name + "_" + csr.name] = {
                    "addr": origin,
                    "size": size,
                    "type": "ro" if isinstance(csr, CSRStatus) else "rw"
                }
                origin += alignment//8*size

    for name, value in constants:
        d["constants"][name.lower()] = value.lower() if isinstance(value, str) else value

    for name, origin, length in memory_regions:
        d["memories"][name.lower()] = {
            "base": origin,
            "size": length
        }

    return json.dumps(d, indent=4)

def get_csr_csv(csr_regions=[], constants=[], memory_regions=[]):
    d = json.loads(get_csr_json(csr_regions, constants, memory_regions))
    r = generated_banner("#")
    for name, value in d["csr_bases"].items():
        r += "csr_base,{},0x{:08x},,\n".format(name, value)
    for name in d["csr_registers"].keys():
        r += "csr_register,{},0x{:08x},{},{}\n".format(name,
            d["csr_registers"][name]["addr"],
            d["csr_registers"][name]["size"],
            d["csr_registers"][name]["type"])
    for name, value in d["constants"].items():
        r += "constant,{},{},,\n".format(name, value)
    for name in d["memories"].keys():
        r += "memory_region,{},0x{:08x},{:d},\n".format(name,
            d["memories"][name]["base"],
            d["memories"][name]["size"])
    return r

def get_git_header():
    from litex.build.tools import get_migen_git_revision, get_litex_git_revision
    r = generated_banner("//")
    r += "#ifndef __GENERATED_GIT_H\n#define __GENERATED_GIT_H\n\n"
    r += "#define MIGEN_GIT_SHA1 \"{}\"\n".format(get_migen_git_revision())
    r += "#define LITEX_GIT_SHA1 \"{}\"\n".format(get_litex_git_revision())
    r += "#endif\n"
    return r
