#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

"""Keep UltraScale failure propagation separate from legacy PHY training."""

import unittest

from test.software import test_usnative as firmware
from test.software.test_usnative_retry import function


@unittest.skipUnless(firmware.CC, "Host C compiler required")
class TestComponentLevelingCompatibility(unittest.TestCase):
    compile_run = firmware.TestUSNativeFirmware.compile_run

    def test_write_leveling_failure_scope(self):
        body = function(firmware.ROOT / "litex/soc/software/liblitedram/sdram.c",
                        "int sdram_leveling(void)")
        for phy, fail_closed in (("USDDRPHY", True), ("USPDDRPHY", True),
                                 ("LPDDR5SIMPHY", False), ("S7DDRPHY", False)):
            with self.subTest(phy=phy):
                self.compile_run("#define SDRAM_PHY_" + phy + "\n" +
                                 "#define FAIL_CLOSED " + str(int(fail_closed)) + "\n" + r'''
#include <assert.h>
#include <stdio.h>
#define SDRAM_PHY_MODULES 2
#define DQ_COUNT 1
#define SDRAM_PHY_WRITE_LEVELING_CAPABLE
#define SDRAM_PHY_READ_LEVELING_CAPABLE
static int write_result, writes, reads, software_on, software_off, resets;
static void sdram_software_control_on(void) {++software_on;}
static void sdram_software_control_off(void) {++software_off;}
static void write_rst_delay(int module) {(void)module; ++resets;}
static void read_rst_dq_delay(int module) {(void)module; ++resets;}
static void sdram_leveling_action(int module, int dq, void (*action)(int)) {
 (void)dq; action(module);
}
static int sdram_write_leveling(void) {++writes; return write_result;}
static void sdram_read_leveling(void) {++reads;}
''' + body + r'''
int main(void) {
 for (write_result=0; write_result<2; ++write_result) {
  writes=reads=software_on=software_off=resets=0;
  int expected=write_result || !FAIL_CLOSED;
  assert(sdram_leveling()==expected);
  assert(writes==1 && reads==expected);
  assert(software_on==1 && software_off==1);
  assert(resets==4);
 }
 return 0;
}
''')
