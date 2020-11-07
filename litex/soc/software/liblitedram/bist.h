// This file is Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#ifndef __SDRAM_BIST_H
#define __SDRAM_BIST_H

void sdram_bist_loop(uint32_t loop, uint32_t burst_length, uint32_t random);
void sdram_bist(uint32_t burst_length, uint32_t random);

#endif /* __SDRAM_BIST_H */
