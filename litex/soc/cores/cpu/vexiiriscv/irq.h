#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>

// VexiiRiscv uses a Platform-Level Interrupt Controller (PLIC) which
// is programmed and queried via a set of MMIO registerss

#define PLIC_BASE    0xf0c00000L // Base address and per-pin priority array
#define PLIC_PENDING 0xf0c01000L // Bit field matching currently pending pins
#define PLIC_ENABLED 0xf0c02000L // Bit field corresponding to the current mask
#define PLIC_THRSHLD 0xf0e00000L // Per-pin priority must be >= this to trigger
#define PLIC_CLAIM   0xf0e00004L // Claim & completion register address

#define PLIC_EXT_IRQ_BASE 0

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

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
