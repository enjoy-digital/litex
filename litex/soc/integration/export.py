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

# CPU files ----------------------------------------------------------------------------------------

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
    for name, region in regions.items():
        r += "\t{} : ORIGIN = 0x{:08x}, LENGTH = 0x{:08x}\n".format(name, region.origin, region.length)
    r += "}\n"
    return r


# C Export -----------------------------------------------------------------------------------------

def get_git_header():
    from litex.build.tools import get_migen_git_revision, get_litex_git_revision
    r = generated_banner("//")
    r += "#ifndef __GENERATED_GIT_H\n#define __GENERATED_GIT_H\n\n"
    r += "#define MIGEN_GIT_SHA1 \"{}\"\n".format(get_migen_git_revision())
    r += "#define LITEX_GIT_SHA1 \"{}\"\n".format(get_litex_git_revision())
    r += "#endif\n"
    return r

def get_mem_header(regions):
    r = generated_banner("//")
    r += "#ifndef __GENERATED_MEM_H\n#define __GENERATED_MEM_H\n\n"
    for name, region in regions.items():
        r += "#define {name}_BASE 0x{base:08x}L\n#define {name}_SIZE 0x{size:08x}\n\n".format(
            name=name.upper(), base=region.origin, size=region.length)
    r += "#endif\n"
    return r

def get_soc_header(constants, with_access_functions=True):
    r = generated_banner("//")
    r += "#ifndef __GENERATED_SOC_H\n#define __GENERATED_SOC_H\n"
    for name, value in constants.items():
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

def _get_rw_functions_c(reg_name, reg_base, nwords, busword, read_only, with_access_functions):
    r = ""

    addr_str = "CSR_{}_ADDR".format(reg_name.upper())
    size_str = "CSR_{}_SIZE".format(reg_name.upper())
    r += "#define {} {}L\n".format(addr_str, hex(reg_base))
    r += "#define {} {}\n".format(size_str, nwords)

    size = nwords*busword//8
    if size > 8:
        # FIXME: maybe implement some "memcpy-like" semantics for larger blobs?
        return r
    elif size > 4:
        ctype = "uint64_t"
    elif size > 2:
        ctype = "uint32_t"
    elif size > 1:
        ctype = "uint16_t"
    else:
        ctype = "uint8_t"

    if with_access_functions:
        r += "static inline {} {}_read(void) {{\n".format(ctype, reg_name)
        r += "\treturn _csr_rd((unsigned long *){}, {});\n}}\n".format(addr_str, size)

        if not read_only:
            r += "static inline void {}_write({} v) {{\n".format(reg_name, ctype)
            r += "\t_csr_wr((unsigned long *){}, v, {});\n}}\n".format(addr_str, size)
    return r


def get_csr_header(regions, constants, with_access_functions=True):
    alignment = constants.get("CONFIG_CSR_ALIGNMENT", 32)
    r = generated_banner("//")
    if with_access_functions: # FIXME
        r += "#include <generated/soc.h>\n"
    r += "#ifndef __GENERATED_CSR_H\n#define __GENERATED_CSR_H\n"
    if with_access_functions:
        r += "#include <stdint.h>\n"
        r += "#ifdef CSR_ACCESSORS_DEFINED\n"
        r += "extern void csr_wr_uint8(uint8_t v, unsigned long a);\n"
        r += "extern void csr_wr_uint16(uint16_t v, unsigned long a);\n"
        r += "extern void csr_wr_uint32(uint32_t v, unsigned long a);\n"
        r += "extern void csr_wr_uint64(uint64_t v, unsigned long a);\n"
        r += "extern uint8_t csr_rd_uint8(unsigned long a);\n"
        r += "extern uint16_t csr_rd_uint16(unsigned long a);\n"
        r += "extern uint32_t csr_rd_uint32(unsigned long a);\n"
        r += "extern uint64_t csr_rd_uint64(unsigned long a);\n"
        r += "#else /* ! CSR_ACCESSORS_DEFINED */\n"
        r += "#include <hw/common.h>\n"
        r += "#endif /* ! CSR_ACCESSORS_DEFINED */\n"
    for name, region in regions.items():
        origin = region.origin
        r += "\n/* "+name+" */\n"
        r += "#define CSR_"+name.upper()+"_BASE "+hex(origin)+"L\n"
        if not isinstance(region.obj, Memory):
            for csr in region.obj:
                nr = (csr.size + region.busword - 1)//region.busword
                r += _get_rw_functions_c(name + "_" + csr.name, origin, nr, region.busword,
                    isinstance(csr, CSRStatus), with_access_functions)
                origin += alignment//8*nr
                if hasattr(csr, "fields"):
                    for field in csr.fields.fields:
                        r += "#define CSR_"+name.upper()+"_"+csr.name.upper()+"_"+field.name.upper()+"_OFFSET "+str(field.offset)+"\n"
                        r += "#define CSR_"+name.upper()+"_"+csr.name.upper()+"_"+field.name.upper()+"_SIZE "+str(field.size)+"\n"

    r += "\n#endif\n"
    return r

# JSON Export --------------------------------------------------------------------------------------

def get_csr_json(csr_regions={}, constants={}, mem_regions={}):
    alignment = constants.get("CONFIG_CSR_ALIGNMENT", 32)

    d = {
        "csr_bases":     {},
        "csr_registers": {},
        "constants":     {},
        "memories":      {},
    }

    for name, region in csr_regions.items():
        d["csr_bases"][name] = region.origin
        region_origin = region.origin
        if not isinstance(region.obj, Memory):
            for csr in region.obj:
                size = (csr.size + region.busword - 1)//region.busword
                d["csr_registers"][name + "_" + csr.name] = {
                    "addr": region_origin,
                    "size": size,
                    "type": "ro" if isinstance(csr, CSRStatus) else "rw"
                }
                region_origin += alignment//8*size

    for name, value in constants.items():
        d["constants"][name.lower()] = value.lower() if isinstance(value, str) else value

    for name, region in mem_regions.items():
        d["memories"][name.lower()] = {
            "base": region.origin,
            "size": region.length,
            "type": region.type,
        }

    return json.dumps(d, indent=4)


# CSV Export --------------------------------------------------------------------------------------

def get_csr_csv(csr_regions={}, constants={}, mem_regions={}):
    d = json.loads(get_csr_json(csr_regions, constants, mem_regions))
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
        r += "memory_region,{},0x{:08x},{:d},{:s}\n".format(name,
            d["memories"][name]["base"],
            d["memories"][name]["size"],
            d["memories"][name]["type"],
            )
    return r
