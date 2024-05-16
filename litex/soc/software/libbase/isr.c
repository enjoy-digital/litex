// This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
// This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
// This file is Copyright (c) 2020 Raptor Engineering, LLC <sales@raptorengineering.com>
// License: BSD


#include <generated/csr.h>
#include <generated/soc.h>
#include <irq.h>
#include <libbase/uart.h>
#include <stdio.h>

#if defined(__microwatt__)
void isr(uint64_t vec);
void isr_dec(void);
#else
void isr(void);
#endif

#ifdef CONFIG_CPU_HAS_INTERRUPT

#if defined(__blackparrot__) /*TODO: Update this function for BP*/ //
void isr(void)
{
  static int onetime = 0;
  if ( onetime == 0){
    printf("ISR blackparrot\n");
    printf("TRAP!!\n");
    onetime++;
  }
}
#elif defined(__riscv_plic__)

// PLIC initialization.
void plic_init(void);
void plic_init(void)
{
	int i;

	// Set priorities for the first 8 external interrupts to 1.
	for (i = 0; i < 8; i++)
		*((unsigned int *)PLIC_BASE + PLIC_EXT_IRQ_BASE + i) = 1;

	// Enable the first 8 external interrupts
	*((unsigned int *)PLIC_ENABLED) = 0xff << PLIC_EXT_IRQ_BASE;

	// Set priority threshold to 0 (any priority > 0 triggers an interrupt).
	*((unsigned int *)PLIC_THRSHLD) = 0;
}

// Interrupt Service Routine.
void isr(void)
{
	unsigned int claim;

	// Claim and handle pending interrupts.
	while ((claim = *((unsigned int *)PLIC_CLAIM))) {
		switch (claim - PLIC_EXT_IRQ_BASE) {
		case UART_INTERRUPT:
			uart_isr(); // Handle UART interrupt.
			break;
		default:
			// Unhandled interrupt source, print diagnostic information.
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
		// Acknowledge the interrupt.
		*((unsigned int *)PLIC_CLAIM) = claim;
	}
}
#elif defined(__cv32e40p__)  || defined(__cv32e41p__)

#define FIRQ_OFFSET 16
#define IRQ_MASK 0x7FFFFFFF
#define INVINST 2
#define ECALL 11
#define RISCV_TEST

void isr(void)
{
    unsigned int cause = csrr(mcause) & IRQ_MASK;

    if (csrr(mcause) & 0x80000000) {
#ifndef UART_POLLING
        if (cause == (UART_INTERRUPT+FIRQ_OFFSET)){
            uart_isr();
        }
#endif
    } else {
#ifdef RISCV_TEST
        int gp;
        asm volatile ("mv %0, gp" : "=r"(gp));
        printf("E %d\n", cause);
        if (cause == INVINST) {
            printf("Inv Instr\n");
            for(;;);
        }
        if (cause == ECALL) {
            printf("Ecall (gp: %d)\n", gp);
            csrw(mepc, csrr(mepc)+4);
        }
#endif
    }
}

#elif defined(__microwatt__)

void isr(uint64_t vec)
{
	if (vec == 0x900)
		return isr_dec();

	if (vec == 0x500) {
		// Read interrupt source
		uint32_t xirr = xics_icp_readw(PPC_XICS_XIRR);
		uint32_t irq_source = xirr & 0x00ffffff;

		__attribute__((unused)) unsigned int irqs;

		// Handle IPI interrupts separately
		if (irq_source == 2) {
			// IPI interrupt
			xics_icp_writeb(PPC_XICS_MFRR, 0xff);
		}
		else {
			// External interrupt
			irqs = irq_pending() & irq_getmask();

#ifndef UART_POLLING
			if(irqs & (1 << UART_INTERRUPT))
				uart_isr();
#endif
		}

		// Clear interrupt
		xics_icp_writew(PPC_XICS_XIRR, xirr);

		return;
	}
}

void isr_dec(void)
{
	//  For now, just set DEC back to a large enough value to slow the flood of DEC-initiated timer interrupts
	mtdec(0x000000000ffffff);
}

#elif defined(__cva6__)
void plic_init(void);
void plic_init(void)
{
	int i;

	// priorities for interrupt pins 0...7
	for (i = 0; i < 8; i++)
		*((unsigned int *)PLIC_SOURCE_0 + i) = 1;
	// enable interrupt pins 0...7 (M-mode)
	*((unsigned int *)PLIC_M_ENABLE) = 0xff;
	// set priority threshold to 0 (any priority > 0 triggers interrupt)
	*((unsigned int *)PLIC_M_THRESHOLD) = 0;
}

void isr(void)
{
	unsigned int claim;

	while ((claim = *((unsigned int *)PLIC_M_CLAIM))) {
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
		*((unsigned int *)PLIC_M_CLAIM) = claim;
	}
}

#else
struct irq_table
{
	isr_t isr;
} irq_table[CONFIG_CPU_INTERRUPTS];

int irq_attach(unsigned int irq, isr_t isr)
{
	if (irq >= CONFIG_CPU_INTERRUPTS) {
		printf("Inv irq %d\n", irq);
		return -1;
	}

	unsigned int ie = irq_getie();
	irq_setie(0);
	irq_table[irq].isr = isr;
	irq_setie(ie);
	return irq;
}

int irq_detach(unsigned int irq)
{
	return irq_attach(irq, NULL);
}

void isr(void)
{
	unsigned int irqs = irq_pending() & irq_getmask();

	while (irqs)
	{
		const unsigned int irq = __builtin_ctz(irqs);
		if ((irq < CONFIG_CPU_INTERRUPTS) && irq_table[irq].isr)
			irq_table[irq].isr();
		else {
			irq_setmask(irq_getmask() & ~(1<<irq));
			printf("\n*** disabled spurious irq %d ***\n", irq);
		}
		irqs &= irqs - 1; // clear this irq (the first bit set)
	}
}
#endif

#else

#if defined(__microwatt__)
void isr(uint64_t vec){};
#else
void isr(void){};
#endif

#endif
