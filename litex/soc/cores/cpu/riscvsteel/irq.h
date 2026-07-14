#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>

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
	unsigned int mask;
	asm volatile ("csrr %0, %1" : "=r"(mask) : "i"(CSR_IRQ_MASK));
	return (mask >> FIRQ_OFFSET);
}

static inline void irq_setmask(unsigned int mask)
{
	asm volatile ("csrw %0, %1" :: "i"(CSR_IRQ_MASK), "r"(mask << FIRQ_OFFSET));
}

static inline unsigned int irq_pending(void)
{
	unsigned int pending;
	asm volatile ("csrr %0, %1" : "=r"(pending) : "i"(CSR_IRQ_PENDING));
	return (pending >> FIRQ_OFFSET);
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
