#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>

static inline unsigned int irq_getie(void)
{
	return (csrr(mstatus) & CSR_MSTATUS_MIE) != 0;
}

static inline void irq_setie(unsigned int ie)
{
	if(ie) csrs(mstatus,CSR_MSTATUS_MIE); else csrc(mstatus,CSR_MSTATUS_MIE);
}

/* TODO: these three don't yet talk to VeeR's PIC (pic_ctrl.sv). They need the
 * PIC's priority-based CSR interface (meipt/meicurpl/meicidpl/meivt/meicpct,
 * per the SweRV EH1 PRM) to correctly gate/read individual external interrupt
 * lines. For now this just uses the coarse MEIE bit so the BIOS links and
 * boots; per-source masking (UART vs timer0, etc.) is not yet functional. */
static inline unsigned int irq_getmask(void)
{
    unsigned int mie;
    __asm__ __volatile__ ("csrr %0, mie" : "=r"(mie));
    return (mie >> 11) & 1; /* MEIE bit only, not per-source */
}

static inline void irq_setmask(unsigned int mask)
{
    if (mask)
        __asm__ __volatile__ ("csrs mie, %0" :: "r"(1 << 11));
    else
        __asm__ __volatile__ ("csrc mie, %0" :: "r"(1 << 11));
}

static inline unsigned int irq_pending(void)
{
    unsigned int mip;
    __asm__ __volatile__ ("csrr %0, mip" : "=r"(mip));
    return (mip >> 11) & 1; /* MEIP only, not per-source */
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */