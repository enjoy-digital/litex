#ifndef __WISHBONE_BURST_BENCHMARK_H
#define __WISHBONE_BURST_BENCHMARK_H

#include <stdbool.h>

void wishbone_burst_benchmark(unsigned int *addr, unsigned long size, bool read_only, bool random, bool finish);

#endif /* __WISHBONE_BURST_BENCHMARK_H */
