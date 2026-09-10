# SPDX-License-Identifier: BSD-2-Clause

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("with_direction", [False, True])
def test_read_delay_reset_and_scan(tmp_path, with_direction):
    repo = Path(__file__).resolve().parents[2]
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "csr.h").write_text("""
#define CSR_SDRAM_BASE 1
#define CSR_DDRPHY_BASE 1
void ddrphy_dly_sel_write(unsigned int value);
void ddrphy_rdly_dq_rst_write(unsigned int value);
void ddrphy_rdly_dq_inc_write(unsigned int value);
void ddrphy_rdly_dq_dir_write(unsigned int value);
void cdelay(int cycles);
""")
    (generated / "sdram_phy.h").write_text("""
#define SDRAM_PHY_READ_LEVELING_CAPABLE
#define SDRAM_PHY_GW5DDRPHY
#define SDRAM_PHY_MODULES 2
#define SDRAM_PHY_DELAYS 256
""")
    source = tmp_path / "delay.c"
    source.write_text(r'''
#include <assert.h>
#include <liblitedram/accessors.h>

static unsigned int selected, direction, dll_value;
static int delay[2];

void ddrphy_dly_sel_write(unsigned int value) { selected = value; }
void cdelay(int cycles) { }
void ddrphy_rdly_dq_dir_write(unsigned int value) { direction = value; }
void ddrphy_rdly_dq_rst_write(unsigned int value) {
    for (int lane = 0; lane < 2; lane++) {
        if (selected & (1 << lane)) {
#ifdef MODEL_HAS_DIRECTION
            delay[lane] = dll_value;
#else
            delay[lane] = 0;
#endif
        }
    }
}
void ddrphy_rdly_dq_inc_write(unsigned int value) {
    for (int lane = 0; lane < 2; lane++) {
        if (selected & (1 << lane)) {
            if (direction && delay[lane] > 0)
                delay[lane]--;
            if (!direction && delay[lane] < 255)
                delay[lane]++;
        }
    }
}

int main(void) {
    for (dll_value = 0; dll_value < 256; dll_value++) {
        for (int lane = 0; lane < 2; lane++) {
            delay[1 - lane] = 123;
            sdram_leveling_action(lane, 0, read_rst_dq_delay);
            assert(direction == 0);
            for (int tap = 0; tap < 256; tap++) {
                assert(read_dq_delay[lane] == tap);
                assert(delay[lane] == tap);
                assert(delay[1 - lane] == 123);
                if (tap < 255)
                    sdram_leveling_action(lane, 0, read_inc_dq_delay);
            }
        }
    }
    return 0;
}
''')
    binary = tmp_path / "delay"
    flags = ["-DCSR_DDRPHY_RDLY_DQ_DIR_ADDR=1", "-DMODEL_HAS_DIRECTION=1"] if with_direction else []
    subprocess.check_call([
        "gcc", "-std=gnu99", "-Wall", "-Werror", *flags,
        f"-I{tmp_path}", f"-I{repo}/litex/soc/software", str(source),
        str(repo / "litex/soc/software/liblitedram/accessors.c"), "-o", str(binary),
    ])
    subprocess.check_call([str(binary)])
