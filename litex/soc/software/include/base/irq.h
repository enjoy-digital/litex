#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>

#ifdef __picorv32__
// PicoRV32 has a very limited interrupt support, implemented via custom
// instructions. It also doesn't have a global interrupt enable/disable, so
// we have to emulate it via saving and restoring a mask and using 0/~1 as a
// hardware mask.
// Due to all this somewhat low-level mess, all of the glue is implemented in
// the RiscV crt0, and this header is kept as a thin wrapper. Since interrupts
// managed by this layer, do not call interrupt instructions directly, as the
// state will go out of sync with the hardware.

// Read only.
extern unsigned int _irq_pending;
// Read only.
extern unsigned int _irq_mask;
// Read only.
extern unsigned int _irq_enabled;
extern void _irq_enable(void);
extern void _irq_disable(void);
extern void _irq_setmask(unsigned int);
#endif

#ifdef __rocket__
// The RocketChip uses a Platform-Level Interrupt Controller (PLIC) which
// is programmed and queried via a set of MMIO registers.

#define PLIC_BASE    0x0c000000L // Base address and per-pin priority array
#define PLIC_PENDING 0x0c001000L // Bit field matching currently pending pins
#define PLIC_ENABLED 0x0c002000L // Bit field corresponding to the current mask
#define PLIC_THRSHLD 0x0c200000L // Per-pin priority must be >= this to trigger
#define PLIC_CLAIM   0x0c200004L // Claim & completion register address
#endif /* __rocket__ */

static inline unsigned int irq_getie(void)
{
#if defined (__lm32__)
	unsigned int ie;
	__asm__ __volatile__("rcsr %0, IE" : "=r" (ie));
	return ie;
#elif defined (__or1k__)
	return !!(mfspr(SPR_SR) & SPR_SR_IEE);
#elif defined (__picorv32__)
	return _irq_enabled != 0;
#elif defined (__vexriscv__)
	return (csrr(mstatus) & CSR_MSTATUS_MIE) != 0;
#elif defined (__minerva__)
	return (csrr(mstatus) & CSR_MSTATUS_MIE) != 0;
#elif defined (__rocket__)
	return (csrr(mstatus) & CSR_MSTATUS_MIE) != 0;
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
#elif defined (__picorv32__)
    if (ie & 0x1)
        _irq_enable();
    else
        _irq_disable();
#elif defined (__vexriscv__)
	if(ie) csrs(mstatus,CSR_MSTATUS_MIE); else csrc(mstatus,CSR_MSTATUS_MIE);
#elif defined (__minerva__)
	if(ie) csrs(mstatus,CSR_MSTATUS_MIE); else csrc(mstatus,CSR_MSTATUS_MIE);
#elif defined (__rocket__)
	if(ie) csrs(mstatus,CSR_MSTATUS_MIE); else csrc(mstatus,CSR_MSTATUS_MIE);
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
#elif defined (__picorv32__)
    // PicoRV32 interrupt mask bits are high-disabled. This is the inverse of how
    // LiteX sees things.
    return ~_irq_mask;
#elif defined (__vexriscv__)
	unsigned int mask;
	asm volatile ("csrr %0, %1" : "=r"(mask) : "i"(CSR_IRQ_MASK));
	return mask;
#elif defined (__minerva__)
	unsigned int mask;
	asm volatile ("csrr %0, %1" : "=r"(mask) : "i"(CSR_IRQ_MASK));
	return mask;
#elif defined (__rocket__)
	return csr_readl(PLIC_ENABLED) >> 1;
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
#elif defined (__picorv32__)
    // PicoRV32 interrupt mask bits are high-disabled. This is the inverse of how
    // LiteX sees things.
    _irq_setmask(~mask);
#elif defined (__vexriscv__)
	asm volatile ("csrw %0, %1" :: "i"(CSR_IRQ_MASK), "r"(mask));
#elif defined (__minerva__)
	asm volatile ("csrw %0, %1" :: "i"(CSR_IRQ_MASK), "r"(mask));
#elif defined (__rocket__)
	csr_writel(mask << 1, PLIC_ENABLED);
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
#elif defined (__picorv32__)
	return _irq_pending;
#elif defined (__vexriscv__)
	unsigned int pending;
	asm volatile ("csrr %0, %1" : "=r"(pending) : "i"(CSR_IRQ_PENDING));
	return pending;
#elif defined (__minerva__)
	unsigned int pending;
	asm volatile ("csrr %0, %1" : "=r"(pending) : "i"(CSR_IRQ_PENDING));
	return pending;
#elif defined (__rocket__)
	return csr_readl(PLIC_PENDING) >> 1;
#else
#error Unsupported architecture
#endif
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
