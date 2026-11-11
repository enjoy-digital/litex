#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import textwrap

# Host harness for liblitespi/spiflash.c: the LiteSPI master CSRs are replaced by functions that
# record the bytes of each command (CS high to CS low); the status register always reads ready.

CSR_H = """
    #ifndef __GENERATED_CSR_H
    #define __GENERATED_CSR_H

    #define CSR_SPIFLASH_BASE                             1
    #define CSR_SPIFLASH_MASTER_CS_ADDR                   1
    #define CSR_SPIFLASH_MASTER_PHYCONFIG_LEN_SIZE        8
    #define CSR_SPIFLASH_MASTER_PHYCONFIG_LEN_OFFSET      0
    #define CSR_SPIFLASH_MASTER_PHYCONFIG_WIDTH_SIZE      4
    #define CSR_SPIFLASH_MASTER_PHYCONFIG_WIDTH_OFFSET    8
    #define CSR_SPIFLASH_MASTER_PHYCONFIG_MASK_SIZE       8
    #define CSR_SPIFLASH_MASTER_PHYCONFIG_MASK_OFFSET    16
    #define CSR_SPIFLASH_MASTER_STATUS_TX_READY_OFFSET    0
    #define CSR_SPIFLASH_MASTER_STATUS_RX_READY_OFFSET    1

    uint32_t test_spiflash_master_status_read(void);
    uint32_t test_spiflash_master_rxtx_read(void);
    void test_spiflash_master_rxtx_write(uint32_t value);
    void test_spiflash_master_phyconfig_write(uint32_t value);
    void test_spiflash_master_cs_write(uint32_t value);

    #define spiflash_master_status_read      test_spiflash_master_status_read
    #define spiflash_master_rxtx_read        test_spiflash_master_rxtx_read
    #define spiflash_master_rxtx_write       test_spiflash_master_rxtx_write
    #define spiflash_master_phyconfig_write  test_spiflash_master_phyconfig_write
    #define spiflash_master_cs_write         test_spiflash_master_cs_write

    #endif
"""

HARNESS_C = """
    #include <stdbool.h>
    #include <stdint.h>
    #include <stdio.h>
    #include <string.h>

    #define MAX_TRANSACTIONS      16
    #define MAX_TRANSACTION_BYTES 300

    static uint8_t transactions[MAX_TRANSACTIONS][MAX_TRANSACTION_BYTES];
    static unsigned int transaction_lengths[MAX_TRANSACTIONS];
    static unsigned int transaction_count;
    static bool transaction_active;
    static bool rx_ready;

    uint32_t test_spiflash_master_status_read(void)
    {
        return 1 | (rx_ready << 1);
    }

    uint32_t test_spiflash_master_rxtx_read(void)
    {
        rx_ready = false;
        return 0;
    }

    void test_spiflash_master_phyconfig_write(uint32_t value)
    {
        (void)value;
    }

    void test_spiflash_master_cs_write(uint32_t value)
    {
        if (value) {
            transaction_active = true;
            transaction_lengths[transaction_count] = 0;
        } else if (transaction_active) {
            transaction_active = false;
            transaction_count++;
        }
    }

    void test_spiflash_master_rxtx_write(uint32_t value)
    {
        unsigned int length = transaction_lengths[transaction_count];

        if (transaction_count < MAX_TRANSACTIONS && length < MAX_TRANSACTION_BYTES)
            transactions[transaction_count][length] = value;
        transaction_lengths[transaction_count] = length + 1;
        rx_ready = true;
    }

    #include "@SPIFLASH_C@"

    #define REQUIRE(cond) do { \\
        if (!(cond)) { \\
            fprintf(stderr, "requirement failed at %s:%d: %s\\n", __FILE__, __LINE__, #cond); \\
            return 1; \\
        } \\
    } while (0)

    static void clear_transactions(void)
    {
        memset(transactions, 0, sizeof(transactions));
        memset(transaction_lengths, 0, sizeof(transaction_lengths));
        transaction_count  = 0;
        transaction_active = false;
        rx_ready           = false;
    }

    static int check_address(unsigned int index, uint8_t opcode, unsigned int addr_bytes, uint32_t addr)
    {
        REQUIRE(transactions[index][0] == opcode);
        for (unsigned int i = 0; i < addr_bytes; i++)
            REQUIRE(transactions[index][1 + i] == ((addr >> (8*(addr_bytes - 1 - i))) & 0xff));
        return 0;
    }

    static uint8_t data[600];

    static int check_program(unsigned int index, uint32_t addr, uint32_t offset, uint32_t len)
    {
        REQUIRE(transactions[index][0] == 0x06);
        REQUIRE(transaction_lengths[index + 1] == 1 + 3 + len);
        REQUIRE(check_address(index + 1, 0x02, 3, addr) == 0);
        REQUIRE(memcmp(&transactions[index + 1][4], &data[offset], len) == 0);
        REQUIRE(transactions[index + 2][0] == 0x05);
        return 0;
    }

    int main(void)
    {
        for (unsigned int i = 0; i < sizeof(data); i++)
            data[i] = i*7 + 3;
@MAIN@
        return 0;
    }
"""


def _run_harness(tmp_path, defines, main):
    repo        = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    include_dir = tmp_path / "include"
    source      = tmp_path / "spiflash_page_harness.c"
    binary      = tmp_path / "spiflash_page_harness"

    def write(path, contents=""):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(contents))

    write(include_dir / "generated" / "csr.h", CSR_H)
    write(include_dir / "generated" / "mem.h")
    write(include_dir / "libbase" / "crc.h")
    write(include_dir / "libbase" / "memtest.h")
    write(include_dir / "system.h", "\n".join([
        "#ifndef __SYSTEM_H",
        "#define __SYSTEM_H",
        "#include <stdbool.h>",
        "#define CONFIG_CLOCK_FREQUENCY 1000000",
        "#define SPIFLASH_PHY_FREQUENCY 1000000",
        "#define SPIFLASH_MODULE_NAME   \"model\"",
        *[f"#define {k} {v}" for k, v in defines.items()],
        "static inline void cdelay(int cycles) { (void)cycles; }",
        "#endif",
    ]) + "\n")
    harness = textwrap.dedent(HARNESS_C)
    harness = harness.replace("@SPIFLASH_C@", f"{repo}/litex/soc/software/liblitespi/spiflash.c")
    harness = harness.replace("@MAIN@", textwrap.indent(textwrap.dedent(main), " "*4))
    write(source, harness)

    subprocess.check_call([
        "gcc",
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wno-format",
        "-Wno-unused-function",
        "-I", str(include_dir),
        str(source),
        "-o", str(binary),
    ])
    subprocess.check_call([str(binary)])


def test_unaligned_write_does_not_cross_a_page(tmp_path):
    _run_harness(tmp_path, {}, """
        /* 300 bytes at 0x10: 240 bytes up to the 0x100 page boundary, then 60 bytes. */
        REQUIRE(spiflash_write_stream(0x10, data, 300) == 300);
        REQUIRE(transaction_count == 6);
        REQUIRE(check_program(0, 0x010,   0, 240) == 0);
        REQUIRE(check_program(3, 0x100, 240,  60) == 0);

        /* Aligned write: full 256-byte pages. */
        clear_transactions();
        REQUIRE(spiflash_write_stream(0x200, data, 300) == 300);
        REQUIRE(transaction_count == 6);
        REQUIRE(check_program(0, 0x200,   0, 256) == 0);
        REQUIRE(check_program(3, 0x300, 256,  44) == 0);

        /* Short write inside a page: one program. */
        clear_transactions();
        REQUIRE(spiflash_write_stream(0x4f0, data, 16) == 16);
        REQUIRE(transaction_count == 3);
        REQUIRE(check_program(0, 0x4f0, 0, 16) == 0);
    """)


def test_write_chunks_follow_a_smaller_module_page(tmp_path):
    _run_harness(tmp_path, {"SPIFLASH_MODULE_PAGE_SIZE": 64}, """
        REQUIRE(spiflash_write_stream(0x30, data, 100) == 100);
        REQUIRE(transaction_count == 9);
        REQUIRE(check_program(0, 0x30,  0, 16) == 0);
        REQUIRE(check_program(3, 0x40, 16, 64) == 0);
        REQUIRE(check_program(6, 0x80, 80, 20) == 0);
    """)
