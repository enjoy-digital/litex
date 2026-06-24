#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>

#include "csr-defs.h"

static inline unsigned int irq_getie(void)
{
	return (csrr(mstatus) & CSR_MSTATUS_MIE) != 0;
}

static inline void irq_setie(unsigned int ie)
{
	if(ie) csrs(mstatus,CSR_MSTATUS_MIE); else csrc(mstatus,CSR_MSTATUS_MIE);
}

#ifdef __riscv_plic__

#define PLIC_BASE    0xe2000000L // Base address and per-pin priority array
#define PLIC_PENDING 0xe2001000L // Bit field matching currently pending pins
#define PLIC_ENABLED 0xe2002000L // Bit field corresponding to the current mask
#define PLIC_THRSHLD 0xe2200000L // Per-pin priority must be >= this to trigger
#define PLIC_CLAIM   0xe2200004L // Claim & completion register address

#define PLIC_EXT_IRQ_BASE 0


static inline unsigned int irq_getmask(void)
{
	return *((unsigned int *)PLIC_ENABLED) >> PLIC_EXT_IRQ_BASE;
}

static inline void irq_setmask(unsigned int mask)
{
	*((unsigned int *)PLIC_ENABLED) = mask << PLIC_EXT_IRQ_BASE;
}

static inline unsigned int irq_pending(void)
{
	return *((unsigned int *)PLIC_PENDING) >> PLIC_EXT_IRQ_BASE;
}

#else

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

#endif

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
