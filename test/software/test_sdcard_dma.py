# SPDX-License-Identifier: BSD-2-Clause

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("mode", ["enabled", "disabled", "other_cpu", "noncoherent"])
def test_sdcard_receive_dma(tmp_path, mode):
    repo = Path(__file__).resolve().parents[2]
    generated = tmp_path / "generated"
    generated.mkdir()
    for name in ["csr", "mem", "soc"]:
        (generated / f"{name}.h").write_text("")
    (tmp_path / "system.h").write_text("")
    source = tmp_path / "sdcard.c"
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
static uint8_t ram[4096] __attribute__((aligned(64)));
#define MAIN_RAM_BASE ((uintptr_t)ram)
#define MAIN_RAM_SIZE sizeof(ram)
#ifndef TEST_OTHER_CPU
#define CONFIG_CPU_TYPE_VEXIIRISCV 1
#endif
#ifndef TEST_NONCOHERENT
#define CONFIG_CPU_HAS_DMA_BUS 1
#endif
#define CONFIG_CLOCK_FREQUENCY 100000000
#define CSR_SDCARD_BASE 1
#define CSR_SDCARD_BLOCK2MEM_DMA_BASE_ADDR 1
#define CSR_SDCARD_CORE_CMD_RESPONSE_ADDR 1
#define SDCARD_DMA_TIMEOUT_US 4
#define min(a, b) ((a) < (b) ? (a) : (b))
#define max(a, b) ((a) > (b) ? (a) : (b))
static uintptr_t dma_base, bases[32];
static unsigned int dma_length, dma_enabled, command, argument;
static unsigned int commands[32], arguments[32], lengths[32], transfers;
static unsigned int cmd_error, data_error, dma_stuck, done_reads, switch_bad;
static void busy_wait(unsigned int v) { (void)v; }
static void busy_wait_us(unsigned int v) { (void)v; }
static void flush_cpu_dcache(void) {}
static void flush_l2_cache(void) {}
static void sdcard_phy_clocker_divider_write(unsigned int v) { (void)v; }
static void sdcard_phy_init_initialize_write(unsigned int v) { (void)v; }
static void sdcard_phy_settings_write(unsigned int v) { (void)v; }
static void sdcard_core_block_length_write(unsigned int v) { (void)v; }
static void sdcard_core_block_count_write(unsigned int v) { (void)v; }
static void sdcard_core_cmd_argument_write(unsigned int v) { argument = v; }
static void sdcard_core_cmd_command_write(unsigned int v) { command = v >> 8; }
static void sdcard_block2mem_dma_base_write(uint64_t v) { dma_base = v; }
static void sdcard_block2mem_dma_length_write(unsigned int v) { dma_length = v; }
static void sdcard_block2mem_dma_enable_write(unsigned int v) { dma_enabled = v; }
static void sdcard_core_cmd_send_write(unsigned int v)
{
    (void)v;
    if (command == 6 || command == 51 || command == 17 || command == 18) {
        assert(dma_enabled && transfers < 32);
        bases[transfers] = dma_base;
        lengths[transfers] = dma_length;
        commands[transfers] = command;
        arguments[transfers++] = argument;
        done_reads = 0;
    }
}
static unsigned int sdcard_core_cmd_event_read(void) { return 1 | cmd_error; }
static unsigned int sdcard_core_data_event_read(void) { return 1 | data_error; }
static unsigned int sdcard_block2mem_dma_done_read(void)
{
    if (dma_stuck || ++done_reads < 3) return 0;
    uint8_t *dst = (uint8_t *)dma_base;
    for (unsigned int i = 0; i < dma_length; i++)
        dst[i] = command == 6 ? 0 : (uint8_t)(argument + i / 512 + i);
    if (command == 6) dst[16] = switch_bad ? 0 : 1;
    return 1;
}
static void csr_rd_buf_uint32(unsigned int addr, uint32_t *buf, unsigned int n)
{
    (void)addr;
    memset(buf, 0, n * sizeof(*buf));
}
#include <liblitesdcard/sdcard.c>
DISKOPS *FfDiskOps;

static void reset(void)
{
    transfers = cmd_error = data_error = dma_stuck = switch_bad = 0;
}
static void check_blocks(const uint8_t *buf, unsigned int first, unsigned int count)
{
    for (unsigned int i = 0; i < 512 * count; i++)
        assert(buf[i] == (uint8_t)(first + i / 512 + i));
}
int main(void)
{
    assert(SDCARD_DMA_BOUNCE == EXPECT_BOUNCE);
    struct {
        uint8_t before[64];
        uint8_t data[1024];
        uint8_t after[64];
    } buffer;
    uint32_t scr[2];
    memset(&buffer, 0xa5, sizeof(buffer));

    assert(sdcard_switch(SD_SWITCH_SWITCH, 0, 1) == SD_OK);
    assert(!dma_enabled && dma_length == 64);
#if SDCARD_DMA_BOUNCE
    assert(dma_base == SDCARD_DMA_BUFFER_BASE);
    assert(!(dma_base & 63));
#else
    assert(dma_base == (uintptr_t)sdcard_switch_status);
#endif
    switch_bad = 1;
    assert(sdcard_switch(SD_SWITCH_SWITCH, 0, 1) == SD_SWITCHERROR);
    reset();
    assert(sdcard_get_scr(scr, 1));
    for (unsigned int i = 0; i < sizeof(scr); i++) assert(((uint8_t *)scr)[i] == i);
    assert(!dma_enabled && dma_length == 8);
#if SDCARD_DMA_BOUNCE
    assert(dma_base == SDCARD_DMA_BUFFER_BASE);
#else
    assert(dma_base == (uintptr_t)scr);
#endif

    reset();
    support_cmd23 = 1;
    assert(sdcard_read(7, 2, buffer.data) == SD_OK);
    check_blocks(buffer.data, 7, 2);
    for (unsigned int i = 0; i < 64; i++) {
        assert(buffer.before[i] == 0xa5 && buffer.after[i] == 0xa5);
    }
#if SDCARD_DMA_BOUNCE
    assert(transfers == 2);
    for (unsigned int i = 0; i < 2; i++) {
        assert(bases[i] == SDCARD_DMA_BUFFER_BASE);
        assert(lengths[i] == 512 && commands[i] == 17 && arguments[i] == 7 + i);
    }
#else
    assert(transfers == 1 && bases[0] == (uintptr_t)buffer.data);
#endif
    reset();
    assert(sdcard_read(9, 2, ram) == SD_OK);
    check_blocks(ram, 9, 2);
    assert(transfers == 1 && bases[0] == (uintptr_t)ram);
    assert(commands[0] == 18 && lengths[0] == 1024);

#if SDCARD_DMA_BOUNCE
    reset();
    assert(sdcard_read(11, 1, ram + 1) == SD_OK);
    check_blocks(ram + 1, 11, 1);
    assert(bases[0] == SDCARD_DMA_BUFFER_BASE);
    assert(!sdcard_dma_direct(ram, UINT32_MAX));
    assert(!sdcard_dma_direct((uint8_t *)SDCARD_DMA_BUFFER_BASE, 1));
#endif
    reset();
    sdcard_ccs = 0;
    assert(sdcard_read(3, 2, buffer.data) == SD_OK);
    assert(arguments[0] == 3 * 512);
#if SDCARD_DMA_BOUNCE
    assert(arguments[1] == 4 * 512);
#endif
    sdcard_ccs = 1;

    for (unsigned int failure = 0; failure < 3; failure++) {
        reset();
        memset(buffer.data, 0xa5, sizeof(buffer.data));
        cmd_error = failure == 0 ? 4 : 0;
        data_error = failure == 1 ? 8 : 0;
        dma_stuck = failure == 2;
        assert(sdcard_read(7, 1, buffer.data) != SD_OK);
        assert(!dma_enabled);
        for (unsigned int i = 0; i < sizeof(buffer.data); i++) assert(buffer.data[i] == 0xa5);
        assert(!sdcard_get_scr(scr, 1));
        assert(!dma_enabled);
        assert(sdcard_switch(SD_SWITCH_SWITCH, 0, 1) != SD_OK);
        assert(!dma_enabled);
    }
    reset();
    assert(sdcard_read(0, 0, buffer.data) == SD_OK && transfers == 0);
    return 0;
}
''')
    binary = tmp_path / "sdcard"
    flags = {
        "enabled": ["-DEXPECT_BOUNCE=1"],
        "disabled": ["-DEXPECT_BOUNCE=0", "-DSDCARD_DMA_BOUNCE=0"],
        "other_cpu": ["-DEXPECT_BOUNCE=0", "-DTEST_OTHER_CPU"],
        "noncoherent": ["-DEXPECT_BOUNCE=0", "-DTEST_NONCOHERENT"],
    }[mode]
    subprocess.check_call([
        "gcc", "-std=gnu99", "-O2", "-Wall", "-Werror", "-Wno-unused-function",
        *flags,
        f"-I{tmp_path}", f"-I{repo}/litex/soc/software",
        str(source), "-o", str(binary),
    ])
    subprocess.check_call([str(binary)], timeout=10)
