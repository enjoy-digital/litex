# SPDX-License-Identifier: BSD-2-Clause

import subprocess
from pathlib import Path


def test_spi_transfer_failures_reach_storage_callers(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    generated = tmp_path / "generated"
    generated.mkdir()
    for name in ["csr", "mem", "soc"]:
        (generated / f"{name}.h").write_text("")
    (tmp_path / "system.h").write_text("")
    source = tmp_path / "spisd.c"
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <libbase/timeout.h>
#define CSR_SPISDCARD_BASE 1
#define CONFIG_CLOCK_FREQUENCY 100000000
#define min(a, b) ((a) < (b) ? (a) : (b))
#define max(a, b) ((a) > (b) ? (a) : (b))
static int transfers, status_reads, stuck, block_mode, fail_transfer;
void timeout_start(struct timeout *t, unsigned int us) { (void)us; t->remaining = 4; }
int timeout_expired(struct timeout *t) { return !--t->remaining; }
void busy_wait(unsigned int ms) { (void)ms; }
void busy_wait_us(unsigned int us) { (void)us; }
static void spisdcard_clk_divider_write(uint32_t v) { (void)v; }
static void spisdcard_mosi_write(uint32_t v) { (void)v; }
static void spisdcard_cs_write(uint32_t v) { (void)v; }
static void spisdcard_control_write(uint32_t v) { (void)v; transfers++; }
static uint32_t spisdcard_status_read(void)
{
    status_reads++;
    return stuck || transfers == fail_transfer ? 0 : 1;
}
static uint32_t spisdcard_miso_read(void)
{
    return block_mode && transfers == 1 ? 0xfe : 0x5a;
}
#include <liblitesdcard/spisdcard.c>
DISKOPS *FfDiskOps;

int main(void)
{
    uint8_t buffer[512];
    assert(spi_xfer(0xff) == 0x5a);
    transfers = status_reads = 0;
    stuck = 1;
    assert(spi_xfer(0xff) == -1);
    assert(status_reads <= 6);
    transfers = 0;
    assert(!spisdcard_init());
    assert(transfers == 1);
    transfers = 0;
    assert(spisd_disk_read(0, buffer, 0, 1) == RES_ERROR);
    assert(transfers <= 3);
    transfers = 0;
    stuck = 0;
    block_mode = 1;
    fail_transfer = 4;
    memset(buffer, 0xa5, sizeof(buffer));
    assert(!spisdcardreceive_block(buffer));
    assert(buffer[0] == 0x5a && buffer[1] == 0x5a && buffer[2] == 0xa5);
    transfers = 0;
    fail_transfer = 0;
    assert(spisdcardreceive_block(buffer));
    for (unsigned int i = 0; i < sizeof(buffer); i++) assert(buffer[i] == 0x5a);
    return 0;
}
''')
    binary = tmp_path / "spisd"
    subprocess.check_call([
        "gcc", "-std=gnu99", "-Wall", "-Werror", f"-I{tmp_path}",
        f"-I{repo}/litex/soc/software", str(source), "-o", str(binary),
    ])
    subprocess.check_call([str(binary)], timeout=10)
