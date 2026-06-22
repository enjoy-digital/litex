#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>

// The CVA5 uses a Platform-Level Interrupt Controller (PLIC) which
// is programmed and queried via a set of MMIO registers.

#define PLIC_BASE    0xf8000000L // Base address and per-pin priority array
#define PLIC_PENDING 0xf8001000L // Bit field matching currently pending pins
#define PLIC_ENABLED 0xf8002000L // Bit field corresponding to the current mask
#define PLIC_THRSHLD 0xf8200000L // Per-pin priority must be >= this to trigger
#define PLIC_CLAIM   0xf8200004L // Claim & completion register address

#define PLIC_EXT_IRQ_BASE 1

#ifndef __riscv_plic__

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
#else

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
        // (csrr(mie) >> CSR_IRQ_EXTERNAL_OFFSET);
        return *((unsigned int *)PLIC_ENABLED) >> PLIC_EXT_IRQ_BASE;
    }

    static inline void irq_setmask(unsigned int mask)
    {
        // if (mask) csrs(mie,CSR_IRQ_EXTERNAL_OFFSET); else csrc(mie,CSR_IRQ_EXTERNAL_OFFSET);
        *((unsigned int *)PLIC_ENABLED) = mask << PLIC_EXT_IRQ_BASE;
    }

    static inline unsigned int irq_pending(void)
    {
        // ((csrr(mie) | csrr(mip)) >> CSR_IRQ_EXTERNAL_OFFSET) & 0x1;
        return *((unsigned int *)PLIC_PENDING) >> PLIC_EXT_IRQ_BASE;
    }

#endif

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */