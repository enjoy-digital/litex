#ifndef __MEMTEST_H
#define __MEMTEST_H

#include <stdbool.h>

int memtest(unsigned int *addr, unsigned long maxsize);
void memspeed(unsigned int *addr, unsigned long size, bool read_only);

int memtest_addr(unsigned int *addr, unsigned long size, int random);
int memtest_data(unsigned int *addr, unsigned long size, int random);
int memtest_bus(unsigned int *addr, unsigned long size);

#endif /* __MEMTEST_H */
