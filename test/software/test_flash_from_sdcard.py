#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import textwrap

import pytest

# Host harness for the BIOS flash_from_sdcard command (bios/cmds/cmd_spiflash.c): FatFs and the
# SPI Flash write are stubs, f_mount checks that the SDCard disk operations were selected.

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _write(path, contents=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(contents))


@pytest.mark.parametrize("csr,ops", [
    ("CSR_SDCARD_BASE",    "sdcard"),
    ("CSR_SPISDCARD_BASE", "spisdcard"),
])
def test_flash_from_sdcard_selects_sdcard_disk_ops(tmp_path, csr, ops):
    include_dir = tmp_path / "include"
    source      = tmp_path / "flash_from_sdcard.c"
    binary      = tmp_path / "flash_from_sdcard"
    _write(include_dir / "generated" / "csr.h", f"""
        #ifndef __GENERATED_CSR_H
        #define __GENERATED_CSR_H
        #define CSR_SPIFLASH_MASTER_CS_ADDR 1
        #define {csr} 1
        #endif
    """)
    for header in ["mem.h", "soc.h"]:
        _write(include_dir / "generated" / header)
    _write(include_dir / "libbase" / "parse.h", """
        #include <stdbool.h>
        bool parse_uint(char *s, unsigned int *v);
        bool parse_ulong(char *s, unsigned long *v);
    """)
    _write(include_dir / "libbase" / "progress.h", """
        void init_progression_bar(int max);
        void show_progress(int now);
    """)
    _write(include_dir / "libfatfs" / "ff.h", """
        #ifndef __FF_H
        #define __FF_H
        typedef unsigned int UINT;
        typedef int FRESULT;
        typedef struct { int dummy; } FATFS;
        typedef struct { unsigned int size; } FIL;
        #define FR_OK 0
        #define FR_NOT_READY 3
        #define FA_READ 1
        FRESULT f_mount(FATFS *fs, const char *path, int opt);
        FRESULT f_open(FIL *file, const char *path, int mode);
        unsigned int f_size(FIL *file);
        FRESULT f_read(FIL *file, void *buffer, unsigned int btr, UINT *br);
        FRESULT f_close(FIL *file);
        #endif
    """)
    _write(source, f"""
        #include <assert.h>
        #include <stdint.h>
        #include <stdio.h>
        #include <string.h>

        static const char *disk_ops;
        static unsigned int mounts, written;

        #include "{REPO}/litex/soc/software/bios/cmds/cmd_spiflash.c"

        void fatfs_set_ops_sdcard(void)    {{ disk_ops = "sdcard"; }}
        void fatfs_set_ops_spisdcard(void) {{ disk_ops = "spisdcard"; }}
        void fatfs_set_ops_sata(void)      {{ disk_ops = "sata"; }}

        FRESULT f_mount(FATFS *fs, const char *path, int opt)
        {{
            (void)path; (void)opt;
            if (fs == NULL)
                return FR_OK;
            /* FatFs dereferences FfDiskOps (NULL at reset) in f_mount. */
            if (disk_ops == NULL || strcmp(disk_ops, "{ops}") != 0)
                return FR_NOT_READY;
            mounts++;
            return FR_OK;
        }}
        FRESULT f_open(FIL *file, const char *path, int mode) {{ (void)path; (void)mode; file->size = 4; return FR_OK; }}
        unsigned int f_size(FIL *file) {{ return file->size; }}
        FRESULT f_read(FIL *file, void *buffer, unsigned int btr, UINT *br)
        {{
            (void)btr;
            memset(buffer, 0x5a, file->size);
            *br = file->size;
            file->size = 0;
            return FR_OK;
        }}
        FRESULT f_close(FIL *file) {{ (void)file; return FR_OK; }}
        void init_progression_bar(int max) {{ (void)max; }}
        void show_progress(int now) {{ (void)now; }}
        bool parse_uint(char *s, unsigned int *v) {{ (void)s; (void)v; return false; }}
        bool parse_ulong(char *s, unsigned long *v) {{ (void)s; (void)v; return false; }}
        int spiflash_write_stream(uint32_t addr, uint8_t *stream, uint32_t len)
        {{
            (void)addr; (void)stream;
            written += len;
            return len;
        }}
        void spiflash_erase_range(uint32_t addr, uint32_t len) {{ (void)addr; (void)len; }}

        int main(void)
        {{
            char *params[] = {{"boot.bin"}};

            /* No sdcardboot before, then after a sataboot (FfDiskOps on SATA). */
            flash_from_sdcard_handler(1, params);
            fatfs_set_ops_sata();
            flash_from_sdcard_handler(1, params);
            assert(mounts == 2);
            assert(written == 8);
            return 0;
        }}
    """)
    subprocess.check_call([
        "gcc",
        "-std=gnu11",
        "-Wall",
        "-Werror",
        "-Wno-unused-function",
        "-I", str(include_dir),
        "-I", f"{REPO}/litex/soc/software",
        "-I", f"{REPO}/litex/soc/software/include",
        str(source),
        "-o", str(binary),
    ])
    subprocess.check_call([str(binary)], timeout=10)
