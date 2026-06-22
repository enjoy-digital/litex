#ifndef __IRQ_H
#define __IRQ_H

#include <stdint.h>
#include "system.h"
#include "generated/soc.h"


#ifdef __cplusplus
extern "C" {
#endif

extern volatile unsigned int irqs_enabled;

static inline unsigned int irq_getie(void)
{
    return irqs_enabled; /* FIXME */
}

static inline void irq_setie(unsigned int ie)
{
    if (ie)
        __asm__ volatile ("cpsie i" : : : "memory");
    else
        __asm__ volatile ("cpsid i" : : : "memory");
    irqs_enabled = ie;
}

static inline unsigned int irq_getmask(void)
{
    return (1 << UART_INTERRUPT); // FIXME
}

static inline void irq_setmask(unsigned int mask)
{
   /* TODO */
}

static inline unsigned int irq_pending(void)
{
    /* TODO */
    return 0;
}


#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
