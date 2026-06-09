#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/mem.h>
#include <generated/soc.h>

// QEMU exposes a SiFive-compatible Platform-Level Interrupt Controller (PLIC)
// at the LiteX-generated PLIC memory region.

#define PLIC_PENDING      (PLIC_BASE + 0x001000L) // Bit field matching currently pending pins
#define PLIC_ENABLED      (PLIC_BASE + 0x002000L) // Bit field corresponding to the current mask
#define PLIC_THRSHLD      (PLIC_BASE + 0x200000L) // Per-pin priority must be >= this to trigger
#define PLIC_CLAIM        (PLIC_BASE + 0x200004L) // Claim & completion register address

#define PLIC_EXT_IRQ_BASE 0

static inline unsigned int irq_getie(void)
{
	return (csrr(mstatus) & CSR_MSTATUS_MIE) != 0;
}

static inline void irq_setie(unsigned int ie)
{
	if (ie)
		csrs(mstatus, CSR_MSTATUS_MIE);
	else
		csrc(mstatus, CSR_MSTATUS_MIE);
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
