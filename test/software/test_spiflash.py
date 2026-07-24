#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import textwrap


def _write(path, contents=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(contents))


def test_is25lp128_quad_enable_preserves_status(tmp_path):
    repo        = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    include_dir = tmp_path / "include"
    source      = tmp_path / "spiflash_harness.c"
    binary      = tmp_path / "spiflash_harness"

    _write(include_dir / "generated" / "csr.h", """
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
    """)
    _write(include_dir / "generated" / "mem.h")
    _write(include_dir / "libbase" / "crc.h")
    _write(include_dir / "libbase" / "memtest.h")
    _write(include_dir / "system.h", """
        #ifndef __SYSTEM_H
        #define __SYSTEM_H

        #include <stdbool.h>

        #define CONFIG_CLOCK_FREQUENCY                         1000000
        #define SPIFLASH_PHY_FREQUENCY                         1000000
        #define SPIFLASH_MODULE_NAME                         "is25lp128"
        #define SPIFLASH_MODULE_QUAD_CAPABLE
        #define SPIFLASH_MODULE_QUAD_ENABLE_WRSR_SR1_BIT6

        static inline void cdelay(int cycles) { (void)cycles; }

        #endif
    """)
    _write(source, f"""
        #include <stdbool.h>
        #include <stdint.h>
        #include <stdio.h>

        static uint8_t  flash_status;
        static uint8_t  transaction_command;
        static unsigned int transaction_index;
        static uint32_t phyconfig;
        static uint32_t rx_value;
        static uint32_t wrsr_value;
        static unsigned int wrsr_bits;
        static unsigned int write_enable_count;
        static bool rx_ready;
        static bool ignore_wrsr;

        uint32_t test_spiflash_master_status_read(void)
        {{
            return 1 | (rx_ready << 1);
        }}

        uint32_t test_spiflash_master_rxtx_read(void)
        {{
            rx_ready = false;
            return rx_value;
        }}

        void test_spiflash_master_phyconfig_write(uint32_t value)
        {{
            phyconfig = value;
        }}

        void test_spiflash_master_cs_write(uint32_t value)
        {{
            if (value) {{
                transaction_command = 0;
                transaction_index   = 0;
            }} else if (transaction_command == 0x06) {{
                flash_status |= 0x02;
                write_enable_count++;
            }}
        }}

        void test_spiflash_master_rxtx_write(uint32_t value)
        {{
            unsigned int bits = phyconfig & 0xff;

            rx_value = 0;
            if (bits > 8) {{
                transaction_command = (value >> (bits - 8)) & 0xff;
                if (transaction_command == 0x01) {{
                    wrsr_value = value;
                    wrsr_bits  = bits;
                    if ((flash_status & 0x02) && !ignore_wrsr)
                        flash_status = value & 0xfc;
                    else
                        flash_status &= ~0x02;
                }}
            }} else {{
                uint8_t byte = value;

                if (transaction_index++ == 0)
                    transaction_command = byte;
                else if (transaction_command == 0x05)
                    rx_value = flash_status;
            }}
            rx_ready = true;
        }}

        #include "{repo}/litex/soc/software/liblitespi/spiflash.c"

        #define REQUIRE(cond) do {{ \\
            if (!(cond)) {{ \\
                fprintf(stderr, "requirement failed at %s:%d: %s\\n", __FILE__, __LINE__, #cond); \\
                return 1; \\
            }} \\
        }} while (0)

        int main(void)
        {{
            flash_status = 0x9c;
            REQUIRE(spiflash_enable_quad_mode());
            REQUIRE(write_enable_count == 1);
            REQUIRE(wrsr_bits == 16);
            REQUIRE(wrsr_value == 0x01dc);
            REQUIRE(flash_status == 0xdc);

            REQUIRE(spiflash_enable_quad_mode());
            REQUIRE(write_enable_count == 1);

            flash_status       = 0x04;
            wrsr_value         = 0;
            wrsr_bits          = 0;
            write_enable_count = 0;
            ignore_wrsr        = true;
            REQUIRE(!spiflash_enable_quad_mode());
            REQUIRE(write_enable_count == 1);
            REQUIRE(wrsr_bits == 16);
            REQUIRE(wrsr_value == 0x0144);
            REQUIRE(flash_status == 0x04);
            return 0;
        }}
    """)

    subprocess.check_call([
        "gcc",
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wno-format",
        "-I", str(include_dir),
        str(source),
        "-o", str(binary),
    ])
    subprocess.check_call([str(binary)])


def test_erase_uses_module_geometry(tmp_path):
    repo        = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    include_dir = tmp_path / "include"
    source      = tmp_path / "spiflash_erase_harness.c"
    binary      = tmp_path / "spiflash_erase_harness"

    _write(include_dir / "generated" / "csr.h", """
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
    """)
    _write(include_dir / "generated" / "mem.h")
    _write(include_dir / "libbase" / "crc.h")
    _write(include_dir / "libbase" / "memtest.h")
    _write(include_dir / "system.h", """
        #ifndef __SYSTEM_H
        #define __SYSTEM_H

        #include <stdbool.h>

        #define CONFIG_CLOCK_FREQUENCY                         1000000
        #define SPIFLASH_PHY_FREQUENCY                         1000000
        #define SPIFLASH_MODULE_NAME                         "model"
        #define SPIFLASH_MODULE_ERASE_OPCODE                  0x21
        #define SPIFLASH_MODULE_ERASE_SIZE                    4096
        #define SPIFLASH_MODULE_ERASE_ADDR_BITS                 32

        static inline void cdelay(int cycles) { (void)cycles; }

        #endif
    """)
    _write(source, f"""
        #include <stdbool.h>
        #include <stdint.h>
        #include <stdio.h>
        #include <string.h>

        #define MAX_TRANSACTIONS 16
        #define MAX_TRANSACTION_BYTES 8

        static uint8_t transactions[MAX_TRANSACTIONS][MAX_TRANSACTION_BYTES];
        static unsigned int transaction_lengths[MAX_TRANSACTIONS];
        static unsigned int transaction_count;
        static bool transaction_active;
        static bool rx_ready;
        static uint32_t rx_value;

        uint32_t test_spiflash_master_status_read(void)
        {{
            return 1 | (rx_ready << 1);
        }}

        uint32_t test_spiflash_master_rxtx_read(void)
        {{
            rx_ready = false;
            return rx_value;
        }}

        void test_spiflash_master_phyconfig_write(uint32_t value)
        {{
            (void)value;
        }}

        void test_spiflash_master_cs_write(uint32_t value)
        {{
            if (value) {{
                transaction_active = true;
                transaction_lengths[transaction_count] = 0;
            }} else if (transaction_active) {{
                transaction_active = false;
                transaction_count++;
            }}
        }}

        void test_spiflash_master_rxtx_write(uint32_t value)
        {{
            unsigned int length = transaction_lengths[transaction_count];

            if (transaction_count < MAX_TRANSACTIONS && length < MAX_TRANSACTION_BYTES)
                transactions[transaction_count][length] = value;
            transaction_lengths[transaction_count] = length + 1;
            rx_value = 0;
            rx_ready = true;
        }}

        #include "{repo}/litex/soc/software/liblitespi/spiflash.c"

        #define REQUIRE(cond) do {{ \
            if (!(cond)) {{ \
                fprintf(stderr, "requirement failed at %s:%d: %s\\n", __FILE__, __LINE__, #cond); \
                return 1; \
            }} \
        }} while (0)

        static void clear_transactions(void)
        {{
            memset(transactions, 0, sizeof(transactions));
            memset(transaction_lengths, 0, sizeof(transaction_lengths));
            transaction_count  = 0;
            transaction_active = false;
            rx_ready            = false;
            rx_value            = 0;
        }}

        static int check_erase(unsigned int index, uint32_t address)
        {{
            REQUIRE(transaction_lengths[index] == 5);
            REQUIRE(transactions[index][0] == 0x21);
            REQUIRE(transactions[index][1] == ((address >> 24) & 0xff));
            REQUIRE(transactions[index][2] == ((address >> 16) & 0xff));
            REQUIRE(transactions[index][3] == ((address >>  8) & 0xff));
            REQUIRE(transactions[index][4] == ((address >>  0) & 0xff));
            return 0;
        }}

        int main(void)
        {{
            spiflash_erase_range(0x1234, 1);
            REQUIRE(transaction_count == 3);
            REQUIRE(transaction_lengths[0] == 1);
            REQUIRE(transactions[0][0] == 0x06);
            REQUIRE(check_erase(1, 0x1000) == 0);
            REQUIRE(transactions[2][0] == 0x05);

            clear_transactions();
            spiflash_erase_range(0x1fff, 2);
            REQUIRE(transaction_count == 6);
            REQUIRE(check_erase(1, 0x1000) == 0);
            REQUIRE(check_erase(4, 0x2000) == 0);

            clear_transactions();
            spiflash_erase_range(0xffffffff, 2);
            REQUIRE(transaction_count == 0);

            clear_transactions();
            spiflash_erase_4k_sector(0x3456);
            REQUIRE(transaction_count == 3);
            REQUIRE(transactions[0][0] == 0x06);
            REQUIRE(transaction_lengths[1] == 4);
            REQUIRE(transactions[1][0] == 0x20);
            REQUIRE(transactions[1][1] == 0x00);
            REQUIRE(transactions[1][2] == 0x34);
            REQUIRE(transactions[1][3] == 0x56);
            REQUIRE(transactions[2][0] == 0x05);
            return 0;
        }}
    """)

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
