#include <irq.h>
#include <uart.h>
#ifdef __or1k__
#include <spr-defs.h>
#endif

#if defined (__vexriscv__)
#include <csr-defs.h>
#endif

#include <system.h>
#include <generated/mem.h>
#include <generated/csr.h>

#include <stdio.h>

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
#elif defined (__vexriscv__)
	asm volatile(
		".word(0x400F)\n"
		"nop\n"
		"nop\n"
		"nop\n"
		"nop\n"
		"nop\n"
	);
#elif defined (__minerva__)
	/* no instruction cache */
	asm volatile("nop");
#elif defined (__rocket__)
	/* FIXME: do something useful here! */
	asm volatile("nop");
#elif defined (__microwatt__)
	/* FIXME: do something useful here! */
        asm volatile("nop");
#elif defined (__blackparrot__)
	/* TODO: BP do something useful here! */
	asm volatile("nop");
#elif defined (__serv__)
	/* no instruction cache */
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
#elif defined (__vexriscv__)
	unsigned long cache_info;
	asm volatile ("csrr %0, %1" : "=r"(cache_info) : "i"(CSR_DCACHE_INFO));
	unsigned long cache_way_size = cache_info & 0xFFFFF;
	unsigned long cache_line_size = (cache_info >> 20) & 0xFFF;
	for(register unsigned long idx = 0;idx < cache_way_size;idx += cache_line_size){
		asm volatile("mv x10, %0 \n .word(0b01110000000001010101000000001111)"::"r"(idx));
	}
#elif defined (__minerva__)
	/* no data cache */
	asm volatile("nop");
#elif defined (__rocket__)
	/* FIXME: do something useful here! */
	asm volatile("nop");
#elif defined (__microwatt__)
	/* FIXME: do something useful here! */
	asm volatile("nop");
/*SC_add: What BB does here?*/
#elif defined (__blackparrot__)
	/* FIXME: do something useful here! */
	asm volatile("nop");
#elif defined (__serv__)
	/* no data cache */
#else
#error Unsupported architecture
#endif
}

#ifdef CONFIG_L2_SIZE
void flush_l2_cache(void)
{
	#if CONFIG_L2_SIZE > 0
	unsigned int i;
	debug_helper_set_tag("L2-flush");
	for(i=0;i<2*CONFIG_L2_SIZE/4;i++) {
		debug_helper_arg_write(i);
		printf("  > %d/%d          \r", i, 2*CONFIG_L2_SIZE/4);
		((volatile unsigned int *) MAIN_RAM_BASE)[i];
	}
	printf("\r  > %d/%d\n", CONFIG_L2_SIZE/4, CONFIG_L2_SIZE/4);
	debug_helper_set_tag("");
	debug_helper_arg_write(~0);
	#endif
}
#endif

void busy_wait(unsigned int ms)
{
	timer0_en_write(0);
	timer0_reload_write(0);
	timer0_load_write(CONFIG_CLOCK_FREQUENCY/1000*ms);
	timer0_en_write(1);
	timer0_update_value_write(1);
	while(timer0_value_read()) timer0_update_value_write(1);
}
