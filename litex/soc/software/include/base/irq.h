#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#ifdef __or1k__
#include <system.h>
#endif

static inline unsigned int irq_getie(void)
{
#if defined (__lm32__)
	unsigned int ie;
	__asm__ __volatile__("rcsr %0, IE" : "=r" (ie));
	return ie;
#elif defined (__or1k__)
	return !!(mfspr(SPR_SR) & SPR_SR_IEE);
#elif defined (__riscv__)
	/* FIXME */
	return 0;
#else
#error Unsupported architecture
#endif
}

static inline void irq_setie(unsigned int ie)
{
#if defined (__lm32__)
	__asm__ __volatile__("wcsr IE, %0" : : "r" (ie));
#elif defined (__or1k__)
	if (ie & 0x1)
		mtspr(SPR_SR, mfspr(SPR_SR) | SPR_SR_IEE);
	else
		mtspr(SPR_SR, mfspr(SPR_SR) & ~SPR_SR_IEE);
#elif defined (__riscv__)
	/* FIXME */
	return 0;
#else
#error Unsupported architecture
#endif
}

static inline unsigned int irq_getmask(void)
{
#if defined (__lm32__)
	unsigned int mask;
	__asm__ __volatile__("rcsr %0, IM" : "=r" (mask));
	return mask;
#elif defined (__or1k__)
	return mfspr(SPR_PICMR);
#elif defined (__riscv__)
	/* FIXME */
	return 0;
#else
#error Unsupported architecture
#endif
}

static inline void irq_setmask(unsigned int mask)
{
#if defined (__lm32__)
	__asm__ __volatile__("wcsr IM, %0" : : "r" (mask));
#elif defined (__or1k__)
	mtspr(SPR_PICMR, mask);
#elif defined (__riscv__)
	/* FIXME */
	return 0;
#else
#error Unsupported architecture
#endif
}

static inline unsigned int irq_pending(void)
{
#if defined (__lm32__)
	unsigned int pending;
	__asm__ __volatile__("rcsr %0, IP" : "=r" (pending));
	return pending;
#elif defined (__or1k__)
	return mfspr(SPR_PICSR);
#elif defined (__riscv__)
	/* FIXME */
	return 0;
#else
#error Unsupported architecture
#endif
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
