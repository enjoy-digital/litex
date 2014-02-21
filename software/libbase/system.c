#include <irq.h>
#include <uart.h>

#include <system.h>
#include <generated/mem.h>
#include <generated/csr.h>

void flush_cpu_icache(void)
{
	asm volatile(
		"wcsr ICC, r0\n"
		"nop\n"
		"nop\n"
		"nop\n"
		"nop\n"
	);
}

void flush_cpu_dcache(void)
{
	asm volatile(
		"wcsr DCC, r0\n"
		"nop\n"
	);
}

void flush_l2_cache(void)
{
	unsigned int l2_nwords;
	unsigned int i;
	register unsigned int addr;
	register unsigned int dummy;

	l2_nwords = 1 << (identifier_l2_size_read() - 2);
	for(i=0;i<2*l2_nwords;i++) {
		addr = SDRAM_BASE + i*4;
		__asm__ volatile("lw %0, (%1+0)\n":"=r"(dummy):"r"(addr));
	}
}
