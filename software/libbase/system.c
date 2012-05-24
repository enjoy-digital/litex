#include <irq.h>
#include <uart.h>

#include <system.h>

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
