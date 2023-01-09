// This file is Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#ifndef __SDRAM_BIST_H
#define __SDRAM_BIST_H

#include <stdint.h>

void sdram_bist(uint32_t burst_length, uint32_t random);
int sdram_hw_test(uint64_t origin, uint64_t size, uint64_t burst_length);

#endif /* __SDRAM_BIST_H */
