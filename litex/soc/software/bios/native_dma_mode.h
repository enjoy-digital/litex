/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

#ifndef __BIOS_NATIVE_DMA_MODE_H
#define __BIOS_NATIVE_DMA_MODE_H

#ifdef CONFIG_SDRAM_NATIVE_DMA_BANK_GROUP_INTERLEAVING
#define NATIVE_DMA_MODE_NAME "paired-bank-group-interleaved"
#define NATIVE_DMA_BANK_GROUP_INTERLEAVED 1
#else
#define NATIVE_DMA_MODE_NAME "standard-native-port"
#define NATIVE_DMA_BANK_GROUP_INTERLEAVED 0
#endif

#endif
