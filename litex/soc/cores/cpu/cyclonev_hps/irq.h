#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* Cyclone V HPS MPU GIC-390 (Distributor / CPU Interface). */
#define GIC_DIST_BASE 0xfffed000L
#define GIC_CPU_BASE  0xfffec100L

/* Distributor registers. */
#define GIC_DIST_CTLR          0x000
#define GIC_DIST_ISENABLER(n)  (0x100 + 4*(n))
#define GIC_DIST_ICENABLER(n)  (0x180 + 4*(n))
#define GIC_DIST_ISPENDR(n)    (0x200 + 4*(n))
#define GIC_DIST_ICPENDR(n)    (0x280 + 4*(n))
#define GIC_DIST_IPRIORITYR(n) (0x400 + 4*(n))
#define GIC_DIST_ITARGETSR(n)  (0x800 + 4*(n))

/* CPU Interface registers. */
#define GIC_CPU_CTLR 0x00
#define GIC_CPU_PMR  0x04
#define GIC_CPU_IAR  0x0c
#define GIC_CPU_EOIR 0x10

/* F2H IRQs 0-31 are connected to GIC IDs 72-103. */
#define GIC_F2H_IRQ_OFFSET 72

static inline uint32_t gic_dist_read(uint32_t offset) {
	return *(volatile uint32_t *)(GIC_DIST_BASE + offset);
}

static inline void gic_dist_write(uint32_t offset, uint32_t value) {
	*(volatile uint32_t *)(GIC_DIST_BASE + offset) = value;
}

static inline uint32_t gic_cpu_read(uint32_t offset) {
	return *(volatile uint32_t *)(GIC_CPU_BASE + offset);
}

static inline void gic_cpu_write(uint32_t offset, uint32_t value) {
	*(volatile uint32_t *)(GIC_CPU_BASE + offset) = value;
}

static inline unsigned int irq_getie(void)
{
	unsigned int cpsr;
	__asm__ volatile("mrs %0, cpsr" : "=r"(cpsr));
	return (cpsr & (1 << 7)) == 0; /* CPSR I-bit: 0 means IRQs enabled. */
}

static inline void irq_setie(unsigned int ie)
{
	if (ie) {
		int i;
		/* Route the F2H IRQs to CPU0 (Target registers hold one byte per interrupt). */
		for (i = GIC_F2H_IRQ_OFFSET/4; i < (GIC_F2H_IRQ_OFFSET + 32)/4; i++)
			gic_dist_write(GIC_DIST_ITARGETSR(i), 0x01010101);
		/* Allow all priorities and enable the Distributor/CPU Interface. */
		gic_cpu_write(GIC_CPU_PMR, 0xff);
		gic_dist_write(GIC_DIST_CTLR, gic_dist_read(GIC_DIST_CTLR) | 1);
		gic_cpu_write(GIC_CPU_CTLR,   gic_cpu_read(GIC_CPU_CTLR)   | 1);
		__asm__ volatile("cpsie i" ::: "memory");
	} else {
		__asm__ volatile("cpsid i" ::: "memory");
	}
}

/* Masks map the 32 F2H IRQs: GIC IDs 72-95 are in registers n=2 bits 31:8, IDs 96-103 in
   registers n=3 bits 7:0. */

static inline unsigned int irq_getmask(void)
{
	return (gic_dist_read(GIC_DIST_ISENABLER(2)) >> 8) |
	       (gic_dist_read(GIC_DIST_ISENABLER(3)) << 24);
}

static inline void irq_setmask(unsigned int mask)
{
	/* Set/Clear-Enable registers: written 1s set/clear the enables, 0s are ignored (other GIC
	   IDs, ex HPS peripherals, are thus not disturbed). */
	gic_dist_write(GIC_DIST_ICENABLER(2), (~mask << 8) & 0xffffff00);
	gic_dist_write(GIC_DIST_ICENABLER(3), (~mask >> 24) & 0x000000ff);
	gic_dist_write(GIC_DIST_ISENABLER(2), ( mask << 8) & 0xffffff00);
	gic_dist_write(GIC_DIST_ISENABLER(3), ( mask >> 24) & 0x000000ff);
}

static inline unsigned int irq_pending(void)
{
	return (gic_dist_read(GIC_DIST_ISPENDR(2)) >> 8) |
	       (gic_dist_read(GIC_DIST_ISPENDR(3)) << 24);
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
