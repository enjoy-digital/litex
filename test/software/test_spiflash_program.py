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

    static uint8_t data[16] = {
        0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
        0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff,
    };

    int main(void)
    {
@MAIN@
        return 0;
    }
"""


def _run_harness(tmp_path, defines, main):
    repo        = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    include_dir = tmp_path / "include"
    source      = tmp_path / "spiflash_program_harness.c"
    binary      = tmp_path / "spiflash_program_harness"

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


def test_program_uses_4byte_address_when_exported(tmp_path):
    # 32 MiB module exporting a 4-byte Page Program and a 4-byte erase.
    _run_harness(tmp_path, {
        "SPIFLASH_MODULE_PROGRAM_ADDR_BITS" : 32,
        "SPIFLASH_MODULE_ERASE_OPCODE"      : "0xdc",
        "SPIFLASH_MODULE_ERASE_SIZE"        : 65536,
        "SPIFLASH_MODULE_ERASE_ADDR_BITS"   : 32,
    }, """
        REQUIRE(spiflash_write_stream(0x01000100, data, 16) == 16);
        REQUIRE(transaction_count == 3);
        REQUIRE(transactions[0][0] == 0x06);
        REQUIRE(transaction_lengths[1] == 1 + 4 + 16);
        REQUIRE(check_address(1, 0x12, 4, 0x01000100) == 0);
        REQUIRE(memcmp(&transactions[1][5], data, 16) == 0);
        REQUIRE(transactions[2][0] == 0x05);

        clear_transactions();
        spiflash_erase_range(0x01ff0000, 1);
        REQUIRE(transaction_count == 3);
        REQUIRE(transaction_lengths[1] == 5);
        REQUIRE(check_address(1, 0xdc, 4, 0x01ff0000) == 0);
    """)


def test_3byte_commands_refuse_addresses_above_16mib(tmp_path):
    # Module without 4-byte commands: default 3-byte Page Program and 64 KiB 24-bit erase.
    _run_harness(tmp_path, {}, """
        /* Below 16 MiB: 3-byte Page Program. */
        REQUIRE(spiflash_write_stream(0x00fffff0, data, 16) == 16);
        REQUIRE(transaction_count == 3);
        REQUIRE(transaction_lengths[1] == 1 + 3 + 16);
        REQUIRE(check_address(1, 0x02, 3, 0x00fffff0) == 0);

        /* At/above 16 MiB or crossing it: refused, no command sent (the flash would wrap). */
        clear_transactions();
        REQUIRE(spiflash_write_stream(0x01000000, data, 16) == -1);
        REQUIRE(spiflash_write_stream(0x00fffff8, data, 16) == -1);
        REQUIRE(transaction_count == 0);

        /* Erase: same limit with the 24-bit erase command. */
        spiflash_erase_range(0x01000000, 1);
        spiflash_erase_range(0x00ff0000, 0x20000);
        spiflash_erase_4k_sector(0x01000000);
        REQUIRE(transaction_count == 0);

        spiflash_erase_range(0x00ff0000, 0x10000);
        REQUIRE(transaction_count == 3);
        REQUIRE(transaction_lengths[1] == 4);
        REQUIRE(check_address(1, 0xd8, 3, 0x00ff0000) == 0);
    """)
