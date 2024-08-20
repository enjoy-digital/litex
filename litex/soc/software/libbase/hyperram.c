// This file is Copyright (c) 2024 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#include <stdio.h>

#include <libbase/hyperram.h>

#include <generated/csr.h>

static void hyperram_write_reg(uint16_t reg_addr, uint16_t data) {
    /* Write data to the register */
    hyperram_reg_wdata_write(data);
    hyperram_reg_control_write(
        1        << CSR_HYPERRAM_REG_CONTROL_WRITE_OFFSET |
        0        << CSR_HYPERRAM_REG_CONTROL_READ_OFFSET  |
        reg_addr << CSR_HYPERRAM_REG_CONTROL_ADDR_OFFSET
    );
    /* Wait for write to complete */
    while ((hyperram_reg_status_read() & (1 << CSR_HYPERRAM_REG_STATUS_WRITE_DONE_OFFSET)) == 0);
 }

static uint16_t hyperram_read_reg(uint16_t reg_addr) {
    /* Read data from the register */
    hyperram_reg_control_write(
        0        << CSR_HYPERRAM_REG_CONTROL_WRITE_OFFSET |
        1        << CSR_HYPERRAM_REG_CONTROL_READ_OFFSET  |
        reg_addr << CSR_HYPERRAM_REG_CONTROL_ADDR_OFFSET
    );
    /* Wait for read to complete */
    while ((hyperram_reg_status_read() & (1 << CSR_HYPERRAM_REG_STATUS_READ_DONE_OFFSET)) == 0);
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

static void hyperram_configure_latency(void) {
    uint16_t config_reg_0 = 0x8f2f;
    uint16_t core_latency_setting;
    uint16_t chip_latency_setting;

    /* Compute Latency settings */
    core_latency_setting = hyperram_get_core_latency_setting(CONFIG_CLOCK_FREQUENCY/4);
    chip_latency_setting = hyperram_get_chip_latency_setting(CONFIG_CLOCK_FREQUENCY/4);

    /* Write Latency to HyperRAM Core */
    printf("HyperRAM Core Latency: %d CK (X1).\n", core_latency_setting);
    hyperram_config_write(core_latency_setting << CSR_HYPERRAM_CONFIG_LATENCY_OFFSET);

    /* Enable Variable Latency on HyperRAM Chip */
    if (hyperram_status_read() & 0x1)
        config_reg_0 &= ~(0b1 << 3); /* Enable Variable Latency */

    /* Update Latency on HyperRAM Chip */
    config_reg_0 &= ~(0b1111 << 4);
    config_reg_0 |= chip_latency_setting << 4;

    /* Write Configuration Register 0 to HyperRAM Chip */
    hyperram_write_reg(2, config_reg_0);

    /* Read current configuration */
    config_reg_0 = hyperram_read_reg(2);
    printf("HyperRAM Configuration Register 0: %08x\n", config_reg_0);
}

void hyperram_init(void) {
	printf("HyperRAM init...\n");
	hyperram_configure_latency();
	printf("\n");
}
