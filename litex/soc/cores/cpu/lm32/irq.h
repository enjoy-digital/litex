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
	unsigned int ie;
	__asm__ __volatile__("rcsr %0, IE" : "=r" (ie));
	return ie;
}

static inline void irq_setie(unsigned int ie)
{
	__asm__ __volatile__("wcsr IE, %0" : : "r" (ie));
}

static inline unsigned int irq_getmask(void)
{
	unsigned int mask;
	__asm__ __volatile__("rcsr %0, IM" : "=r" (mask));
	return mask;
}

static inline void irq_setmask(unsigned int mask)
{
	__asm__ __volatile__("wcsr IM, %0" : : "r" (mask));
}

static inline unsigned int irq_pending(void)
{
	unsigned int pending;
	__asm__ __volatile__("rcsr %0, IP" : "=r" (pending));
	return pending;
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
