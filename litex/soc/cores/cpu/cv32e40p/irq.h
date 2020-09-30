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
    return 0; // FIXME
}

static inline void irq_setmask(unsigned int mask)
{
    // FIXME
}

static inline unsigned int irq_pending(void)
{
    return 0;// FIXME
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
