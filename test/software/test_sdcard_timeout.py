#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import textwrap

# Host harness for liblitesdcard/sdcard.c (SD mode, no DMA): the LiteSDCard core CSRs are replaced
# by a small card model that answers the commands of the initialization flow.

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

CSR_H = """
    #ifndef __GENERATED_CSR_H
    #define __GENERATED_CSR_H
    #include <stdint.h>

    #define CSR_SDCARD_BASE                   1
    #define CSR_SDCARD_CORE_CMD_RESPONSE_ADDR 1

    #define min(x, y) (((x) < (y)) ? (x) : (y))
    #define max(x, y) (((x) > (y)) ? (x) : (y))

    void     sdcard_phy_settings_write(uint32_t v);
    void     sdcard_phy_init_initialize_write(uint32_t v);
    void     sdcard_phy_clocker_divider_write(uint32_t v);
    void     sdcard_core_cmd_argument_write(uint32_t v);
    void     sdcard_core_cmd_command_write(uint32_t v);
    void     sdcard_core_cmd_send_write(uint32_t v);
    uint32_t sdcard_core_cmd_event_read(void);
    uint32_t sdcard_core_data_event_read(void);
    void     sdcard_core_block_length_write(uint32_t v);
    void     sdcard_core_block_count_write(uint32_t v);
    uint32_t sdcard_core_block_count_read(void);
    void     csr_rd_buf_uint32(unsigned long addr, uint32_t *buf, int cnt);

    #endif
"""

MODEL_C = """
    #include <stdbool.h>
    #include <stdint.h>
    #include <stdio.h>
    #include <string.h>

    #define CARD_NONE 0 /* No answer to any command.     */
    #define CARD_V2   1 /* SD ver2.00+ high capacity.     */
    #define CARD_V1   2 /* SD ver1.x standard capacity.   */

    static int      card_type = CARD_V2;
    static bool     cmd_stuck;          /* Command done bit never rises.  */
    static bool     data_stuck;         /* Data done bit never rises.     */
    static uint32_t cmd_argument;
    static uint32_t cmd_command;
    static uint32_t cmd_event;
    static uint32_t response[4];
    static uint32_t acmd41_args[8];
    static unsigned int acmd41_count;
    static unsigned int cmd_counts[64];
    static unsigned long event_reads;
    static bool app_cmd;

    /* CID as returned by the LiteSDCard emulator, CSD v2.0 test vector (r[0]..r[3]). */
    static const uint32_t cid[4] = {0x01014fa7, 0x10000000, 0x454c4c4f, 0x7f504348};
    static const uint32_t csd[4] = {0x0a4040ff, 0x3b370000, 0x5b5900c0, 0x400e0032};

    void sdcard_phy_settings_write(uint32_t v)        { (void)v; }
    void sdcard_phy_init_initialize_write(uint32_t v) { (void)v; }
    void sdcard_phy_clocker_divider_write(uint32_t v) { (void)v; }
    void sdcard_core_block_length_write(uint32_t v)   { (void)v; }
    static uint32_t block_count;
    void sdcard_core_block_count_write(uint32_t v)    { block_count = v; }
    uint32_t sdcard_core_block_count_read(void)       { return block_count; }
    void sdcard_core_cmd_argument_write(uint32_t v)   { cmd_argument = v; }
    void sdcard_core_cmd_command_write(uint32_t v)    { cmd_command  = v; }

    void busy_wait(unsigned int ms)     { (void)ms; }
    void busy_wait_us(unsigned int us)  { (void)us; }

    void csr_rd_buf_uint32(unsigned long addr, uint32_t *buf, int cnt)
    {
        (void)addr;
        for (int i = 0; i < cnt; i++)
            buf[i] = response[i];
    }

    static void answer(uint32_t r0)
    {
        memset(response, 0, sizeof(response));
        response[0] = r0;
        cmd_event   = 0x1;
    }

    void sdcard_core_cmd_send_write(uint32_t v)
    {
        unsigned int cmd = (cmd_command >> 8) & 0x3f;
        bool acmd = app_cmd;

        (void)v;
        app_cmd = false;
        cmd_counts[cmd]++;
        cmd_event = 0x1 | 0x4; /* Timeout by default. */
        if (card_type == CARD_NONE)
            return;
        if (acmd && cmd == 41) {
            uint32_t ocr = 0x80ff8000;
            if (acmd41_count < 8)
                acmd41_args[acmd41_count] = cmd_argument;
            acmd41_count++;
            if (card_type == CARD_V2 && (cmd_argument & 0x40000000))
                ocr |= 0x40000000;
            if (card_type == CARD_V2 && !(cmd_argument & 0x40000000))
                ocr &= ~0x80000000; /* High capacity card stays busy with HCS=0. */
            answer(ocr);
            return;
        }
        switch (cmd) {
        case 0:  cmd_event = 0x1; break;
        case 8:  if (card_type == CARD_V2) answer(0x1aa); break;
        case 55: answer(0x120); app_cmd = true; break;
        case 2:  memcpy(response, cid, sizeof(cid)); cmd_event = 0x1; break;
        case 9:  memcpy(response, csd, sizeof(csd)); cmd_event = 0x1; break;
        case 3:  answer(0x12340000); break;
        case 6: case 7: case 10: case 12: case 13: case 16:
        case 17: case 18: case 23: case 24: case 25: case 51: answer(0x900); break;
        default: break; /* CMD1 (MMC) and others: no answer. */
        }
    }

    uint32_t sdcard_core_cmd_event_read(void)
    {
        event_reads++;
        return cmd_stuck ? 0 : cmd_event;
    }

    uint32_t sdcard_core_data_event_read(void)
    {
        event_reads++;
        return data_stuck ? 0 : 0x1;
    }

    #include "@SDCARD_C@"

    DISKOPS *FfDiskOps;

    #define REQUIRE(cond) do { \\
        if (!(cond)) { \\
            fprintf(stderr, "requirement failed at %s:%d: %s\\n", __FILE__, __LINE__, #cond); \\
            return 1; \\
        } \\
    } while (0)

    int main(void)
    {
@MAIN@
        return 0;
    }
"""


def run_sdcard_harness(tmp_path, main, defines={}):
    include_dir = tmp_path / "include"
    source      = tmp_path / "sdcard_harness.c"
    binary      = tmp_path / "sdcard_harness"

    def write(path, contents=""):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(contents))

    write(include_dir / "generated" / "csr.h", CSR_H)
    write(include_dir / "generated" / "mem.h")
    write(include_dir / "generated" / "soc.h")
    write(include_dir / "system.h", "\n".join([
        "#define CONFIG_CLOCK_FREQUENCY 100000000",
        "void busy_wait(unsigned int ms);",
        "void busy_wait_us(unsigned int us);",
        *[f"#define {k} {v}" for k, v in defines.items()],
    ]) + "\n")
    harness = textwrap.dedent(MODEL_C)
    harness = harness.replace("@SDCARD_C@", f"{REPO}/litex/soc/software/liblitesdcard/sdcard.c")
    harness = harness.replace("@MAIN@", textwrap.indent(textwrap.dedent(main), " "*4))
    write(source, harness)

    subprocess.check_call([
        "gcc",
        "-std=gnu11",
        "-Wall",
        "-Werror",
        "-Wno-unused-function",
        "-Wno-unused-variable",
        "-Wno-unused-but-set-variable",
        "-I", str(include_dir),
        "-I", f"{REPO}/litex/soc/software",
        str(source),
        "-o", str(binary),
    ])
    return subprocess.check_output([str(binary)], timeout=30).decode()

def test_wait_loops_are_bounded(tmp_path):
    run_sdcard_harness(tmp_path, """
        /* Command done bit never rises: SD_TIMEOUT after SDCARD_CMD_TIMEOUT_US (2 s, 10 us polls). */
        cmd_stuck = true;
        REQUIRE(sdcard_go_idle() == SD_TIMEOUT);
        REQUIRE(event_reads == 200001);

        /* Data done bit never rises: SD_TIMEOUT after SDCARD_DATA_TIMEOUT_US per block. */
        cmd_stuck   = false;
        data_stuck  = true;
        event_reads = 0;
        REQUIRE(sdcard_read_multiple_block(0, 4) == SD_TIMEOUT);
        REQUIRE(event_reads == 1 + 4*200000 + 1);

        /* Working core: unchanged. */
        data_stuck = false;
        REQUIRE(sdcard_read_multiple_block(0, 4) == SD_OK);
    """)
