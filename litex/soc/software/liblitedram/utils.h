// This file is Copyright (c) 2023 Antmicro <www.antmicro.com>
// License: BSD

#ifndef __SDRAM_UTILS_H
#define __SDRAM_UTILS_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

void print_size(uint64_t size);
void print_progress(const char * header, uint64_t origin, uint64_t size);

uint64_t sdram_get_supported_memory(void);

#ifdef __cplusplus
}
#endif

#endif /* __SDRAM_UTILS_H */
