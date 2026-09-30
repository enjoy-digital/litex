/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

#ifndef __USNATIVE_MAPPING_H
#define __USNATIVE_MAPPING_H

/* Generated logical indices are build products, never a physical device map.
 * A matching configuration identity binds this firmware to its gateware. */
#if !defined(SDRAM_PHY_USNATIVE_ABI_MAJOR) || SDRAM_PHY_USNATIVE_ABI_MAJOR != 1
#error "USNative firmware requires logical mapping ABI major 1"
#endif
#if !defined(CSR_DDRPHY_ABI_VERSION_ADDR) || !defined(CSR_DDRPHY_ABI_CONFIG_ID_ADDR) || !defined(CSR_DDRPHY_ABI_CAPABILITIES_ADDR)
#error "USNative firmware requires runtime mapping identity CSRs"
#endif
#if !defined(SDRAM_PHY_USNATIVE_REQUIRED_CAPS) || SDRAM_PHY_USNATIVE_REQUIRED_CAPS != 1u
#error "USNative mapping requires unsupported capabilities"
#endif
#if SDRAM_PHY_USNATIVE_DQ_TAPS_COUNT != 16 || SDRAM_PHY_USNATIVE_DQS_TAPS_COUNT != 2 || SDRAM_PHY_USNATIVE_DM_TAPS_COUNT != 2 || SDRAM_PHY_USNATIVE_CK_TAPS_COUNT != 1 || SDRAM_PHY_USNATIVE_LANE_COUNT != 2
#error "USNative training currently requires x16 DDR4, two byte lanes and one clock"
#endif
#if SDRAM_PHY_USNATIVE_TAP_COUNT < 21 || SDRAM_PHY_USNATIVE_CONTROL_COUNT < 1 || SDRAM_PHY_USNATIVE_CONTROL_COUNT > 32 || SDRAM_PHY_USNATIVE_DATA_CONTROLS_COUNT < 1
#error "USNative mapping has invalid resource counts"
#endif
#define USNATIVE_CONTROL_MASK (0xffffffffu >> (32 - SDRAM_PHY_USNATIVE_CONTROL_COUNT))
static const unsigned usnative_dq_taps[] = SDRAM_PHY_USNATIVE_DQ_TAPS;
static const unsigned usnative_dqs_taps[] = SDRAM_PHY_USNATIVE_DQS_TAPS;
static const unsigned usnative_dm_taps[] = SDRAM_PHY_USNATIVE_DM_TAPS;
static const unsigned usnative_ck_taps[] = SDRAM_PHY_USNATIVE_CK_TAPS;
static const unsigned usnative_data_controls[] = SDRAM_PHY_USNATIVE_DATA_CONTROLS;
#define USNATIVE_ARRAY_COUNT(a) (sizeof(a) / sizeof((a)[0]))

static int usnative_mapping_validate(void)
{
    unsigned version = ddrphy_abi_version_read();
    if ((version >> 16) != SDRAM_PHY_USNATIVE_ABI_MAJOR ||
        (version & 0xffffu) < SDRAM_PHY_USNATIVE_ABI_MINOR ||
        ddrphy_abi_config_id_read() != SDRAM_PHY_USNATIVE_CONFIG_ID ||
        (ddrphy_abi_capabilities_read() & SDRAM_PHY_USNATIVE_REQUIRED_CAPS) != SDRAM_PHY_USNATIVE_REQUIRED_CAPS)
        return 0;
    if (USNATIVE_ARRAY_COUNT(usnative_dq_taps) != SDRAM_PHY_USNATIVE_DQ_TAPS_COUNT ||
        USNATIVE_ARRAY_COUNT(usnative_dqs_taps) != SDRAM_PHY_USNATIVE_DQS_TAPS_COUNT ||
        USNATIVE_ARRAY_COUNT(usnative_dm_taps) != SDRAM_PHY_USNATIVE_DM_TAPS_COUNT ||
        USNATIVE_ARRAY_COUNT(usnative_ck_taps) != SDRAM_PHY_USNATIVE_CK_TAPS_COUNT ||
        USNATIVE_ARRAY_COUNT(usnative_data_controls) != SDRAM_PHY_USNATIVE_DATA_CONTROLS_COUNT)
        return 0;
    /* DQ, strobe, mask and clock taps must be distinct and in range. */
    unsigned taps[21], count = 0;
    for (unsigned i=0; i<16; ++i) taps[count++] = usnative_dq_taps[i];
    for (unsigned i=0; i<2; ++i) taps[count++] = usnative_dqs_taps[i];
    for (unsigned i=0; i<2; ++i) taps[count++] = usnative_dm_taps[i];
    taps[count++] = usnative_ck_taps[0];
    for (unsigned i=0; i<count; ++i) {
        if (taps[i] >= SDRAM_PHY_USNATIVE_TAP_COUNT) return 0;
        for (unsigned j=0; j<i; ++j) if (taps[i] == taps[j]) return 0;
    }
    for (unsigned i=0; i<USNATIVE_ARRAY_COUNT(usnative_data_controls); ++i) {
        if (usnative_data_controls[i] >= SDRAM_PHY_USNATIVE_CONTROL_COUNT) return 0;
        for (unsigned j=0; j<i; ++j)
            if (usnative_data_controls[i] == usnative_data_controls[j]) return 0;
    }
    return 1;
}
#endif
