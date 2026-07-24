#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

/* Interrupt support is stubbed: the Agilex HPS GIC (GIC-600 on Agilex 3/5, GIC-400 on Agilex 7,
   bases in the CPU's HPS_VARIANTS table) is managed by U-Boot/Linux on the ARM cores. A GIC-aware
   bare-metal implementation (as done for cyclonev_hps) can be added later if a BIOS is run. */

static inline unsigned int irq_getie(void)
{
	return 0; /* FIXME */
}

static inline void irq_setie(unsigned int ie)
{
	/* FIXME */
}

static inline unsigned int irq_getmask(void)
{
	return 0; /* FIXME */
}

static inline void irq_setmask(unsigned int mask)
{
	/* FIXME */
}

static inline unsigned int irq_pending(void)
{
	return 0; /* FIXME */
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
