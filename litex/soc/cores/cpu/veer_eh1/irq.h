#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/soc.h>

// VeeR EH1 routes all external interrupts through an on-core PIC. The
// interrupt sources are ORed into mie.meie/mip.meip; per-source state is
// exposed through the memory-mapped registers below.
//
// PIC source IDs are 1-based, while LiteX IRQ numbers are 0-based.

#define PIC_REG(offset)   (*((volatile unsigned int *)(PIC_BASE + (offset))))
#define PIC_MEIPL(source) PIC_REG(0x0000 + ((source) * 4))
#define PIC_MEIP(word)    PIC_REG(0x1000 + ((word)   * 4))
#define PIC_MEIE(source)  PIC_REG(0x2000 + ((source) * 4))
#define PIC_MPICCFG       PIC_REG(0x3000)
#define PIC_MEIGWCTRL(source) PIC_REG(0x4000 + ((source) * 4))
#define PIC_MEIGWCLR(source)  PIC_REG(0x5000 + ((source) * 4))

static inline void pic_fence(void)
{
	asm volatile ("fence" ::: "memory");
}

static inline unsigned int irq_getie(void)
{
	return (csrr(mstatus) & CSR_MSTATUS_MIE) != 0;
}

static inline void irq_setie(unsigned int ie)
{
	if (ie)
		csrs(mstatus, CSR_MSTATUS_MIE);
	else
		csrc(mstatus, CSR_MSTATUS_MIE);
}

static inline unsigned int irq_getmask(void)
{
	unsigned int mask = 0;
	unsigned int irq;

	for (irq = 0; irq < CONFIG_CPU_INTERRUPTS; irq++)
		if (PIC_MEIE(irq + 1) & 1)
			mask |= 1u << irq;

	return mask;
}

static inline void irq_setmask(unsigned int mask)
{
	unsigned int irq;

	for (irq = 0; irq < CONFIG_CPU_INTERRUPTS; irq++) {
		PIC_MEIE(irq + 1) = (mask >> irq) & 1;
		pic_fence();
	}

	if (mask)
		csrs(mie, 1 << 11);
	else
		csrc(mie, 1 << 11);
}

static inline unsigned int irq_pending(void)
{
	/* Source 32 is bit 0 of the second pending word. */
	return (PIC_MEIP(0) >> 1) | (PIC_MEIP(1) << 31);
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
