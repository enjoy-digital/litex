#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>

#define PLIC_SOURCE_0    0x0c000004L // source 0 priority
#define PLIC_SOURCE_1    0x0c000008L // source 1 priority
#define PLIC_PENDING     0x0c001000L // start of pending array
#define PLIC_M_ENABLE    0x0c002000L // Start of Hart 0 M-mode enables
#define PLIC_S_ENABLE    0x0c002100L // Start of Hart 0 S-mode enables
#define PLIC_M_THRESHOLD 0x0c200000L // hart 0 M-mode priority threshold
#define PLIC_M_CLAIM     0x0c200004L // hart 0 M-mode priority claim/complete
#define PLIC_S_THRESHOLD 0x0c200100L // hart 0 S-mode priority threshold
#define PLIC_S_CLAIM     0x0c200104L // hart 0 S-mode priority claim/complete

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
	return *((unsigned int *)PLIC_M_ENABLE) >> 1;
}

static inline void irq_setmask(unsigned int mask)
{
	*((unsigned int *)PLIC_M_ENABLE) = mask << 1;
}

static inline unsigned int irq_pending(void)
{
	return *((unsigned int *)PLIC_PENDING) >> 1;
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
