#include <irq.h>
#include <uart.h>
#ifdef __or1k__
#include <spr-defs.h>
#endif

#include <system.h>
#include <generated/mem.h>
#include <generated/csr.h>

void flush_cpu_icache(void)
{
#if defined (__lm32__)
	asm volatile(
		"wcsr ICC, r0\n"
		"nop\n"
		"nop\n"
		"nop\n"
		"nop\n"
	);
#elif defined (__or1k__)
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
#elif defined (__picorv32__)
	/* no instruction cache */
	asm volatile("nop");
#else
#error Unsupported architecture
#endif
}

void flush_cpu_dcache(void)
{
#if defined (__lm32__)
	asm volatile(
		"wcsr DCC, r0\n"
		"nop\n"
	);
#elif defined (__or1k__)
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
#elif defined (__picorv32__)
	/* no data cache */
	asm volatile("nop");
#else
#error Unsupported architecture
#endif
}

#ifdef L2_SIZE
void flush_l2_cache(void)
{
	unsigned int i;
	for(i=0;i<2*L2_SIZE/4;i++) {
		((volatile unsigned int *) MAIN_RAM_BASE)[i];
	}
}
#endif
