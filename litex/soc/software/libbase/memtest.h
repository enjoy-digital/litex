#ifndef __MEMTEST_H
#define __MEMTEST_H

#include <stdbool.h>

// Called when an error is encountered. Can return non-zero to stop the memtest.
// `arg` can be used to pass arbitrary data to the callback via `memtest_config.arg`.
typedef int (*on_error_callback)(unsigned int addr, unsigned int rdata, unsigned int refdata, void *arg);

// Optional memtest configuration. If NULL, then we default to progress=1, read_only=0.
struct memtest_config {
	int show_progress;
	int read_only;
	on_error_callback on_error;
	void *arg;
};

int memtest_access(unsigned int *addr);
int memtest_bus(unsigned int *addr, unsigned long size);
int memtest_addr(unsigned int *addr, unsigned long size, int random);
int memtest_data(unsigned int *addr, unsigned long size, int random, struct memtest_config *config);

void memspeed(unsigned int *addr, unsigned long size, bool read_only, bool random);
int memtest(unsigned int *addr, unsigned long maxsize);

#endif /* __MEMTEST_H */
