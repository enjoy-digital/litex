// This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
// This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
// License: BSD


#include <generated/csr.h>
#include <irq.h>
#include <uart.h>
#include <stdio.h>

#ifdef __rocket__
void plic_init(void);
void plic_init(void)
{
	int i;

	// priorities for interrupt pins 1..4
	for (i = 1; i <= 4; i++)
		csr_writel(1, PLIC_BASE + 4*i);
	// enable interrupt pins 1..4
	csr_writel(0xf << 1, PLIC_ENABLED);
	// set priority threshold to 0 (any priority > 0 triggers interrupt)
	csr_writel(0, PLIC_THRSHLD);
}

void isr(void);
void isr(void)
{
	unsigned int claim;

	while ((claim = csr_readl(PLIC_CLAIM))) {
		switch (claim - 1) {
		case UART_INTERRUPT:
			uart_isr();
			break;
		default:
			printf("## PLIC: Unhandled claim: %d\n", claim);
			printf("# plic_enabled:    %08x\n", irq_getmask());
			printf("# plic_pending:    %08x\n", irq_pending());
			printf("# mepc:    %016lx\n", csrr(mepc));
			printf("# mcause:  %016lx\n", csrr(mcause));
			printf("# mtval:   %016lx\n", csrr(mtval));
			printf("# mie:     %016lx\n", csrr(mie));
			printf("# mip:     %016lx\n", csrr(mip));
			printf("###########################\n\n");
			break;
		}
		csr_writel(claim, PLIC_CLAIM);
	}
}
#else
void isr(void);
void isr(void)
{
	unsigned int irqs;

	irqs = irq_pending() & irq_getmask();

	if(irqs & (1 << UART_INTERRUPT))
		uart_isr();
}
#endif
