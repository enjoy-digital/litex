#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import subprocess
from pathlib import Path

# Host harness for the size argument of the BIOS sdram_test command (bios/cmds/cmd_litedram.c).


def test_sdram_test_size_argument(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "csr.h").write_text("#define CSR_SDRAM_BASE 1\n")
    (generated / "soc.h").write_text("")
    (generated / "mem.h").write_text(
        "#define MAIN_RAM_BASE 0x40000000UL\n"
        "#define MAIN_RAM_SIZE 0x20000000UL\n"
    )
    source = tmp_path / "sdram_test.c"
    source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#define MAIN_RAM_BASE_VA MAIN_RAM_BASE
#include <bios/cmds/cmd_litedram.c>

static unsigned int *test_addr;
static unsigned long test_size;
static unsigned int  test_count;

int memtest(unsigned int *addr, unsigned long maxsize)
{
    test_addr = addr;
    test_size = maxsize;
    test_count++;
    return 1;
}
int sdram_init(void) { return 1; }

static void run(int nb_params, char *param)
{
    char *params[] = {param};
    test_size = 0;
    sdram_test_handler(nb_params, params);
}

int main(void)
{
    /* No argument: 1/32 of main_ram, as before. */
    run(0, NULL);
    assert(test_count == 1 && test_size == MAIN_RAM_SIZE/32);
    assert(test_addr == (unsigned int *)MAIN_RAM_BASE);

    /* Size in bytes. */
    run(1, "0x100000");
    assert(test_count == 2 && test_size == 0x100000);
    run(1, "4096");
    assert(test_count == 3 && test_size == 4096);

    /* Full main_ram, larger sizes limited to it. */
    run(1, "0x20000000");
    assert(test_count == 4 && test_size == MAIN_RAM_SIZE);
    run(1, "0x80000000");
    assert(test_count == 5 && test_size == MAIN_RAM_SIZE);

    /* Invalid sizes: no test. */
    run(1, "full");
    run(1, "0x1000k");
    run(1, "0");
    run(1, "");
    assert(test_count == 5);
    return 0;
}
''')
    binary = tmp_path / "sdram_test"
    subprocess.check_call([
        "gcc", "-std=gnu99", "-Wall", "-Werror", "-Wno-unused-function",
        "-DBIOS_CONSOLE_DISABLE", "-ffunction-sections", "-fdata-sections",
        f"-I{tmp_path}", f"-I{repo}/litex/soc/software", str(source),
        "-Wl,--gc-sections", "-o", str(binary),
    ])
    subprocess.check_call([str(binary)])
