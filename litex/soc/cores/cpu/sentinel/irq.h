#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>

/* Custom interrupt I/O registers. The value of IRQ line to Sentinel is:
   (irq_pending() & irq_getmask()) != 0.

   Of course, if MIE is clear, no interrupts will be serviced :). */
#define INTERRUPT_PEND 0x10L
#define INTERRUPT_MASK 0x14L

static inline unsigned int irq_getie(void)
{
	return (csrr(mstatus) & CSR_MSTATUS_MIE) != 0;
}

static inline void irq_setie(unsigned int ie)
{
	if(ie) csrs(mstatus,CSR_MSTATUS_MIE); else csrc(mstatus,CSR_MSTATUS_MIE);
}

static inline unsigned int irq_getmask(void)
{
	return *((unsigned int *)INTERRUPT_MASK);
}

static inline void irq_setmask(unsigned int mask)
{
	*((unsigned int *)INTERRUPT_MASK) = mask;
}

static inline unsigned int irq_pending(void) {

	return *((unsigned int *)INTERRUPT_PEND);
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
