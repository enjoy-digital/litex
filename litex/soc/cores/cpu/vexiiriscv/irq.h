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
	return 0;
}

static inline void irq_setie(unsigned int ie)
{

}

static inline unsigned int irq_getmask(void)
{

	return 0;
}

static inline void irq_setmask(unsigned int mask)
{

}

static inline unsigned int irq_pending(void)
{
	return 0;
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
