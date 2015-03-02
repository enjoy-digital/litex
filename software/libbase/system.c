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
#else
#error Unsupported architecture
#endif
}

#ifdef CSR_WISHBONE2LASMI_BASE
void flush_l2_cache(void)
{
	unsigned int l2_nwords;
	unsigned int i;
	register unsigned int addr;
	register unsigned int dummy;

	l2_nwords = 1 << wishbone2lasmi_cachesize_read();
	for(i=0;i<2*l2_nwords;i++) {
		addr = SDRAM_BASE + i*4;
#ifdef __lm32__
		__asm__ volatile("lw %0, (%1+0)\n":"=r"(dummy):"r"(addr));
#else
#warning TODO
#endif
	}
}
#else
void flush_l2_cache(void)
{
}
#endif
