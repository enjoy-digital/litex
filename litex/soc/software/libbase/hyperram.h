// This file is Copyright (c) 2024 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#ifndef __HYPERRAM_H
#define __HYPERRAM_H

#ifdef __cplusplus
extern "C" {
#endif

/* HyperRAM Registers */
#define HYPERRAM_ID_0_REG     0x0  /* Identification Register 0 */
#define HYPERRAM_ID_1_REG     0x1  /* Identification Register 1 */
#define HYPERRAM_CONFIG_0_REG 0x2  /* Configuration Register 0  */
#define HYPERRAM_CONFIG_1_REG 0x3  /* Configuration Register 1  */

/* Configuration Register 0 Field Offsets */
#define HYPERRAM_CONFIG_0_REG_BL_OFFSET     0  /* Burst Length         */
#define HYPERRAM_CONFIG_0_REG_HBE_OFFSET    2  /* Hybrid Burst Enable  */
#define HYPERRAM_CONFIG_0_REG_FLE_OFFSET    3  /* Fixed Latency Enable */
#define HYPERRAM_CONFIG_0_REG_IL_OFFSET     4  /* Initial Latency      */
#define HYPERRAM_CONFIG_0_REG_RSD_OFFSET    8  /* Reserved bits        */
#define HYPERRAM_CONFIG_0_REG_DS_OFFSET     12 /* Drive Strength       */
#define HYPERRAM_CONFIG_0_REG_DPD_OFFSET    15 /* Deep Power Down      */

/* Configuration Register 0 Field Values */

/* Burst Length */
#define HYPERRAM_CONFIG_0_REG_BL_128_BYTES  0b00
#define HYPERRAM_CONFIG_0_REG_BL_64_BYTES   0b01
#define HYPERRAM_CONFIG_0_REG_BL_16_BYTES   0b10
#define HYPERRAM_CONFIG_0_REG_BL_32_BYTES   0b11

/* Hybrid Burst Enable */
#define HYPERRAM_CONFIG_0_REG_HBE_WRAPPED   0b0
#define HYPERRAM_CONFIG_0_REG_HBE_LEGACY    0b1

/* Fixed Latency Enable */
#define HYPERRAM_CONFIG_0_REG_FLE_DISABLED  0b0
#define HYPERRAM_CONFIG_0_REG_FLE_ENABLED   0b1

/* Initial Latency */
#define HYPERRAM_CONFIG_0_REG_IL_3_CLOCKS   0b1110
#define HYPERRAM_CONFIG_0_REG_IL_4_CLOCKS   0b1111
#define HYPERRAM_CONFIG_0_REG_IL_5_CLOCKS   0b0000
#define HYPERRAM_CONFIG_0_REG_IL_6_CLOCKS   0b0001
#define HYPERRAM_CONFIG_0_REG_IL_7_CLOCKS   0b0010

/* Drive Strength */
#define HYPERRAM_CONFIG_0_REG_DS_34_OHM     0b000
#define HYPERRAM_CONFIG_0_REG_DS_115_OHM    0b001
#define HYPERRAM_CONFIG_0_REG_DS_67_OHM     0b010
#define HYPERRAM_CONFIG_0_REG_DS_46_OHM     0b011
#define HYPERRAM_CONFIG_0_REG_DS_27_OHM     0b101
#define HYPERRAM_CONFIG_0_REG_DS_22_OHM     0b110
#define HYPERRAM_CONFIG_0_REG_DS_19_OHM     0b111

/* Deep Power Down */
#define HYPERRAM_CONFIG_0_REG_DPD_DISABLED  0b1
#define HYPERRAM_CONFIG_0_REG_DPD_ENABLED   0b0

void hyperram_init(void);

#ifdef __cplusplus
}
#endif

#endif /* __HYPERRAM_H */
