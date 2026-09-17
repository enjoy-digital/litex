# SPDX-License-Identifier: BSD-2-Clause

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("with_direction", [False, True])
@pytest.mark.parametrize("write", [False, True])
def test_delay_reset_and_scan(tmp_path, with_direction, write):
    repo = Path(__file__).resolve().parents[2]
    prefix = "write" if write else "read"
    csr = "wdly" if write else "rdly"
    capability = "WRITE_DQ_DQS_TRAINING" if write else "READ_LEVELING"
    direction_macro = f"CSR_DDRPHY_{csr.upper()}_DQ_DIR_ADDR"
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "csr.h").write_text(f"""
#define CSR_SDRAM_BASE 1
#define CSR_DDRPHY_BASE 1
void ddrphy_dly_sel_write(unsigned int value);
void ddrphy_{csr}_dq_rst_write(unsigned int value);
void ddrphy_{csr}_dq_inc_write(unsigned int value);
void ddrphy_{csr}_dq_dir_write(unsigned int value);
void cdelay(int cycles);
""")
    (generated / "sdram_phy.h").write_text(f"""
#define SDRAM_PHY_{capability}_CAPABLE
#define SDRAM_PHY_GW5DDRPHY
#define SDRAM_PHY_MODULES 2
#define SDRAM_PHY_DELAYS 256
""")
    source = tmp_path / "delay.c"
    source.write_text(f"""
#define phy_set_direction ddrphy_{csr}_dq_dir_write
#define phy_reset_delay ddrphy_{csr}_dq_rst_write
#define phy_inc_delay ddrphy_{csr}_dq_inc_write
#define reset_delay {prefix}_rst_dq_delay
#define inc_delay {prefix}_inc_dq_delay
#define software_delay {prefix}_dq_delay
""" + r'''
#include <assert.h>
#include <liblitedram/accessors.h>

static unsigned int selected, direction, dll_value;
static int delay[2];

void ddrphy_dly_sel_write(unsigned int value) { selected = value; }
void cdelay(int cycles) { }
void phy_set_direction(unsigned int value) { direction = value; }
void phy_reset_delay(unsigned int value) {
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
void phy_inc_delay(unsigned int value) {
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
            sdram_leveling_action(lane, 0, reset_delay);
            assert(direction == 0);
            for (int tap = 0; tap < 256; tap++) {
                assert(software_delay[lane] == tap);
                assert(delay[lane] == tap);
                assert(delay[1 - lane] == 123);
                if (tap < 255)
                    sdram_leveling_action(lane, 0, inc_delay);
            }
        }
    }
    return 0;
}
''')
    binary = tmp_path / "delay"
    flags = [f"-D{direction_macro}=1", "-DMODEL_HAS_DIRECTION=1"] if with_direction else []
    subprocess.check_call([
        "gcc", "-std=gnu99", "-Wall", "-Werror", *flags,
        f"-I{tmp_path}", f"-I{repo}/litex/soc/software", str(source),
        str(repo / "litex/soc/software/liblitedram/accessors.c"), "-o", str(binary),
    ])
    subprocess.check_call([str(binary)])


def test_ultrascale_dqs_wrap_from_zero_and_nonzero_count(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "csr.h").write_text(r"""
#define CSR_SDRAM_BASE 1
#define CSR_DDRPHY_BASE 1
void ddrphy_dly_sel_write(unsigned int value);
void ddrphy_wdly_dq_inc_write(unsigned int value);
void ddrphy_wdly_dqs_inc_write(unsigned int value);
unsigned int ddrphy_wdly_dqs_inc_count_read(void);
void ddrphy_cdly_inc_write(unsigned int value);
void ddrphy_cdly_rst_write(unsigned int value);
void cdelay(int cycles);
""")
    (generated / "sdram_phy.h").write_text(r"""
#define SDRAM_PHY_WRITE_LEVELING_CAPABLE
#define SDRAM_PHY_USPDDRPHY
#define SDRAM_PHY_MODULES 2
#define SDRAM_PHY_DELAYS 512
""")
    source = tmp_path / "dqs_wrap.c"
    source.write_text(r"""
#include <assert.h>
#include <liblitedram/accessors.h>
static unsigned selected, count[2], increments[2], stuck;
void cdelay(int cycles) {(void)cycles;}
void ddrphy_dly_sel_write(unsigned value) {selected=value;}
void ddrphy_wdly_dq_inc_write(unsigned value) {(void)value;}
void ddrphy_cdly_inc_write(unsigned value) {(void)value;}
void ddrphy_cdly_rst_write(unsigned value) {(void)value;}
unsigned ddrphy_wdly_dqs_inc_count_read(void) {
 for (unsigned i=0;i<2;i++) if (selected & (1u<<i)) return count[i];
 return 0;
}
void ddrphy_wdly_dqs_inc_write(unsigned value) {
 (void)value;
 for (unsigned i=0;i<2;i++) if (selected & (1u<<i)) {
  if (!stuck) count[i]=(count[i]+1)&511;
  increments[i]++;
 }
}
int main(void) {
 sdram_leveling_action(0, 0, write_rst_dqs_delay);
 assert(count[0]==0 && increments[0]==0);
 count[1]=37;
 sdram_leveling_action(1, 0, write_rst_dqs_delay);
 assert(count[1]==0 && increments[1]==512-37);
 assert(count[0]==0 && increments[0]==0);
 count[0]=37; stuck=1;
 sdram_select(0, 0);
 assert(!write_rst_dqs_delay_checked(0));
 sdram_deselect(0, 0);
 assert(count[0]==37 && increments[0]==512);
 return 0;
}
""")
    binary = tmp_path / "dqs_wrap"
    subprocess.check_call([
        "gcc", "-std=gnu99", "-Wall", "-Werror",
        f"-I{tmp_path}", f"-I{repo}/litex/soc/software", str(source),
        str(repo / "litex/soc/software/liblitedram/accessors.c"), "-o", str(binary),
    ])
    subprocess.check_call([str(binary)])
