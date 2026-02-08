#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>
#include <generated/mem.h>

// VexiiRiscv uses a Platform-Level Interrupt Controller (PLIC) which
// is programmed and queried via a set of MMIO registerss

// PLIC
#if defined(__riscv_plic__)

#define PLIC_PENDING (PLIC_BASE + 0x001000L) // Bit field matching currently pending pins
#define PLIC_ENABLED (PLIC_BASE + 0x002000L) // Bit field corresponding to the current mask
#define PLIC_THRSHLD (PLIC_BASE + 0x200000L) // Per-pin priority must be >= this to trigger
#define PLIC_CLAIM   (PLIC_BASE + 0x200004L) // Claim & completion register address

#else

// APLIC
#define APLIC_BASE           APLIC_M_BASE
#define APLIC_DOMAINCFG      (APLIC_BASE + 0x0000L)
#define APLIC_SOURCECFG      (APLIC_BASE + 0x0004L)
#define APLIC_SETIP          (APLIC_BASE + 0x1c00L)
#define APLIC_SETIPNUM       (APLIC_BASE + 0x1cdcL)
#define APLIC_CLRIP          (APLIC_BASE + 0x1d00L)
#define APLIC_CLRIPNUM       (APLIC_BASE + 0x1ddcL)
#define APLIC_SETIE          (APLIC_BASE + 0x1e00L)
#define APLIC_SETIENUM       (APLIC_BASE + 0x1edcL)
#define APLIC_CLRIE          (APLIC_BASE + 0x1f00L)
#define APLIC_CLRIENUM       (APLIC_BASE + 0x1fdcL)
#define APLIC_SETIENUM_LE    (APLIC_BASE + 0x2000L)
#define APLIC_SETIENUM_BE    (APLIC_BASE + 0x2004L)
#define APLIC_GENMSI         (APLIC_BASE + 0x3000L)
#define APLIC_TARGET         (APLIC_BASE + 0x3004L)

#define APLIC_IDC            (APLIC_BASE + 0x4000L)
#define APLIC_IDC_IDELIVERY  (APLIC_IDC + 0x00L)
#define APLIC_IDC_ITHRESHOLD (APLIC_IDC + 0x08L)
#define APLIC_IDC_TOPI       (APLIC_IDC + 0x18L)
#define APLIC_IDC_CLAIMI     (APLIC_IDC + 0x1cL)

#endif

#define PLIC_EXT_IRQ_BASE 0

static inline unsigned int irq_getie(void)
{
	return (csrr(mstatus) & CSR_MSTATUS_MIE) != 0;
}

static inline void irq_setie(unsigned int ie)
{
	if(ie) csrs(mstatus,CSR_MSTATUS_MIE); else csrc(mstatus,CSR_MSTATUS_MIE);
}

#if defined(__riscv_plic__)

static inline unsigned int irq_getmask(void)
{
	return *((unsigned int *)PLIC_ENABLED) >> PLIC_EXT_IRQ_BASE;
}

static inline void irq_setmask(unsigned int mask)
{
	*((unsigned int *)PLIC_ENABLED) = mask << PLIC_EXT_IRQ_BASE;
}

static inline unsigned int irq_pending(void)
{
	return *((unsigned int *)PLIC_PENDING) >> PLIC_EXT_IRQ_BASE;
}

#elif defined(__riscv_aplic__)

static inline unsigned int irq_getmask(void)
{
	return *((unsigned int *)(APLIC_SETIE));
}

static inline void irq_setmask(unsigned int mask)
{
	*((unsigned int *)(APLIC_SETIE)) = mask;
}

static inline unsigned int irq_pending(void)
{
	return *((unsigned int *)(APLIC_SETIP));
}

#endif

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
