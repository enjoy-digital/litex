// This file is Copyright (c) 2023 Antmicro <www.antmicro.com>
// License: BSD

#include <stdio.h>

#include <liblitedram/utils.h>

#define KIB 1024
#define MIB (KIB*1024)
#define GIB (MIB*1024)

void print_size(uint64_t size) {
	if (size < KIB)
		printf("%lluB", size);
	else if (size < MIB)
		printf("%llu.%lluKiB", size/KIB, (size/1   - KIB*(size/KIB))/(KIB/10));
	else if (size < GIB)
		printf("%llu.%lluMiB", size/MIB, (size/KIB - KIB*(size/MIB))/(KIB/10));
	else
		printf("%llu.%lluGiB", size/GIB, (size/MIB - KIB*(size/GIB))/(KIB/10));
}

void print_progress(const char * header, uint64_t origin, uint64_t size)
{
	printf("%s 0x%llx-0x%llx ", header, origin, origin + size);
	print_size(size);
	printf("   \r");
}
