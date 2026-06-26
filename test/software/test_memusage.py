#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import textwrap

from litex.soc.software import memusage


def write_regions(path, sram_size=0x1000):
    path.write_text(textwrap.dedent(f"""
        MEMORY {{
            rom  : ORIGIN = 0x00000000, LENGTH = 0x00010000
            sram : ORIGIN = 0x10000000, LENGTH = 0x{sram_size:08x}
        }}
    """))


def section(name, addr, size, flags="A", section_type="PROGBITS"):
    return {
        "name" : name,
        "type" : section_type,
        "addr" : addr,
        "size" : size,
        "flags": flags,
    }


def test_memusage_reports_data_bss_and_stack_margin(tmp_path, capsys, monkeypatch):
    regions = tmp_path / "regions.ld"
    write_regions(regions)

    sections = [
        section(".text",         0x00000000, 0x1000, "AX"),
        section(".rodata",       0x00001000, 0x0100, "A"),
        section(".commands",     0x00001100, 0x0080, "A"),
        section(".init",         0x00001180, 0x0040, "A"),
        section(".boot_methods", 0x000011c0, 0x0040, "A"),
        section(".data",         0x10000000, 0x0300, "WA"),
        section(".bss",          0x10000380, 0x0200, "WA", "NOBITS"),
    ]
    monkeypatch.setattr(memusage, "parse_sections", lambda bios, triple: sections)

    memusage.print_usage("bios.elf", str(regions), "riscv64-unknown-elf")

    output = capsys.readouterr().out
    assert "ROM usage: 5.25KiB" in output
    assert "SRAM usage: 1.25KiB" in output
    assert "  .data: 0.75KiB" in output
    assert "  .bss: 0.50KiB" in output
    assert "  stack margin: 2.62KiB" in output
    assert "WARNING" not in output


def test_memusage_passes_requested_stack_margin(tmp_path, capsys, monkeypatch):
    regions = tmp_path / "regions.ld"
    write_regions(regions)

    sections = [
        section(".text", 0x00000000, 0x1000, "AX"),
        section(".data", 0x10000000, 0x0300, "WA"),
        section(".bss",  0x10000380, 0x0200, "WA", "NOBITS"),
    ]
    monkeypatch.setattr(memusage, "parse_sections", lambda bios, triple: sections)

    result = memusage.print_usage("bios.elf", str(regions), "riscv64-unknown-elf", fail_stack_margin=0x800)

    output = capsys.readouterr().out
    assert result == 0
    assert "  stack margin: 2.62KiB" in output
    assert "ERROR" not in output


def test_memusage_warns_on_low_implicit_stack_margin(tmp_path, capsys, monkeypatch):
    regions = tmp_path / "regions.ld"
    write_regions(regions, sram_size=0x800)

    sections = [
        section(".text", 0x00000000, 0x1000, "AX"),
        section(".data", 0x10000000, 0x0400, "WA"),
        section(".bss",  0x10000400, 0x0100, "WA", "NOBITS"),
    ]
    monkeypatch.setattr(memusage, "parse_sections", lambda bios, triple: sections)

    memusage.print_usage("bios.elf", str(regions), "riscv64-unknown-elf")

    output = capsys.readouterr().out
    assert "  stack margin: 0.75KiB" in output
    assert "WARNING: SRAM stack margin is very small" in output


def test_memusage_fails_on_requested_stack_margin(tmp_path, capsys, monkeypatch):
    regions = tmp_path / "regions.ld"
    write_regions(regions, sram_size=0x800)

    sections = [
        section(".text", 0x00000000, 0x1000, "AX"),
        section(".data", 0x10000000, 0x0400, "WA"),
        section(".bss",  0x10000400, 0x0100, "WA", "NOBITS"),
    ]
    monkeypatch.setattr(memusage, "parse_sections", lambda bios, triple: sections)

    result = memusage.print_usage("bios.elf", str(regions), "riscv64-unknown-elf", fail_stack_margin=0x400)

    output = capsys.readouterr().out
    assert result == 1
    assert "  stack margin: 0.75KiB" in output
    assert "ERROR: SRAM stack margin is below required minimum (0.75KiB < 1.00KiB)." in output


def test_memusage_reports_explicit_stack_section(tmp_path, capsys, monkeypatch):
    regions = tmp_path / "regions.ld"
    write_regions(regions)

    sections = [
        section(".text",  0x00000000, 0x1000, "AX"),
        section(".data",  0x10000000, 0x0200, "WA"),
        section(".bss",   0x10000200, 0x0200, "WA", "NOBITS"),
        section(".stack", 0x10000400, 0x0400, "WA", "NOBITS"),
    ]
    monkeypatch.setattr(memusage, "parse_sections", lambda bios, triple: sections)

    memusage.print_usage("bios.elf", str(regions), "riscv64-unknown-elf")

    output = capsys.readouterr().out
    assert "  .stack: 1.00KiB" in output
    assert "  stack margin" not in output
    assert "WARNING" not in output


def test_memusage_fails_on_requested_explicit_stack_size(tmp_path, capsys, monkeypatch):
    regions = tmp_path / "regions.ld"
    write_regions(regions)

    sections = [
        section(".text",  0x00000000, 0x1000, "AX"),
        section(".data",  0x10000000, 0x0200, "WA"),
        section(".bss",   0x10000200, 0x0200, "WA", "NOBITS"),
        section(".stack", 0x10000400, 0x0400, "WA", "NOBITS"),
    ]
    monkeypatch.setattr(memusage, "parse_sections", lambda bios, triple: sections)

    result = memusage.print_usage("bios.elf", str(regions), "riscv64-unknown-elf", fail_stack_margin=0x800)

    output = capsys.readouterr().out
    assert result == 1
    assert "  .stack: 1.00KiB" in output
    assert "ERROR: SRAM .stack is below required minimum (1.00KiB < 2.00KiB)." in output
