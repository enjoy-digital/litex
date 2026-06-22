// This file is Copyright (c) 2023 Antmicro <www.antmicro.com>
// License: BSD

#ifndef __SDRAM_SPD_H
#define __SDRAM_SPD_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>
#include <libbase/i2c.h>

#include <generated/csr.h>

#if defined(CSR_SDRAM_BASE) && defined(CONFIG_HAS_I2C)

#include <generated/sdram_phy.h>

#define SPD_RW_PREAMBLE    0b1010
#define SPD_RW_ADDR(a210)  ((SPD_RW_PREAMBLE << 3) | ((a210) & 0b111))

#if defined(SDRAM_PHY_DDR4)
#define SDRAM_SPD_PAGES 2
#define SDRAM_SPD_PAGE_SIZE 256
#elif defined(SDRAM_PHY_DDR3)
#define SDRAM_SPD_PAGES 1
#define SDRAM_SPD_PAGE_SIZE 256
#else
#define SDRAM_SPD_PAGES 1
#define SDRAM_SPD_PAGE_SIZE 128
#endif

#define SDRAM_SPD_SIZE (SDRAM_SPD_PAGES * SDRAM_SPD_PAGE_SIZE)

#endif /* CSR_SDRAM_BASE && CONFIG_HAS_I2C */

bool sdram_read_spd(uint8_t spd, uint16_t addr, uint8_t *buf, uint16_t len);

#ifdef __cplusplus
}
#endif

#endif /* __SDRAM_SPD_H */
