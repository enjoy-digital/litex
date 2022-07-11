#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>

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
    return (csrr(mie) >> CSR_IRQ_EXTERNAL_OFFSET);
}

static inline void irq_setmask(unsigned int mask)
{
    if (mask) csrs(mie,CSR_IRQ_EXTERNAL_OFFSET); else csrc(mie,CSR_IRQ_EXTERNAL_OFFSET);
}

static inline unsigned int irq_pending(void)
{
    return ((csrr(mie) | csrr(mip)) >> CSR_IRQ_EXTERNAL_OFFSET) & 0x1;
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
