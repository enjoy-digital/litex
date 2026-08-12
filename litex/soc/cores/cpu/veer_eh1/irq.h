#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>

// VeeR EH1 routes all external interrupts through an on-core PIC rather
// than mapping each source to its own mip/mie bit. All sources are OR'd
// into the single standard mie.meie/mip.meip bit (bit 11); per-source
// enable and pending state live in the PIC's memory-mapped registers
// below.
//
// PIC_base_addr = (pic_region << 28) | pic_offset, from veer_eh1.py's
// mem_map(). With current defaults (region=0xf, offset=0xc0000) this
// is 0xf00c0000.
//
// PIC source IDs are 1-based; source 0 means "no interrupt pending"
// (meihap.claimid). LiteX irq numbers are 0-based, so throughout:
//     PIC source ID = LiteX irq number + 1

#define PIC_BASE         0xf00c0000L
#define PIC_MEIPL(s)     (*((unsigned int *)(PIC_BASE + 0x0000 + ((s) * 4))))
#define PIC_MEIP(x)      (*((unsigned int *)(PIC_BASE + 0x1000 + ((x) * 4))))
#define PIC_MEIE(s)      (*((unsigned int *)(PIC_BASE + 0x2000 + ((s) * 4))))
#define PIC_MPICCFG      (*((unsigned int *)(PIC_BASE + 0x3000)))
#define PIC_MEIGWCTRL(s) (*((unsigned int *)(PIC_BASE + 0x4000 + ((s) * 4))))
#define PIC_MEIGWCLR(s)  (*((unsigned int *)(PIC_BASE + 0x5000 + ((s) * 4))))

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

	for (irq = 0; irq < CONFIG_CPU_INTERRUPTS; irq++)
		PIC_MEIE(irq + 1) = (mask >> irq) & 1;

	// Individual sources are gated above; this is the aggregate
	// machine-external-interrupt enable the PIC's output feeds into.
	if (mask) csrs(mie, 1 << 11); else csrc(mie, 1 << 11);
}

static inline unsigned int irq_pending(void)
{
	// meipX(0) covers PIC source IDs 1..31; fine while
	// CONFIG_CPU_INTERRUPTS stays under 31.
	return PIC_MEIP(0) >> 1;
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */