#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

"""Execute ABI admission against synthetic logical maps, never queried pins."""

import unittest
from test.software import test_usnative as firmware

DESCRIPTOR = r"""
#include <assert.h>
#define SDRAM_PHY_USNATIVE_ABI_MAJOR 1
#define SDRAM_PHY_USNATIVE_ABI_MINOR 0
#define SDRAM_PHY_USNATIVE_CONFIG_ID 0x12345678u
#define SDRAM_PHY_USNATIVE_REQUIRED_CAPS 1
#define SDRAM_PHY_USNATIVE_DQ_TAPS_COUNT 16
#define SDRAM_PHY_USNATIVE_DQS_TAPS_COUNT 2
#define SDRAM_PHY_USNATIVE_DM_TAPS_COUNT 2
#define SDRAM_PHY_USNATIVE_CK_TAPS_COUNT 1
#define SDRAM_PHY_USNATIVE_LANE_COUNT 2
#define SDRAM_PHY_USNATIVE_TAP_COUNT 45
#define SDRAM_PHY_USNATIVE_CONTROL_COUNT 8
#define SDRAM_PHY_USNATIVE_DATA_CONTROLS_COUNT 4
#define SDRAM_PHY_USNATIVE_DQ_TAPS {7,6,5,4,3,2,1,0,15,14,13,12,11,10,9,8}
#define SDRAM_PHY_USNATIVE_DQS_TAPS {16,17}
#define SDRAM_PHY_USNATIVE_DM_TAPS {18,19}
#define SDRAM_PHY_USNATIVE_CK_TAPS {20}
#define SDRAM_PHY_USNATIVE_DATA_CONTROLS {7,5,3,1}
#define CSR_DDRPHY_ABI_VERSION_ADDR 1
#define CSR_DDRPHY_ABI_CONFIG_ID_ADDR 1
#define CSR_DDRPHY_ABI_CAPABILITIES_ADDR 1
static unsigned version=0x10000, identity=0x12345678, caps=1;
static unsigned ddrphy_abi_version_read(void) {return version;}
static unsigned ddrphy_abi_config_id_read(void) {return identity;}
static unsigned ddrphy_abi_capabilities_read(void) {return caps;}
"""

@unittest.skipUnless(firmware.CC, "Host C compiler required")
class TestUSNativeMapping(unittest.TestCase):
    compile_run = firmware.TestUSNativeFirmware.compile_run

    def test_runtime_identity_version_and_capabilities(self):
        self.compile_run(DESCRIPTOR + r'''
#include "mapping.h"
int main(void) {
 assert(usnative_mapping_validate());
 assert(usnative_dq_taps[0]==7 && usnative_ck_taps[0]==20);
 assert(usnative_data_controls[0]==7 && USNATIVE_CONTROL_MASK==255);
 version=0x20000; assert(!usnative_mapping_validate());
 version=0x10001; assert(usnative_mapping_validate());
 identity++; assert(!usnative_mapping_validate());
 identity--; caps=0; assert(!usnative_mapping_validate());
 caps=3; assert(usnative_mapping_validate());
 return 0;
}
''')

    def test_reject_stale_unknown_and_unsupported_descriptors(self):
        changes = (
            "#undef SDRAM_PHY_USNATIVE_REQUIRED_CAPS\n#define SDRAM_PHY_USNATIVE_REQUIRED_CAPS 0",
            "#undef SDRAM_PHY_USNATIVE_ABI_MAJOR",
            "#undef SDRAM_PHY_USNATIVE_ABI_MAJOR\n#define SDRAM_PHY_USNATIVE_ABI_MAJOR 2",
            "#undef SDRAM_PHY_USNATIVE_REQUIRED_CAPS\n#define SDRAM_PHY_USNATIVE_REQUIRED_CAPS 3",
            "#undef SDRAM_PHY_USNATIVE_DQ_TAPS_COUNT\n#define SDRAM_PHY_USNATIVE_DQ_TAPS_COUNT 32",
            "#undef CSR_DDRPHY_ABI_VERSION_ADDR",
        )
        for change in changes:
            with self.subTest(change=change):
                self.compile_run(DESCRIPTOR + change + '\n#include "mapping.h"\nint main(void) {return 0;}', False)

    def test_reject_malformed_mapping_before_training(self):
        changes = (
            "#undef SDRAM_PHY_USNATIVE_CK_TAPS\n#define SDRAM_PHY_USNATIVE_CK_TAPS {0}",
            "#undef SDRAM_PHY_USNATIVE_CK_TAPS\n#define SDRAM_PHY_USNATIVE_CK_TAPS {45}",
            "#undef SDRAM_PHY_USNATIVE_CK_TAPS\n#define SDRAM_PHY_USNATIVE_CK_TAPS {20,21}",
            "#undef SDRAM_PHY_USNATIVE_DATA_CONTROLS\n#define SDRAM_PHY_USNATIVE_DATA_CONTROLS {0,1,2,8}",
            "#undef SDRAM_PHY_USNATIVE_DATA_CONTROLS\n#define SDRAM_PHY_USNATIVE_DATA_CONTROLS {0,1,2,2}",
        )
        for change in changes:
            with self.subTest(change=change):
                self.compile_run(DESCRIPTOR + change + '\n#include "mapping.h"\nint main(void) {assert(!usnative_mapping_validate());return 0;}')
