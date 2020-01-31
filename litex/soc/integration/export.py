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

from litex.soc.interconnect.csr import CSRStatus, CSRStorage

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

def _get_rw_functions_c(reg_name, reg_base, nwords, busword, alignment, read_only, with_access_functions):
    r = ""

    addr_str = "CSR_{}_ADDR".format(reg_name.upper())
    size_str = "CSR_{}_SIZE".format(reg_name.upper())
    r += "#define {} {}L\n".format(addr_str, hex(reg_base))
    r += "#define {} {}\n".format(size_str, nwords)

    size = nwords*busword//8
    if size > 8:
        # downstream should select appropriate `csr_[rd|wr]_buf_uintX()` pair!
        return r
    elif size > 4:
        ctype = "uint64_t"
    elif size > 2:
        ctype = "uint32_t"
    elif size > 1:
        ctype = "uint16_t"
    else:
        ctype = "uint8_t"

    stride = alignment//8;
    if with_access_functions:
        r += "static inline {} {}_read(void) {{\n".format(ctype, reg_name)
        if nwords > 1:
            r += "\t{} r = csr_read_simple({}L);\n".format(ctype, hex(reg_base))
            for sub in range(1, nwords):
                r += "\tr <<= {};\n".format(busword)
                r += "\tr |= csr_read_simple({}L);\n".format(hex(reg_base+sub*stride))
            r += "\treturn r;\n}\n"
        else:
            r += "\treturn csr_read_simple({}L);\n}}\n".format(hex(reg_base))

        if not read_only:
            r += "static inline void {}_write({} v) {{\n".format(reg_name, ctype)
            for sub in range(nwords):
                shift = (nwords-sub-1)*busword
                if shift:
                    v_shift = "v >> {}".format(shift)
                else:
                    v_shift = "v"
                r += "\tcsr_write_simple({}, {}L);\n".format(v_shift, hex(reg_base+sub*stride))
            r += "}\n"
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
        r += "extern void csr_write_simple(unsigned long v, unsigned long a);\n"
        r += "extern unsigned long csr_read_simple(unsigned long a);\n"
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
                r += _get_rw_functions_c(name + "_" + csr.name, origin, nr, region.busword, alignment,
                    isinstance(csr, CSRStatus), with_access_functions)
                origin += alignment//8*nr
                if hasattr(csr, "fields"):
                    for field in csr.fields.fields:
                        r += "#define CSR_"+name.upper()+"_"+csr.name.upper()+"_"+field.name.upper()+"_OFFSET "+str(field.offset)+"\n"
                        r += "#define CSR_"+name.upper()+"_"+csr.name.upper()+"_"+field.name.upper()+"_SIZE "+str(field.size)+"\n"

    r += "\n#endif\n"
    return r


# SVD Export ---------------------------------------------------------------------------------------

def get_csr_svd(csr_regions={}, constants={}, mem_regions={}):
    alignment_bits = constants.get("CONFIG_CSR_ALIGNMENT", 32)

    r = """<?xml version="1.0" encoding="utf-8"?>
<device schemaVersion="1.1" xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" xs:noNamespaceSchemaLocation="CMSIS-SVD.xsd" >
    <name>LiteX SoC</name>
    <addressUnitBits>8</addressUnitBits>
    <width>32</width>
    <peripherals>
"""
    for name, region in csr_regions.items():
        busword_bits = region.busword
        if not isinstance(region.obj, Memory):
            r += 8 * " " + "<peripheral>\n"
            r += 12 * " " + "<name>%s</name>\n" % name
            r += 12 * " " + "<baseAddress>0x%08x</baseAddress>\n" % region.origin
            r += 12 * " " + "<registers>\n"
            csr_offset = 0
            for csr in region.obj:
                csr_size_bits = csr.size
                nwords = (csr_size_bits + busword_bits - 1) // busword_bits
                if nwords > 1 and alignment_bits != busword_bits:
                    raise ValueError("Multi-word registers are not supported")
                r += 16 * " " + "<register>\n"
                r += 20 * " " + "<name>%s</name>\n" % csr.name
                r += 20 * " " + "<addressOffset>0x%02x</addressOffset>\n" % csr_offset
                r += 20 * " " + "<size>%d</size>\n" % (nwords * busword_bits)
                access = "read-only" if isinstance(csr, CSRStatus) else "read-write"
                r += 20 * " " + "<access>%s</access>\n" % access
                reset_value = 0
                if isinstance(csr, CSRStatus):
                    reset_value = csr.status.reset
                if isinstance(csr, CSRStorage):
                    reset_value = csr.storage.reset
                if isinstance(reset_value, Constant):
                    reset_value = reset_value.value
                if not isinstance(reset_value, int):
                    raise TypeError("Unsupported reset value type")
                r += 20 * " " + "<resetValue>0x%x</resetValue>\n" % reset_value
                if hasattr(csr, "fields"):
                    r += 20 * " " + "<fields>\n"
                    for field in csr.fields.fields:
                        r += 24 * " " + "<field>\n"
                        r += 28 * " " + "<name>%s</name>\n" % field.name
                        r += 28 * " " + "<bitOffset>%d</bitOffset>\n" % field.offset
                        r += 28 * " " + "<bitWidth>%d</bitWidth>\n" % field.size
                        r += 24 * " " + "</field>\n"
                    r += 20 * " " + "</fields>\n"
                r += 16 * " " + "</register>\n"
                csr_offset += alignment_bits//8 * nwords
            r += 12 * " " + "</registers>\n"
            r += 8 * " " + "</peripheral>\n"


    r += """
    </peripherals>
</device>
"""
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
