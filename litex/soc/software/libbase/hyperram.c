// This file is Copyright (c) 2024 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#include <stdio.h>

#include <libbase/hyperram.h>

#include <generated/csr.h>

#ifdef CSR_HYPERRAM_BASE

static void hyperram_write_reg(uint16_t reg_addr, uint16_t data) {
    /* Write data to the register */
    hyperram_reg_wdata_write(data);
    hyperram_reg_control_write(
        1        << CSR_HYPERRAM_REG_CONTROL_WRITE_OFFSET |
        0        << CSR_HYPERRAM_REG_CONTROL_READ_OFFSET  |
        reg_addr << CSR_HYPERRAM_REG_CONTROL_ADDR_OFFSET
    );
    /* Wait for write to complete */
    while ((hyperram_reg_status_read() & (1 << CSR_HYPERRAM_REG_STATUS_DONE_OFFSET)) == 0);
 }

static uint16_t hyperram_read_reg(uint16_t reg_addr) {
    /* Read data from the register */
    hyperram_reg_control_write(
        0        << CSR_HYPERRAM_REG_CONTROL_WRITE_OFFSET |
        1        << CSR_HYPERRAM_REG_CONTROL_READ_OFFSET  |
        reg_addr << CSR_HYPERRAM_REG_CONTROL_ADDR_OFFSET
    );
    /* Wait for read to complete */
    while ((hyperram_reg_status_read() & (1 << CSR_HYPERRAM_REG_STATUS_DONE_OFFSET)) == 0);
    return hyperram_reg_rdata_read();
}

/* Configuration and Utility Functions */

static uint16_t hyperram_get_core_latency_setting(uint32_t clk_freq) {
    /* Raw clock latency settings for the HyperRAM core */
    if (clk_freq <=  85000000) return 3; /* 3 Clock Latency */
    if (clk_freq <= 104000000) return 4; /* 4 Clock Latency */
    if (clk_freq <= 133000000) return 5; /* 5 Clock Latency */
    if (clk_freq <= 166000000) return 6; /* 6 Clock Latency */
    if (clk_freq <= 250000000) return 7; /* 7 Clock Latency */
    return 7; /* Default to highest latency for safety */
}

static uint16_t hyperram_get_chip_latency_setting(uint32_t clk_freq) {
    /* LUT/Translated settings for the HyperRAM chip */
    if (clk_freq <=  85000000) return 0b1110; /* 3 Clock Latency */
    if (clk_freq <= 104000000) return 0b1111; /* 4 Clock Latency */
    if (clk_freq <= 133000000) return 0b0000; /* 5 Clock Latency */
    if (clk_freq <= 166000000) return 0b0001; /* 6 Clock Latency */
    if (clk_freq <= 250000000) return 0b0010; /* 7 Clock Latency */
    return 0b0010; /* Default to highest latency for safety */
}

static uint16_t hyperram_get_chip_latency_setting_from_latency(uint16_t latency) {
    switch (latency) {
        case 3: return HYPERRAM_CONFIG_0_REG_IL_3_CLOCKS;
        case 4: return HYPERRAM_CONFIG_0_REG_IL_4_CLOCKS;
        case 5: return HYPERRAM_CONFIG_0_REG_IL_5_CLOCKS;
        case 6: return HYPERRAM_CONFIG_0_REG_IL_6_CLOCKS;
        case 7: return HYPERRAM_CONFIG_0_REG_IL_7_CLOCKS;
        default: return HYPERRAM_CONFIG_0_REG_IL_7_CLOCKS;
    }
}

static uint16_t hyperram_get_chip_drive_strength_setting(uint16_t drive_strength_ohms) {
    switch (drive_strength_ohms) {
        case  34: return HYPERRAM_CONFIG_0_REG_DS_34_OHM;
        case 115: return HYPERRAM_CONFIG_0_REG_DS_115_OHM;
        case  67: return HYPERRAM_CONFIG_0_REG_DS_67_OHM;
        case  46: return HYPERRAM_CONFIG_0_REG_DS_46_OHM;
        case  27: return HYPERRAM_CONFIG_0_REG_DS_27_OHM;
        case  22: return HYPERRAM_CONFIG_0_REG_DS_22_OHM;
        case  19: return HYPERRAM_CONFIG_0_REG_DS_19_OHM;
        default: return HYPERRAM_CONFIG_0_REG_DS_19_OHM;
    }
}

void hyperram_init(void) {
    uint16_t config_reg_0;
    uint8_t  core_clk_ratio;
    uint8_t  core_latency_mode;
    uint16_t core_latency_setting;
    uint16_t chip_latency_setting;
    uint16_t drive_strength_ohms;
    uint16_t drive_strength_setting;

    printf("HyperRAM init...\n");

    /* Compute Latency settings */
    core_clk_ratio  = (hyperram_status_read() >> CSR_HYPERRAM_STATUS_CLK_RATIO_OFFSET) & 0xf;
    printf("HyperRAM Clk Ratio %d:1\n", core_clk_ratio);
    core_latency_setting = hyperram_get_core_latency_setting(CONFIG_CLOCK_FREQUENCY / core_clk_ratio);
    chip_latency_setting = hyperram_get_chip_latency_setting(CONFIG_CLOCK_FREQUENCY / core_clk_ratio);

#ifdef CONFIG_HYPERRAM_INIT_LATENCY
    core_latency_setting = CONFIG_HYPERRAM_INIT_LATENCY;
    chip_latency_setting = hyperram_get_chip_latency_setting_from_latency(core_latency_setting);
#endif

    drive_strength_ohms    = 19;
    drive_strength_setting = HYPERRAM_CONFIG_0_REG_DS_19_OHM;
#ifdef CONFIG_HYPERRAM_INIT_DRIVE_STRENGTH
    drive_strength_ohms    = CONFIG_HYPERRAM_INIT_DRIVE_STRENGTH;
    drive_strength_setting = hyperram_get_chip_drive_strength_setting(drive_strength_ohms);
#endif

    /* Configure Latency on HyperRAM Core */
    core_latency_mode = (hyperram_status_read() >> CSR_HYPERRAM_STATUS_LATENCY_MODE_OFFSET) & 0b1;
    printf("HyperRAM %s Latency: %d CK (X1)\n", (core_latency_mode == 0) ? "Fixed" : "Variable", core_latency_setting);
    hyperram_config_write(core_latency_setting << CSR_HYPERRAM_CONFIG_LATENCY_OFFSET);
    printf("HyperRAM Drive Strength: %d ohm\n", drive_strength_ohms);

    /* Configure HyperRAM Chip */
    config_reg_0 = (
        /* Burst Length */
        (HYPERRAM_CONFIG_0_REG_BL_32_BYTES        << HYPERRAM_CONFIG_0_REG_BL_OFFSET)   |

        /* Hybrid Burst Enable */
        (HYPERRAM_CONFIG_0_REG_HBE_LEGACY         << HYPERRAM_CONFIG_0_REG_HBE_OFFSET)  |

        /* Initial Latency */
        (chip_latency_setting                     << HYPERRAM_CONFIG_0_REG_IL_OFFSET)   |

        /* Fixed Latency Enable */
        (HYPERRAM_CONFIG_0_REG_FLE_ENABLED        << HYPERRAM_CONFIG_0_REG_FLE_OFFSET)  |

        /* Reserved Bits (Set to 1 for future compatibility) */
        (0b1111                                   << HYPERRAM_CONFIG_0_REG_RSD_OFFSET) |

        /* Drive Strength */
        (drive_strength_setting                   << HYPERRAM_CONFIG_0_REG_DS_OFFSET)   |

        /* Deep Power Down: Normal operation */
        (HYPERRAM_CONFIG_0_REG_DPD_DISABLED       << HYPERRAM_CONFIG_0_REG_DPD_OFFSET)
    );
    /* Enable Variable Latency on HyperRAM Chip */
    if (hyperram_status_read() & 0x1) {
        config_reg_0 &= ~(1                                  << HYPERRAM_CONFIG_0_REG_FLE_OFFSET);
        config_reg_0 |=  (HYPERRAM_CONFIG_0_REG_FLE_DISABLED << HYPERRAM_CONFIG_0_REG_FLE_OFFSET);
    }
    hyperram_write_reg(HYPERRAM_CONFIG_0_REG, config_reg_0);

    /* Read current configuration to verify changes */
    config_reg_0 = hyperram_read_reg(HYPERRAM_CONFIG_0_REG);
    printf("HyperRAM Configuration Register 0: %04x\n", config_reg_0);
    printf("\n");
}

#endif