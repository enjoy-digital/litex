# SPDX-License-Identifier: BSD-2-Clause

import subprocess
from pathlib import Path


def test_checked_unsigned_arguments(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    source = tmp_path / "parse.c"
    source.write_text(r'''
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <libbase/parse.h>

int main(void)
{
    unsigned long value = 123;
    unsigned int small = 42;
    char boundary[64];
    const char *invalid[] = {"", "-1", "+1", " 1", "1 ", "0x", "08", "0xg", "1x"};

    for (unsigned int i = 0; i < sizeof(invalid) / sizeof(*invalid); i++) {
        assert(!parse_ulong(invalid[i], &value));
        assert(value == 123);
    }
    assert(parse_ulong("0", &value) && value == 0);
    assert(parse_ulong("077", &value) && value == 63);
    assert(parse_ulong("0xAbCd", &value) && value == 0xabcd);
    assert(parse_ulong("1234", &value) && value == 1234);
    snprintf(boundary, sizeof(boundary), "%lu", ULONG_MAX);
    assert(parse_ulong(boundary, &value) && value == ULONG_MAX);
    snprintf(boundary, sizeof(boundary), "0x%lx0", ULONG_MAX);
    assert(!parse_ulong(boundary, &value) && value == ULONG_MAX);
    snprintf(boundary, sizeof(boundary), "%u", UINT_MAX);
    assert(parse_uint(boundary, &small) && small == UINT_MAX);
    snprintf(boundary, sizeof(boundary), "0x%x0", UINT_MAX);
    assert(!parse_uint(boundary, &small) && small == UINT_MAX);
    return 0;
}
''')
    binary = tmp_path / "parse"
    subprocess.check_call([
        "gcc", "-std=gnu99", "-Wall", "-Wextra", "-Werror",
        f"-I{repo}/litex/soc/software", str(source),
        str(repo / "litex/soc/software/libbase/parse.c"), "-o", str(binary),
    ])
    subprocess.check_call([str(binary)])


def test_memory_and_flash_arguments(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    generated = tmp_path / "generated"
    generated.mkdir()
    for name in ["csr", "soc", "mem"]:
        (generated / f"{name}.h").write_text("")
    source = tmp_path / "commands.c"
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define BIOS_CONSOLE_DISABLE
#define CSR_SPIFLASH_MASTER_CS_ADDR 1
#define MEM_REGIONS ""
#include <bios/cmds/cmd_mem.c>
#include <bios/cmds/cmd_spiflash.c>

static uint8_t *flash_source;
static unsigned int flash_count;
int spiflash_write_stream(uint32_t offset, uint8_t *source, uint32_t count)
{
    assert(offset == 0);
    flash_source = source;
    flash_count++;
    return count;
}
int main(void)
{
    uint32_t memory[4] = {0};
    char address[32];
    char *write_args[] = {address, "0x12345678", "1", "4"};
    char *flash_args[] = {"0", address, "4"};
    snprintf(address, sizeof(address), "0x%lx", (unsigned long)memory);
    mem_write_handler(4, write_args);
    assert(memory[0] == 0x12345678 && memory[1] == 0);
    write_args[1] = "0x100000000";
    mem_write_handler(4, write_args);
    assert(memory[0] == 0x12345678);
    write_args[1] = "-1";
    mem_write_handler(4, write_args);
    assert(memory[0] == 0x12345678);
    flash_write_handler(3, flash_args);
    assert(flash_count == 1 && flash_source == (uint8_t *)memory);
    flash_args[2] = "0x100000000";
    flash_write_handler(3, flash_args);
    assert(flash_count == 1);
    return 0;
}
''')
    binary = tmp_path / "commands"
    subprocess.check_call([
        "gcc", "-std=gnu99", "-Wall", "-Werror", "-Wno-unused-function",
        "-ffunction-sections", "-fdata-sections", f"-I{tmp_path}",
        f"-I{repo}/litex/soc/software", str(source),
        str(repo / "litex/soc/software/libbase/parse.c"),
        "-Wl,--gc-sections", "-o", str(binary),
    ])
    subprocess.check_call([str(binary)])


def test_dispatch_help_and_completion(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    generated = tmp_path / "generated"
    generated.mkdir()
    for name in ["csr", "soc", "mem"]:
        (generated / f"{name}.h").write_text("")
    (tmp_path / "system.h").write_text(r'''
#pragma once
#include <stddef.h>
static inline void flush_cpu_dcache(void) {}
static inline void flush_l2_cache(void) {}
static inline void flush_cpu_dcache_range(void *p, size_t n) { (void)p; (void)n; }
''')
    linker = tmp_path / "commands.ld"
    linker.write_text('''
SECTIONS {
    .bios_cmd : {
        __bios_cmd_start = .;
        KEEP(*(.bios_cmd))
        __bios_cmd_end = .;
    }
} INSERT AFTER .rodata;
''')
    source = tmp_path / "dispatch.c"
    source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define MEM_REGIONS ""
#include <bios/helpers.c>
#include <bios/complete.c>
#include <bios/readline.c>
#include <bios/cmds/cmd_mem.c>
#include <bios/cmds/cmd_bios.c>

int memtest(unsigned int *addr, unsigned long size) { (void)addr; (void)size; return 1; }
void memspeed(unsigned int *addr, unsigned long size, bool ro, bool random)
{ (void)addr; (void)size; (void)ro; (void)random; }
unsigned int crc32(const unsigned char *buffer, unsigned int len)
{ (void)buffer; (void)len; return 0; }
int uart_read_nonblock(void) { return 1; }

int main(void)
{
    uint32_t memory = 0;
    char address[32], suffix[32];
    char *args[] = {address, "0x12345678", "1", "4", "extra"};
    char *help_args[] = {"mem_write"};
    char line[] = "cmd 1 2 3 4 5 6 7 8 9";
    char *command, *params[MAX_PARAM];
    snprintf(address, sizeof(address), "0x%lx", (unsigned long)&memory);
    assert(command_dispatcher("mem_write", 5, args));
    assert(memory == 0);
    assert(command_dispatcher("mem_write", 1, args));
    assert(memory == 0);
    assert(command_dispatcher("mem_write", 4, args));
    assert(memory == 0x12345678);
    assert(command_dispatcher("help", 1, help_args));
    assert(memory == 0x12345678);
    assert(!command_dispatcher("nonexistent", 0, NULL));
    assert(get_param(line, &command, params) == -1);
    complete("mem_wr", suffix, sizeof(suffix));
    assert(!strcmp(suffix, "ite"));
    complete("mem_wr", suffix, 2);
    assert(!strcmp(suffix, "i"));
    complete("mem_c", suffix, sizeof(suffix));
    assert(!strcmp(suffix, ""));
    assert(complete("mem_c", suffix, sizeof(suffix)) == 1);
    const char *input = "mem_wr\t\n";
    char line_buffer[CMD_LINE_BUFFER_SIZE];
    for (int i = strlen(input) - 1; i >= 0; i--) ungetc(input[i], stdin);
    hist_init();
    assert(readline(line_buffer, sizeof(line_buffer)) == 9);
    assert(!strcmp(line_buffer, "mem_write"));
    return 0;
}
''')
    binary = tmp_path / "dispatch"
    subprocess.check_call([
        "gcc", "-std=gnu99", "-Wall", "-Werror", "-ffunction-sections", "-fdata-sections",
        f"-I{tmp_path}", f"-I{repo}/litex/soc/software", str(source),
        str(repo / "litex/soc/software/libbase/parse.c"),
        f"-Wl,-T,{linker}", "-Wl,--gc-sections", "-o", str(binary),
    ])
    output = subprocess.check_output([str(binary)], text=True)
    assert "Usage: mem_write <address> <value> [count] [size]" in output
    assert "mem_write - Write address space" in output
    assert "Error: too many parameters" in output
