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

/*******************************************************/
/* Common Interrupt Table for All CPUs.                */
/*******************************************************/
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

/***********************************************************/
/* ISR and PLIC Initialization for RISC-V PLIC-based CPUs. */
/***********************************************************/
#if defined(__riscv_plic__)

/* PLIC initialization. */
void plic_init(void)
{
    int i;
    /* Set priorities for the first 8 external interrupts to 1. */
    for (i = 0; i < 8; i++)
        *((unsigned int *)PLIC_BASE + PLIC_EXT_IRQ_BASE + i) = 1;

    /* Enable the first 8 external interrupts. */
    *((unsigned int *)PLIC_ENABLED) = 0xff << PLIC_EXT_IRQ_BASE;

    /* Set priority threshold to 0 (any priority > 0 triggers an interrupt). */
    *((unsigned int *)PLIC_THRSHLD) = 0;
}

/* Interrupt Service Routine. */
void isr(void)
{
    unsigned int claim;

    /* Claim and handle pending interrupts. */
    while ((claim = *((unsigned int *)PLIC_CLAIM))) {
        unsigned int irq = claim - PLIC_EXT_IRQ_BASE;
        if (irq < CONFIG_CPU_INTERRUPTS && irq_table[irq].isr) {
            irq_table[irq].isr();
        } else {
            /* Unhandled interrupt source, print diagnostic information. */
            printf("## PLIC: Unhandled claim: %d\n", claim);
            printf("# plic_enabled:    %08x\n", irq_getmask());
            printf("# plic_pending:    %08x\n", irq_pending());
            printf("# mepc:    %016lx\n", csrr(mepc));
            printf("# mcause:  %016lx\n", csrr(mcause));
            printf("# mtval:   %016lx\n", csrr(mtval));
            printf("# mie:     %016lx\n", csrr(mie));
            printf("# mip:     %016lx\n", csrr(mip));
            printf("###########################\n\n");
        }
        /* Acknowledge the interrupt. */
        *((unsigned int *)PLIC_CLAIM) = claim;
    }
}

/***********************************/
/* ISR Handling for Ibex CPU. */
/***********************************/
#elif defined(__ibex__)

/* External handler defined in demo code */
extern void software_interrupt_handler(void) __attribute__((weak));

/* Ibex interrupt handler */
void isr(void)
{
    unsigned int cause = csrr(mcause);
    
    /* Check if this is an interrupt (MSB set) */
    if (cause & 0x80000000) {
        unsigned int irq_cause = cause & 0x7FFFFFFF;
        
        /* Handle machine software interrupt (MSIP) - Ibex receives this as a standard RISC-V interrupt */
        if (irq_cause == 3) {
            /* Call the software interrupt handler if available */
            if (software_interrupt_handler) {
                software_interrupt_handler();
            }
        }
        /* Handle machine timer interrupt (MTIP) */
        else if (irq_cause == 7) {
            /* Timer interrupts would be handled here */
            /* For now, just acknowledge */
        }
        /* Handle fast interrupts (Ibex-specific) */
        else {
            unsigned int irqs = irq_pending() & irq_getmask();
            while (irqs) {
                const unsigned int irq = __builtin_ctz(irqs);
                if ((irq < CONFIG_CPU_INTERRUPTS) && irq_table[irq].isr)
                    irq_table[irq].isr();
                else {
                    irq_setmask(irq_getmask() & ~(1 << irq));
                    printf("\n*** disabled spurious irq %d ***\n", irq);
                }
                irqs &= irqs - 1;
            }
        }
    }
}

/************************************************/
/* ISR Handling for CV32E40P and CV32E41P CPUs. */
/************************************************/
#elif defined(__cv32e40p__) || defined(__cv32e41p__)

#define FIRQ_OFFSET 16
#define IRQ_MASK 0x7FFFFFFF
#define INVINST 2
#define ECALL 11
#define RISCV_TEST

/* Interrupt Service Routine. */
void isr(void)
{
    unsigned int cause = csrr(mcause) & IRQ_MASK;

    if (csrr(mcause) & 0x80000000) {
        /* Handle fast interrupts (FIRQ). */
        unsigned int irq = cause - FIRQ_OFFSET;
        if (irq < CONFIG_CPU_INTERRUPTS && irq_table[irq].isr) {
            irq_table[irq].isr();
        }
    } else {
        /* Handle regular exceptions and system calls. */
#ifdef RISCV_TEST
        int gp;
        asm volatile("mv %0, gp" : "=r"(gp));
        printf("E %d\n", cause);
        if (cause == INVINST) {
            printf("Inv Instr\n");
            for (;;);
        }
        if (cause == ECALL) {
            printf("Ecall (gp: %d)\n", gp);
            csrw(mepc, csrr(mepc) + 4);
        }
#endif
    }
}

/*************************************/
/* ISR Handling for BlackParrot CPU. */
/*************************************/

#elif defined(__blackparrot__) /*TODO: Update this function for BP.*/
/* Interrupt Service Routine. */
void isr(void)
{
    static int onetime = 0;
    if (onetime == 0) {
        printf("ISR blackparrot\n");
        printf("TRAP!!\n");
        onetime++;
    }
}

/***********************************/
/* ISR Handling for Microwatt CPU. */
/***********************************/
#elif defined(__microwatt__)

void isr(uint64_t vec)
{
    if (vec == 0x900)
        return isr_dec();

    if (vec == 0x500) {
        /* Read interrupt source. */
        uint32_t xirr = xics_icp_readw(PPC_XICS_XIRR);
        uint32_t irq_source = xirr & 0x00ffffff;

        __attribute__((unused)) unsigned int irqs;

        /* Handle IPI interrupts separately. */
        if (irq_source == 2) {
            /* IPI interrupt. */
            xics_icp_writeb(PPC_XICS_MFRR, 0xff);
        } else {
            /* External interrupt. */
            irqs = irq_pending() & irq_getmask();

            if (irqs) {
                const unsigned int irq = __builtin_ctz(irqs);
                if (irq < CONFIG_CPU_INTERRUPTS && irq_table[irq].isr) {
                    irq_table[irq].isr();
                } else {
                    irq_setmask(irq_getmask() & ~(1 << irq));
                    printf("\n*** disabled spurious irq %d ***\n", irq);
                }
                irqs &= irqs - 1; /* Clear this IRQ (the first bit set). */
            }
        }

        /* Clear interrupt. */
        xics_icp_writew(PPC_XICS_XIRR, xirr);

        return;
    }
}

void isr_dec(void)
{
    /* Set DEC back to a large enough value to slow the flood of DEC-initiated timer interrupts. */
    mtdec(0x000000000ffffff);
}

/***********************************/
/* ISR Handling for RISC-V CPUs with CLINT. */
/***********************************/
#elif defined(CSR_CLINT_BASE)

/* External handler defined in demo code */
extern void software_interrupt_handler(void) __attribute__((weak));

/* CLINT interrupt handler for software and timer interrupts */
void isr(void)
{
    unsigned int cause = csrr(mcause);
    
    /* Check if this is an interrupt (MSB set) */
    if (cause & 0x80000000) {
        unsigned int irq_cause = cause & 0x7FFFFFFF;
        
        /* Handle machine software interrupt (MSIP) */
        if (irq_cause == 3) {
            /* Call the software interrupt handler if available */
            if (software_interrupt_handler) {
                software_interrupt_handler();
            }
        }
        /* Handle machine timer interrupt (MTIP) */
        else if (irq_cause == 7) {
            /* Timer interrupts would be handled here */
            /* Clear timer interrupt by setting MTIMECMP to max value */
            #ifdef CSR_CLINT_MTIMECMP0_LOW_ADDR
            *(volatile uint32_t *)(CSR_CLINT_MTIMECMP0_HIGH_ADDR) = 0xFFFFFFFF;
            *(volatile uint32_t *)(CSR_CLINT_MTIMECMP0_LOW_ADDR) = 0xFFFFFFFF;
            #endif
        }
        /* Handle other interrupts through the standard mechanism */
        else {
            unsigned int irqs = irq_pending() & irq_getmask();
            while (irqs) {
                const unsigned int irq = __builtin_ctz(irqs);
                if ((irq < CONFIG_CPU_INTERRUPTS) && irq_table[irq].isr)
                    irq_table[irq].isr();
                else {
                    irq_setmask(irq_getmask() & ~(1 << irq));
                    printf("\n*** disabled spurious irq %d ***\n", irq);
                }
                irqs &= irqs - 1;
            }
        }
    }
}

/***********************************/
/* ISR Handling for RISC-V CPUs with CLIC. */
/***********************************/
#elif defined(CSR_CLIC_BASE)

#include <clic.h>

/* External handler defined in demo code */
extern void clic_interrupt_handler(unsigned int id, unsigned int priority) __attribute__((weak));

/* CLIC interrupt handler */
void isr(void)
{
    unsigned int cause = csrr(mcause);
    
    /* Check if this is an interrupt (MSB set) */
    if (cause & 0x80000000) {
        /* For CLIC, the interrupt ID is provided by the hardware */
        /* The CPU should have provided the interrupt ID through its clic_interrupt_id signal */
        /* Since we can't directly read the hardware signals from software, we need to:
         * 1. Check which interrupt is pending with highest priority
         * 2. Handle that interrupt
         */
        
        /* Find the highest priority pending interrupt */
        unsigned int highest_priority = 255;  /* Lowest priority */
        int highest_priority_irq = -1;
        unsigned int i;
        
        /* Scan all interrupts to find the highest priority pending one */
        /* Use CLIC_NUM_INTERRUPTS to avoid accessing invalid registers */
        unsigned int max_interrupts = CLIC_NUM_INTERRUPTS;
        if (max_interrupts > CONFIG_CPU_INTERRUPTS) {
            max_interrupts = CONFIG_CPU_INTERRUPTS;
        }
        for (i = 0; i < max_interrupts; i++) {
            if (clic_is_pending(i) && (clic_get_intie(i) != 0)) {
                unsigned int priority = clic_get_intprio(i);
                if (priority < highest_priority) {
                    highest_priority = priority;
                    highest_priority_irq = i;
                }
            }
        }
        
        /* Handle the highest priority interrupt */
        if (highest_priority_irq >= 0) {
            /* Call the CLIC-specific handler if available */
            if (clic_interrupt_handler) {
                clic_interrupt_handler(highest_priority_irq, highest_priority);
            }
            /* Otherwise use the standard interrupt table */
            else if (irq_table[highest_priority_irq].isr) {
                irq_table[highest_priority_irq].isr();
                /* Clear the interrupt if it's edge-triggered */
                if (clic_get_intattr(highest_priority_irq) & CLIC_ATTR_TRIG_EDGE) {
                    clic_clear_pending(highest_priority_irq);
                }
            }
        }
    }
}

/***********************************/
/* ISR Handling for CVA5 CPU in Baremetal Mode. */
/***********************************/
#elif defined(__cva5__)

void plic_init(void);

void plic_init(void)
{
}
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
	// irq_setie(1);
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
/*******************************************************/
/* Generic ISR Handling for CPUs with Interrupt Table. */
/*******************************************************/
#else

/* Interrupt Service Routine. */
void isr(void)
{
    unsigned int irqs = irq_pending() & irq_getmask();

    while (irqs) {
        const unsigned int irq = __builtin_ctz(irqs);
        if ((irq < CONFIG_CPU_INTERRUPTS) && irq_table[irq].isr)
            irq_table[irq].isr();
        else {
            irq_setmask(irq_getmask() & ~(1 << irq));
            printf("\n*** disabled spurious irq %d ***\n", irq);
        }
        irqs &= irqs - 1; /* Clear this IRQ (the first bit set). */
    }
}
#endif

#else

#if defined(__microwatt__)
void isr(uint64_t vec) {};
#else
void isr(void) {};
#endif

#endif

