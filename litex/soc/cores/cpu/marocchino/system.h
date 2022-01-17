#ifndef __SYSTEM_H
#define __SYSTEM_H

#include <spr-defs.h>

#ifdef __cplusplus
extern "C" {
#endif

static inline unsigned long mfspr(unsigned long add)
{
	unsigned long ret;

	__asm__ __volatile__ ("l.mfspr %0,%1,0" : "=r" (ret) : "r" (add));

	return ret;
}

static inline void mtspr(unsigned long add, unsigned long val)
{
	__asm__ __volatile__ ("l.mtspr %0,%1,0" : : "r" (add), "r" (val));
}

__attribute__((unused)) static void flush_cpu_icache(void)
{
	unsigned long iccfgr;
	unsigned long cache_set_size;
	unsigned long cache_ways;
	unsigned long cache_block_size;
	unsigned long cache_size;
	int i;

	iccfgr = mfspr(SPR_ICCFGR);
	cache_ways = 1 << (iccfgr & SPR_ICCFGR_NCW);
	cache_set_size = 1 << ((iccfgr & SPR_ICCFGR_NCS) >> 3);
	cache_block_size = (iccfgr & SPR_ICCFGR_CBS) ? 32 : 16;
	cache_size = cache_set_size * cache_ways * cache_block_size;

	for (i = 0; i < cache_size; i += cache_block_size)
		mtspr(SPR_ICBIR, i);
}

__attribute__((unused)) static void flush_cpu_dcache(void)
{
	unsigned long dccfgr;
	unsigned long cache_set_size;
	unsigned long cache_ways;
	unsigned long cache_block_size;
	unsigned long cache_size;
	int i;

	dccfgr = mfspr(SPR_DCCFGR);
	cache_ways = 1 << (dccfgr & SPR_ICCFGR_NCW);
	cache_set_size = 1 << ((dccfgr & SPR_DCCFGR_NCS) >> 3);
	cache_block_size = (dccfgr & SPR_DCCFGR_CBS) ? 32 : 16;
	cache_size = cache_set_size * cache_ways * cache_block_size;

	for (i = 0; i < cache_size; i += cache_block_size)
		mtspr(SPR_DCBIR, i);
}

void flush_l2_cache(void);

void busy_wait(unsigned int ms);
void busy_wait_us(unsigned int us);

#ifdef __cplusplus
}
#endif

#endif /* __SYSTEM_H */
