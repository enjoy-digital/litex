#ifndef __IRQ_H
#define __IRQ_H

#include <stdint.h>
#include "system.h"
#include "generated/soc.h"


#ifdef __cplusplus
extern "C" {
#endif


static inline unsigned int irq_getie(void)
{
    return 0; /* FIXME */
}

static inline void irq_setie(unsigned int ie)
{
    /* TODO */
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
