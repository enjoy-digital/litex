/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

#ifndef __BIOS_NATIVE_DMA_TIMEOUT_H
#define __BIOS_NATIVE_DMA_TIMEOUT_H

#include <stdint.h>

#define NATIVE_DMA_HW_TIMEOUT_CYCLES 1000000000u
#define NATIVE_DMA_SETTLE_US         1000000u

/* Give the hardware two complete timeout intervals plus one second for CSR
 * synchronization and completion reporting. This deadline measures system
 * clock time rather than an arbitrary number of CPU polling iterations. */
static inline unsigned int native_dma_completion_timeout_us(void)
{
	uint64_t cycles = 2ull * NATIVE_DMA_HW_TIMEOUT_CYCLES;
	return (unsigned int)((cycles * 1000000ull + CONFIG_CLOCK_FREQUENCY - 1) /
		CONFIG_CLOCK_FREQUENCY + NATIVE_DMA_SETTLE_US);
}

#endif /* __BIOS_NATIVE_DMA_TIMEOUT_H */
