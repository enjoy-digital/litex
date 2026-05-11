// SPDX-License-Identifier: BSD-Source-Code

#include <inttypes.h>
#include <stdio.h>

#include "format.h"

#define KIB 1024ULL
#define MIB (KIB*1024ULL)
#define GIB (MIB*1024ULL)

void litex_print_size(uint64_t size)
{
	if (size < KIB)
		printf("%" PRIu64 "B", size);
	else if (size < MIB)
		printf("%" PRIu64 ".%" PRIu64 "KiB", size/KIB, (size - KIB*(size/KIB))/(KIB/10));
	else if (size < GIB)
		printf("%" PRIu64 ".%" PRIu64 "MiB", size/MIB, (size/KIB - KIB*(size/MIB))/(KIB/10));
	else
		printf("%" PRIu64 ".%" PRIu64 "GiB", size/GIB, (size/MIB - KIB*(size/GIB))/(KIB/10));
}
