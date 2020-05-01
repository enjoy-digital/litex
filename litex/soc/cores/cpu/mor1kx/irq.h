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
	return !!(mfspr(SPR_SR) & SPR_SR_IEE);
}

static inline void irq_setie(unsigned int ie)
{
	if (ie & 0x1)
		mtspr(SPR_SR, mfspr(SPR_SR) | SPR_SR_IEE);
	else
		mtspr(SPR_SR, mfspr(SPR_SR) & ~SPR_SR_IEE);
}

static inline unsigned int irq_getmask(void)
{
	return mfspr(SPR_PICMR);
}

static inline void irq_setmask(unsigned int mask)
{
	mtspr(SPR_PICMR, mask);
}

static inline unsigned int irq_pending(void)
{
	return mfspr(SPR_PICSR);
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
