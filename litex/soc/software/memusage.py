#!/usr/bin/env python3

# This file is Copyright (c) 2020 Franck Jullien <franck.jullien@gmail.com>
# License: BSD

import subprocess
import argparse
import re

STACK_MARGIN_WARN_SIZE = 2*1024


def parse_regions(regions):
    parsed_regions = {}
    region_re = re.compile(
        r"\s*(?P<name>\w+)\s*:\s*"
        r"ORIGIN\s*=\s*(?P<origin>0x[0-9a-fA-F]+)\s*,\s*"
        r"LENGTH\s*=\s*(?P<size>0x[0-9a-fA-F]+)"
    )

    with open(regions, "r") as regfile:
        for line in regfile:
            match = region_re.match(line)
            if match is None:
                continue
            parsed_regions[match.group("name")] = {
                "origin" : int(match.group("origin"), 16),
                "size"   : int(match.group("size"),   16),
            }

    return parsed_regions


def parse_sections(bios, triple):
    readelf = triple + "-readelf"
    result  = subprocess.run([readelf, "-S", "-W", bios],
        stdout = subprocess.PIPE,
        check  = True,
    )
    lines   = result.stdout.decode("utf-8").split("\n")
    section_re = re.compile(
        r"\s*\[\s*\d+\]\s+"
        r"(?P<name>\S+)\s+"
        r"(?P<type>\S+)\s+"
        r"(?P<addr>[0-9a-fA-F]+)\s+"
        r"(?P<offset>[0-9a-fA-F]+)\s+"
        r"(?P<size>[0-9a-fA-F]+)\s+"
        r"(?P<entsize>[0-9a-fA-F]+)\s+"
        r"(?P<flags>\S*)"
    )

    sections = []
    for line in lines:
        match = section_re.match(line)
        if match is None:
            continue
        sections.append({
            "name" : match.group("name"),
            "type" : match.group("type"),
            "addr" : int(match.group("addr"), 16),
            "size" : int(match.group("size"), 16),
            "flags": match.group("flags"),
        })

    return sections


def section_in_region(section, region):
    if section["size"] == 0:
        return False

    start = section["addr"]
    end   = start + section["size"]

    return (start >= region["origin"]) and (end <= (region["origin"] + region["size"]))


def print_size(name, size, total=None):
    if total is None:
        print("{}: {:.2f}KiB".format(name, size/1024.0))
    else:
        print("{}: {:.2f}KiB \t({:.2f}%)".format(name, size/1024.0, size/total*100.0))


def print_usage(bios, regions, triple):
    linker_regions = parse_regions(regions)
    sections       = parse_sections(bios, triple)

    rom_region  = linker_regions.get("rom",  None)
    sram_region = linker_regions.get("sram", None)

    rom_usage   = 0
    sram_usage  = 0
    sram_end    = None
    stack_usage = 0
    data_usage  = 0
    bss_usage   = 0

    rom_sections = [
        ".text",
        ".rodata",
        ".commands",
        ".init",
        ".boot_methods",
        ".data",
    ]
    for section in sections:
        if section["name"] in rom_sections:
            rom_usage += section["size"]

        if (sram_region is not None) and section_in_region(section, sram_region):
            if "A" not in section["flags"]:
                continue
            section_end = section["addr"] + section["size"]
            is_stack    = section["name"] == ".stack"
            sram_usage += section["size"]
            if not is_stack:
                sram_end = max(sram_end or section_end, section_end)
            if section["name"] == ".data":
                data_usage += section["size"]
            if section["name"] == ".bss":
                bss_usage += section["size"]
            if is_stack:
                stack_usage += section["size"]

    print("")
    if rom_region is not None:
        print_size("ROM usage", rom_usage, rom_region["size"])
    else:
        print_size("ROM usage", rom_usage)

    if sram_region is not None:
        sram_size    = sram_region["size"]
        stack_margin = sram_region["origin"] + sram_size - (sram_end or sram_region["origin"])
        print_size("SRAM usage", sram_usage, sram_size)
        print_size("  .data", data_usage)
        print_size("  .bss", bss_usage)
        if stack_usage:
            print_size("  .stack", stack_usage)
        else:
            print_size("  stack margin", stack_margin)
            if stack_margin < STACK_MARGIN_WARN_SIZE:
                print("WARNING: SRAM stack margin is very small; consider increasing integrated SRAM")
                print("         or reducing BIOS features.")
    print("")

def main():
    parser = argparse.ArgumentParser(description="Print bios memory usage")
    parser.add_argument("input", help="input file")
    parser.add_argument("regions", help="regions definitions")
    parser.add_argument("triple", help="toolchain triple")
    args = parser.parse_args()
    print_usage(args.input, args.regions, args.triple)


if __name__ == "__main__":
    main()
