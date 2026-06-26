#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import textwrap

import pytest


def _write(path, contents=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(contents))


def _write_bios_stubs(include_dir):
    _write(include_dir / "system.h", """
        #ifndef __SYSTEM_H
        #define __SYSTEM_H
        static inline void flush_cpu_icache(void) {}
        static inline void flush_cpu_dcache(void) {}
        static inline void flush_l2_cache(void) {}
        #endif
    """)
    _write(include_dir / "irq.h", """
        #ifndef __IRQ_H
        #define __IRQ_H
        static inline void irq_setmask(unsigned int mask) {(void)mask;}
        static inline void irq_setie(unsigned int ie) {(void)ie;}
        #endif
    """)
    for header in ["mem.h", "csr.h", "soc.h"]:
        _write(include_dir / "generated" / header)
    _write(include_dir / "libbase" / "uart.h", """
        #ifndef __UART_H
        #define __UART_H
        int uart_read_nonblock(void);
        char uart_read(void);
        void uart_write(char c);
        void uart_sync(void);
        #endif
    """)
    _write(include_dir / "libbase" / "console.h")
    _write(include_dir / "libbase" / "progress.h", """
        #ifndef __PROGRESS_H
        #define __PROGRESS_H
        static inline void init_progression_bar(unsigned int total) {(void)total;}
        static inline void show_progress(unsigned int current) {(void)current;}
        #endif
    """)
    _write(include_dir / "libliteeth" / "udp.h", """
        #ifndef __UDP_H
        #define __UDP_H
        #define IPTOINT(a, b, c, d) (((a) << 24) | ((b) << 16) | ((c) << 8) | (d))
        void udp_start(const unsigned char *mac, unsigned int ip);
        void udp_set_ip(unsigned int ip);
        void udp_set_mac(const unsigned char *mac);
        #endif
    """)
    _write(include_dir / "libliteeth" / "tftp.h", """
        #ifndef __TFTP_H
        #define __TFTP_H
        #include <stddef.h>
        int tftp_get(unsigned int ip, unsigned short server_port,
            const char *filename, char *buffer, size_t max_size);
        #endif
    """)
    _write(include_dir / "liblitesdcard" / "spisdcard.h", """
        #ifndef __SPISDCARD_H
        #define __SPISDCARD_H
        void fatfs_set_ops_spisdcard(void);
        #endif
    """)
    _write(include_dir / "liblitesdcard" / "sdcard.h", """
        #ifndef __SDCARD_H
        #define __SDCARD_H
        void fatfs_set_ops_sdcard(void);
        #endif
    """)
    _write(include_dir / "liblitesata" / "sata.h", """
        #ifndef __SATA_H
        #define __SATA_H
        void fatfs_set_ops_sata(void);
        #endif
    """)
    _write(include_dir / "libfatfs" / "ff.h", """
        #ifndef __FF_H
        #define __FF_H
        typedef unsigned int UINT;
        typedef int FRESULT;
        typedef struct { int dummy; } FATFS;
        typedef struct { unsigned int size; } FIL;
        #define FR_OK 0
        #define FA_READ 1
        FRESULT f_mount(FATFS *fs, const char *path, int opt);
        FRESULT f_open(FIL *file, const char *path, int mode);
        unsigned int f_size(FIL *file);
        FRESULT f_read(FIL *file, void *buffer, unsigned int btr, UINT *br);
        FRESULT f_close(FIL *file);
        #endif
    """)


def test_bios_boot_helpers_host_coverage(tmp_path):
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    include_dir = tmp_path / "include"
    source = tmp_path / "bios_boot_harness.c"
    binary = tmp_path / "bios_boot_harness"

    _write_bios_stubs(include_dir)
    _write(source, f"""
        #include <setjmp.h>
        #include <stddef.h>
        #include <stdint.h>
        #include <stdio.h>
        #include <string.h>

        #define CSR_UART_BASE 1
        #define CSR_ETHMAC_BASE 1
        #define CONFIG_CLOCK_FREQUENCY 1000000
        #define CONFIG_BIOS_NO_DELAYS 1
        #define MAIN_RAM_BASE 0x1000
        #define MAIN_RAM_SIZE 0x1000
        #define SRAM_BASE 0x3000
        #define SRAM_SIZE 0x100

        static jmp_buf boot_jmp;
        static unsigned long boot_r1;
        static unsigned long boot_r2;
        static unsigned long boot_r3;
        static unsigned long boot_addr;

        void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr);
        void bios_print_section(const char *name);
        void uart_sync(void);
        unsigned int crc32(const unsigned char *buffer, unsigned int len);
        void udp_start(const unsigned char *mac, unsigned int ip);
        void udp_set_ip(unsigned int ip);
        void udp_set_mac(const unsigned char *mac);
        int tftp_get(unsigned int ip, unsigned short server_port,
            const char *filename, char *buffer, size_t max_size);
        void timer0_en_write(unsigned int value);
        void timer0_reload_write(unsigned int value);
        void timer0_load_write(unsigned int value);
        void timer0_update_value_write(unsigned int value);
        unsigned int timer0_value_read(void);

        void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr)
        {{
            boot_r1 = r1;
            boot_r2 = r2;
            boot_r3 = r3;
            boot_addr = addr;
            longjmp(boot_jmp, 1);
        }}

        void bios_print_section(const char *name) {{ (void)name; }}
        void uart_sync(void) {{}}
        unsigned int crc32(const unsigned char *buffer, unsigned int len)
        {{
            (void)buffer;
            (void)len;
            return 0;
        }}
        void udp_start(const unsigned char *mac, unsigned int ip) {{ (void)mac; (void)ip; }}
        void udp_set_ip(unsigned int ip) {{ (void)ip; }}
        void udp_set_mac(const unsigned char *mac) {{ (void)mac; }}
        int tftp_get(unsigned int ip, unsigned short server_port,
            const char *filename, char *buffer, size_t max_size)
        {{
            (void)ip;
            (void)server_port;
            (void)filename;
            (void)buffer;
            (void)max_size;
            return 0;
        }}

        static unsigned char uart_in[512];
        static int uart_in_len;
        static int uart_in_pos;
        static unsigned char uart_out[512];
        static int uart_out_len;
        static unsigned int timer_value;
        static unsigned int timer_loads;

        void timer0_en_write(unsigned int value) {{ (void)value; }}
        void timer0_reload_write(unsigned int value) {{ (void)value; }}
        void timer0_load_write(unsigned int value)
        {{
            (void)value;
            timer_loads++;
            timer_value = 1000;
        }}
        void timer0_update_value_write(unsigned int value) {{ (void)value; }}
        unsigned int timer0_value_read(void)
        {{
            if (timer_value == 0)
                return 0;
            timer_value--;
            return 1;
        }}
        int uart_read_nonblock(void)
        {{
            return uart_in_pos < uart_in_len;
        }}
        char uart_read(void)
        {{
            return uart_in[uart_in_pos++];
        }}
        void uart_write(char c)
        {{
            uart_out[uart_out_len++] = (unsigned char)c;
        }}

        #include "{repo}/litex/soc/software/bios/boot.c"

        #define REQUIRE(cond) do {{ \\
            if (!(cond)) {{ \\
                fprintf(stderr, "requirement failed at %s:%d: %s\\n", __FILE__, __LINE__, #cond); \\
                return 1; \\
            }} \\
        }} while (0)

        struct load_event {{
            char filename[32];
            unsigned long addr;
            size_t max_size;
        }};

        struct load_ctx {{
            int count;
            int fail_after;
            struct load_event events[8];
        }};

        static int record_load(void *opaque, const char *filename,
            unsigned long load_addr, size_t max_size)
        {{
            struct load_ctx *ctx = opaque;
            int index = ctx->count++;

            if (index < 8) {{
                strncpy(ctx->events[index].filename, filename,
                    sizeof(ctx->events[index].filename) - 1);
                ctx->events[index].addr = load_addr;
                ctx->events[index].max_size = max_size;
            }}

            if ((ctx->fail_after >= 0) && (index >= ctx->fail_after))
                return 0;
            return 1;
        }}

        static void append_input(const unsigned char *data, int length)
        {{
            memcpy(&uart_in[uart_in_len], data, length);
            uart_in_len += length;
        }}

        static void append_frame(unsigned char cmd, const unsigned char *payload,
            unsigned char payload_length)
        {{
            unsigned char crc_buffer[256];
            unsigned short crc;

            crc_buffer[0] = cmd;
            if (payload_length)
                memcpy(&crc_buffer[1], payload, payload_length);
            crc = crc16(crc_buffer, payload_length + 1);

            uart_in[uart_in_len++] = payload_length;
            uart_in[uart_in_len++] = (crc >> 8) & 0xff;
            uart_in[uart_in_len++] = crc & 0xff;
            uart_in[uart_in_len++] = cmd;
            if (payload_length)
                append_input(payload, payload_length);
        }}

        static void append_bad_crc_frame(unsigned char cmd)
        {{
            uart_in[uart_in_len++] = 0;
            uart_in[uart_in_len++] = 0xff;
            uart_in[uart_in_len++] = 0xff;
            uart_in[uart_in_len++] = cmd;
        }}

        static void reset_serial(const unsigned char *ack, int ack_length)
        {{
            uart_in_len = 0;
            uart_in_pos = 0;
            uart_out_len = 0;
            timer_loads = 0;
            if (ack != NULL)
                append_input(ack, ack_length);
        }}

        static int test_boot_load_max_size(void)
        {{
            size_t max_size;

            REQUIRE(boot_load_max_size(MAIN_RAM_BASE, &max_size) == 1);
            REQUIRE(max_size == MAIN_RAM_SIZE);
            REQUIRE(boot_load_max_size(MAIN_RAM_BASE + MAIN_RAM_SIZE - 1, &max_size) == 1);
            REQUIRE(max_size == 1);
            REQUIRE(boot_load_max_size(MAIN_RAM_BASE + MAIN_RAM_SIZE - 16, &max_size) == 1);
            REQUIRE(max_size == 16);
            REQUIRE(boot_load_max_size(SRAM_BASE + 0x20, &max_size) == 1);
            REQUIRE(max_size == SRAM_SIZE - 0x20);
            REQUIRE(boot_load_max_size(MAIN_RAM_BASE - 1, &max_size) == 0);
            REQUIRE(boot_load_max_size(MAIN_RAM_BASE + MAIN_RAM_SIZE, &max_size) == 0);
            return 0;
        }}

        static int test_manifest_explicit_boot_address(void)
        {{
            const char *json =
                "{{\\"bootargs\\": \\"ignored\\", \\"r1\\": \\"0x11\\", "
                "\\"r2\\": \\"0x22\\", \\"r3\\": \\"0x33\\", "
                "\\"addr\\": \\"0x1800\\", \\"image.bin\\": \\"0x1000\\"}}";
            struct load_ctx ctx = {{ .fail_after = -1 }};

            if (setjmp(boot_jmp) == 0)
                boot_from_json_buffer(json, strlen(json), record_load, &ctx);

            REQUIRE(ctx.count == 1);
            REQUIRE(strcmp(ctx.events[0].filename, "image.bin") == 0);
            REQUIRE(ctx.events[0].addr == 0x1000);
            REQUIRE(ctx.events[0].max_size == MAIN_RAM_SIZE);
            REQUIRE(boot_r1 == 0x11);
            REQUIRE(boot_r2 == 0x22);
            REQUIRE(boot_r3 == 0x33);
            REQUIRE(boot_addr == 0x1800);
            return 0;
        }}

        static int test_manifest_defaults_to_last_image(void)
        {{
            const char *json =
                "{{\\"first.bin\\": \\"0x1000\\", \\"second.bin\\": \\"0x1100\\"}}";
            struct load_ctx ctx = {{ .fail_after = -1 }};

            boot_addr = 0;
            if (setjmp(boot_jmp) == 0)
                boot_from_json_buffer(json, strlen(json), record_load, &ctx);

            REQUIRE(ctx.count == 2);
            REQUIRE(strcmp(ctx.events[0].filename, "first.bin") == 0);
            REQUIRE(strcmp(ctx.events[1].filename, "second.bin") == 0);
            REQUIRE(ctx.events[1].max_size == MAIN_RAM_SIZE - 0x100);
            REQUIRE(boot_addr == 0x1100);
            return 0;
        }}

        static int test_manifest_explicit_addr_ordering_and_boundaries(void)
        {{
            const char *addr_after =
                "{{\\"image.bin\\": \\"0x1000\\", \\"addr\\": \\"0x1800\\"}}";
            const char *addr_before =
                "{{\\"addr\\": \\"0x1804\\", \\"image.bin\\": \\"0x1000\\"}}";
            const char *last_byte =
                "{{\\"last.bin\\": \\"0x1fff\\"}}";
            struct load_ctx ctx = {{ .fail_after = -1 }};

            boot_addr = 0;
            if (setjmp(boot_jmp) == 0)
                boot_from_json_buffer(addr_after, strlen(addr_after), record_load, &ctx);
            REQUIRE(ctx.count == 1);
            REQUIRE(boot_addr == 0x1800);

            memset(&ctx, 0, sizeof(ctx));
            ctx.fail_after = -1;
            boot_addr = 0;
            if (setjmp(boot_jmp) == 0)
                boot_from_json_buffer(addr_before, strlen(addr_before), record_load, &ctx);
            REQUIRE(ctx.count == 1);
            REQUIRE(boot_addr == 0x1804);

            memset(&ctx, 0, sizeof(ctx));
            ctx.fail_after = -1;
            boot_addr = 0;
            if (setjmp(boot_jmp) == 0)
                boot_from_json_buffer(last_byte, strlen(last_byte), record_load, &ctx);
            REQUIRE(ctx.count == 1);
            REQUIRE(ctx.events[0].max_size == 1);
            REQUIRE(boot_addr == 0x1fff);
            return 0;
        }}

        static int test_manifest_rejects_bad_addresses_and_load_failures(void)
        {{
            const char *bad_addr = "{{\\"image.bin\\": \\"not-an-address\\"}}";
            const char *outside_ram = "{{\\"image.bin\\": \\"0x5000\\"}}";
            const char *load_fails = "{{\\"image.bin\\": \\"0x1000\\", \\"later.bin\\": \\"0x1100\\"}}";
            struct load_ctx ctx = {{ .fail_after = -1 }};

            boot_from_json_buffer(bad_addr, strlen(bad_addr), record_load, &ctx);
            REQUIRE(ctx.count == 0);

            memset(&ctx, 0, sizeof(ctx));
            ctx.fail_after = -1;
            boot_from_json_buffer(outside_ram, strlen(outside_ram), record_load, &ctx);
            REQUIRE(ctx.count == 0);

            memset(&ctx, 0, sizeof(ctx));
            ctx.fail_after = 0;
            boot_from_json_buffer(load_fails, strlen(load_fails), record_load, &ctx);
            REQUIRE(ctx.count == 1);
            REQUIRE(boot_addr != 0x1000);
            return 0;
        }}

        static int test_manifest_rejects_oversized_tokens_and_malformed_json(void)
        {{
            /* Name longer than the 256-byte json_name buffer: the manifest must be rejected
               without any load (a partial boot would fail in harder-to-debug ways). */
            static char long_name[512];
            const char *malformed = "{{\\"image.bin\\": \\"0x1000\\"";
            struct load_ctx ctx = {{ .fail_after = -1 }};
            int n = 0;

            long_name[n++] = '{{';
            long_name[n++] = '"';
            for (int i = 0; i < 300; i++)
                long_name[n++] = 'a';
            n += sprintf(&long_name[n], "\\": \\"0x1000\\"}}");

            boot_from_json_buffer(long_name, strlen(long_name), record_load, &ctx);
            REQUIRE(ctx.count == 0);

            boot_from_json_buffer(malformed, strlen(malformed), record_load, &ctx);
            REQUIRE(ctx.count == 0);
            return 0;
        }}

        static int test_manifest_rejects_token_pressure_and_bad_registers(void)
        {{
            /* 33 entries = 67 jsmn tokens, exceeding the 64-token budget: the manifest must
               be rejected (JSMN_ERROR_NOMEM) without any load. */
            static char too_many_tokens[1024];
            const char *bad_r1 = "{{\\"r1\\": \\"bad\\", \\"image.bin\\": \\"0x1000\\"}}";
            struct load_ctx ctx = {{ .fail_after = -1 }};
            int n = 0;

            n += sprintf(&too_many_tokens[n], "{{");
            for (int i = 0; i < 33; i++)
                n += sprintf(&too_many_tokens[n], "%s\\"k%02d\\": \\"0x1000\\"", i ? "," : "", i);
            n += sprintf(&too_many_tokens[n], "}}");

            boot_from_json_buffer(too_many_tokens, strlen(too_many_tokens), record_load, &ctx);
            REQUIRE(ctx.count == 0);

            boot_from_json_buffer(bad_r1, strlen(bad_r1), record_load, &ctx);
            REQUIRE(ctx.count == 0);
            return 0;
        }}

        static int test_serialboot_ack_cancel_and_timeout(void)
        {{
            int result;

            reset_serial((const unsigned char *)"Q", 1);
            result = serialboot();
            REQUIRE(result == 0);

            reset_serial(NULL, 0);
            result = serialboot();
            REQUIRE(result == 1);
            REQUIRE(timer_loads == 1);
            return 0;
        }}

        static int test_serialboot_rejects_out_of_range_load_and_recovers(void)
        {{
            static const unsigned char ack[] = SFL_MAGIC_ACK;
            unsigned char bad_load_payload[4] = {{0x00, 0x00, 0x50, 0x00}};
            int result;
            int saw_error = 0;
            int saw_success = 0;
            int i;

            reset_serial(ack, SFL_MAGIC_LEN);
            append_frame(SFL_CMD_LOAD, bad_load_payload, sizeof(bad_load_payload));
            append_frame(SFL_CMD_ABORT, NULL, 0);

            result = serialboot();
            REQUIRE(result == 1);

            for (i = SFL_MAGIC_LEN; i < uart_out_len; i++) {{
                if (uart_out[i] == SFL_ACK_ERROR)
                    saw_error = 1;
                if (uart_out[i] == SFL_ACK_SUCCESS)
                    saw_success = 1;
            }}
            REQUIRE(saw_error);
            REQUIRE(saw_success);
            return 0;
        }}

        static int test_serialboot_protocol_errors_recover_with_abort(void)
        {{
            static const unsigned char ack[] = SFL_MAGIC_ACK;
            unsigned char short_payload[3] = {{0x00, 0x00, 0x10}};
            int result;
            int saw_crc = 0;
            int saw_unknown = 0;
            int saw_error = 0;
            int saw_success = 0;
            int i;

            reset_serial(ack, SFL_MAGIC_LEN);
            append_bad_crc_frame(SFL_CMD_ABORT);
            append_frame(0x7f, NULL, 0);
            append_frame(SFL_CMD_LOAD, short_payload, sizeof(short_payload));
            append_frame(SFL_CMD_JUMP, short_payload, sizeof(short_payload));
            append_frame(SFL_CMD_ABORT, NULL, 0);

            result = serialboot();
            REQUIRE(result == 1);

            for (i = SFL_MAGIC_LEN; i < uart_out_len; i++) {{
                if (uart_out[i] == SFL_ACK_CRCERROR)
                    saw_crc = 1;
                if (uart_out[i] == SFL_ACK_UNKNOWN)
                    saw_unknown = 1;
                if (uart_out[i] == SFL_ACK_ERROR)
                    saw_error++;
                if (uart_out[i] == SFL_ACK_SUCCESS)
                    saw_success = 1;
            }}
            REQUIRE(saw_crc);
            REQUIRE(saw_unknown);
            REQUIRE(saw_error == 2);
            REQUIRE(saw_success);
            return 0;
        }}

        static int test_serialboot_jump_boots_requested_address(void)
        {{
            static const unsigned char ack[] = SFL_MAGIC_ACK;
            unsigned char jump_payload[4] = {{0x12, 0x34, 0x56, 0x78}};
            int jumped;
            int i;

            reset_serial(ack, SFL_MAGIC_LEN);
            append_frame(SFL_CMD_JUMP, jump_payload, sizeof(jump_payload));

            jumped = setjmp(boot_jmp);
            if (jumped == 0)
                (void)serialboot();

            REQUIRE(jumped == 1);
            REQUIRE(boot_r1 == 0);
            REQUIRE(boot_r2 == 0);
            REQUIRE(boot_r3 == 0);
            REQUIRE(boot_addr == 0x12345678);
            for (i = SFL_MAGIC_LEN; i < uart_out_len; i++) {{
                if (uart_out[i] == SFL_ACK_SUCCESS)
                    return 0;
            }}
            REQUIRE(0);
            return 0;
        }}

        int main(void)
        {{
            if (test_boot_load_max_size())
                return 1;
            if (test_manifest_explicit_boot_address())
                return 1;
            if (test_manifest_defaults_to_last_image())
                return 1;
            if (test_manifest_explicit_addr_ordering_and_boundaries())
                return 1;
            if (test_manifest_rejects_bad_addresses_and_load_failures())
                return 1;
            if (test_manifest_rejects_oversized_tokens_and_malformed_json())
                return 1;
            if (test_manifest_rejects_token_pressure_and_bad_registers())
                return 1;
            if (test_serialboot_ack_cancel_and_timeout())
                return 1;
            if (test_serialboot_rejects_out_of_range_load_and_recovers())
                return 1;
            if (test_serialboot_protocol_errors_recover_with_abort())
                return 1;
            if (test_serialboot_jump_boots_requested_address())
                return 1;
            return 0;
        }}
    """)

    cmd = [
        "gcc",
        "-std=gnu99",
        "-Wall",
        "-Wextra",
        "-Wstrict-prototypes",
        "-Wold-style-definition",
        "-Wmissing-prototypes",
        "-ffunction-sections",
        "-fdata-sections",
        f"-I{include_dir}",
        f"-I{repo}/litex/soc/software",
        f"-I{repo}/litex/soc/software/bios",
        str(source),
        f"{repo}/litex/soc/software/libbase/crc16.c",
        "-Wl,--gc-sections",
        "-o",
        str(binary),
    ]
    subprocess.check_call(cmd)
    subprocess.check_call([str(binary)])


def test_bios_flashboot_host_coverage(tmp_path):
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    include_dir = tmp_path / "include"
    source = tmp_path / "bios_flashboot_harness.c"
    binary = tmp_path / "bios_flashboot_harness"

    _write_bios_stubs(include_dir)
    _write(include_dir / "system.h", """
        #ifndef __SYSTEM_H
        #define __SYSTEM_H
        #include <stdint.h>
        #define MMPTR(a) (*((volatile uint32_t *)(uintptr_t)(a)))
        #define min(a, b) ((a) < (b) ? (a) : (b))
        static inline void flush_cpu_icache(void) {}
        static inline void flush_cpu_dcache(void) {}
        static inline void flush_l2_cache(void) {}
        #endif
    """)
    _write(source, f"""
        #include <setjmp.h>
        #include <stdint.h>
        #include <stdio.h>
        #include <string.h>
        #include <sys/mman.h>
        #include <unistd.h>

        #ifndef MAP_32BIT
        #define MAP_32BIT 0
        #endif

        static unsigned long flash_base;
        static unsigned long ram_base;
        static const unsigned long ram_size = 0x1000;
        static jmp_buf boot_jmp;
        static unsigned long boot_addr;

        #define FLASH_BOOT_ADDRESS ((unsigned int)flash_base)
        #define MAIN_RAM_BASE ram_base
        #define MAIN_RAM_BASE_VA ram_base
        #define MAIN_RAM_SIZE ram_size

        void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr);
        void bios_print_section(const char *name);

        void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr)
        {{
            (void)r1;
            (void)r2;
            (void)r3;
            boot_addr = addr;
            longjmp(boot_jmp, 1);
        }}

        void bios_print_section(const char *name)
        {{
            (void)name;
        }}

        #include "{repo}/litex/soc/software/bios/boot.c"

        #define REQUIRE(cond) do {{ \\
            if (!(cond)) {{ \\
                fprintf(stderr, "requirement failed at %s:%d: %s\\n", __FILE__, __LINE__, #cond); \\
                return 1; \\
            }} \\
        }} while (0)

        static int map_low_memory(void)
        {{
            void *flash;
            void *ram;

            flash = mmap(NULL, 0x02000000, PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS | MAP_32BIT, -1, 0);
            if (flash == MAP_FAILED)
                return 77;
            ram = mmap(NULL, ram_size, PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS | MAP_32BIT, -1, 0);
            if (ram == MAP_FAILED)
                return 77;

            flash_base = (unsigned long)flash;
            ram_base = (unsigned long)ram;
            if ((flash_base > 0xffffffffUL) || (ram_base > 0xffffffffUL))
                return 77;
            return 0;
        }}

        static void write_image(uint32_t length, int valid_crc)
        {{
            uint32_t crc;
            uint32_t *header = (uint32_t *)(uintptr_t)flash_base;
            unsigned char *payload = (unsigned char *)(uintptr_t)(flash_base + 8);
            uint32_t i;

            for (i = 0; i < length; i++)
                payload[i] = (unsigned char)(i ^ 0x5a);

            crc = crc32(payload, length);
            header[0] = length;
            header[1] = valid_crc ? crc : (crc ^ 0xffffffff);
        }}

        static int test_flash_image_validation(void)
        {{
            write_image(31, 1);
            REQUIRE(check_image_in_flash(FLASH_BOOT_ADDRESS) == 0);

            write_image(16 * 1024 * 1024 + 1, 1);
            REQUIRE(check_image_in_flash(FLASH_BOOT_ADDRESS) == 0);

            write_image(64, 0);
            REQUIRE(check_image_in_flash(FLASH_BOOT_ADDRESS) == 0);

            write_image(64, 1);
            REQUIRE(check_image_in_flash(FLASH_BOOT_ADDRESS) == 64);
            return 0;
        }}

        static int test_flash_copy_and_boot(void)
        {{
            unsigned char *ram = (unsigned char *)(uintptr_t)ram_base;

            memset(ram, 0, ram_size);
            write_image(ram_size + 1, 1);
            REQUIRE(copy_image_from_flash_to_ram(FLASH_BOOT_ADDRESS, ram_base) == 0);

            memset(ram, 0, ram_size);
            write_image(128, 1);
            REQUIRE(copy_image_from_flash_to_ram(FLASH_BOOT_ADDRESS, ram_base) == 1);
            REQUIRE(memcmp(ram, (void *)(uintptr_t)(flash_base + 8), 128) == 0);

            boot_addr = 0;
            if (setjmp(boot_jmp) == 0)
                flashboot();
            REQUIRE(boot_addr == ram_base);
            return 0;
        }}

        int main(void)
        {{
            int r;

            r = map_low_memory();
            if (r != 0)
                return r;
            if (test_flash_image_validation())
                return 1;
            if (test_flash_copy_and_boot())
                return 1;
            return 0;
        }}
    """)

    cmd = [
        "gcc",
        "-std=gnu99",
        "-Wall",
        "-Wextra",
        "-Wstrict-prototypes",
        "-Wold-style-definition",
        "-Wmissing-prototypes",
        "-Wno-format",
        "-Wno-int-to-pointer-cast",
        "-ffunction-sections",
        "-fdata-sections",
        f"-I{include_dir}",
        f"-I{repo}/litex/soc/software",
        f"-I{repo}/litex/soc/software/bios",
        str(source),
        f"{repo}/litex/soc/software/libbase/crc16.c",
        f"{repo}/litex/soc/software/libbase/crc32.c",
        "-Wl,--gc-sections",
        "-o",
        str(binary),
    ]
    subprocess.check_call(cmd)
    result = subprocess.run([str(binary)], check=False)
    if result.returncode == 77:
        pytest.skip("host cannot provide low-address mmap for BIOS flashboot test")
    assert result.returncode == 0
