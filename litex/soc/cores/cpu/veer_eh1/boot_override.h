#ifndef VEER_BOOT_OVERRIDE_H
#define VEER_BOOT_OVERRIDE_H

#define BOOT_LOAD_MAX_SIZE_OVERRIDDEN

#ifndef __ASSEMBLER__

#include <stddef.h>
#include <stdio.h>

#if defined(MAIN_RAM_BASE) || defined(MAIN_RAM_BASE_VA) || defined(SRAM_BASE) || defined(SRAM_BASE_VA) \
 || defined(ICCM_BASE) || defined(ICCM_BASE_VA) || defined(DCCM_BASE) || defined(DCCM_BASE_VA)
static int boot_region_max_size(unsigned long addr, unsigned long base, unsigned long size, size_t *max_size)
{
	if ((addr < base) || ((addr - base) >= size))
		return 0;
	*max_size = size - (addr - base);
	return 1;
}
#endif

static int boot_load_max_size(unsigned long addr, size_t *max_size)
{
	(void)max_size;
#ifdef MAIN_RAM_BASE
	if (boot_region_max_size(addr, MAIN_RAM_BASE, MAIN_RAM_SIZE, max_size))
		return 1;
#endif
#ifdef MAIN_RAM_BASE_VA
	if (boot_region_max_size(addr, MAIN_RAM_BASE_VA, MAIN_RAM_SIZE, max_size))
		return 1;
#endif
#ifdef SRAM_BASE
	if (boot_region_max_size(addr, SRAM_BASE, SRAM_SIZE, max_size))
		return 1;
#endif
#ifdef SRAM_BASE_VA
	if (boot_region_max_size(addr, SRAM_BASE_VA, SRAM_SIZE, max_size))
		return 1;
#endif
#ifdef ICCM_BASE
	if (boot_region_max_size(addr, ICCM_BASE, ICCM_SIZE, max_size))
		return 1;
#endif
#ifdef ICCM_BASE_VA
	if (boot_region_max_size(addr, ICCM_BASE_VA, ICCM_SIZE, max_size))
		return 1;
#endif
#ifdef DCCM_BASE
	if (boot_region_max_size(addr, DCCM_BASE, DCCM_SIZE, max_size))
		return 1;
#endif
#ifdef DCCM_BASE_VA
	if (boot_region_max_size(addr, DCCM_BASE_VA, DCCM_SIZE, max_size))
		return 1;
#endif
	printf("Error: boot load address 0x%08lx is outside writable memory\n", addr);
	return 0;
}

#endif /* __ASSEMBLER__ */

#endif /* VEER_BOOT_OVERRIDE_H */