#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>

// VexiiRiscv uses a Platform-Level Interrupt Controller (PLIC) which
// is programmed and queried via a set of MMIO registerss

// PLIC
#define PLIC_BASE    0xf0c00000L // Base address and per-pin priority array
#define PLIC_PENDING 0xf0c01000L // Bit field matching currently pending pins
#define PLIC_ENABLED 0xf0c02000L // Bit field corresponding to the current mask
#define PLIC_THRSHLD 0xf0e00000L // Per-pin priority must be >= this to trigger
#define PLIC_CLAIM   0xf0e00004L // Claim & completion register address

// APLIC
#define APLIC_BASE 0xf0c00000L

#define domaincfgOffset     0x0000L
#define sourcecfgOffset     0x0004L
#define mmsiaddrcfgOffset   0x1BC0L
#define mmsiaddrcfghOffset  0x1BC4L
#define smsiaddrcfgOffset   0x1BC8L
#define smsiaddrcfghOffset  0x1BCCL
#define setipOffset         0x1C00L
#define setipnumOffset      0x1CDCL
#define in_clripOffset      0x1D00L
#define clripnumOffset      0x1DDCL
#define setieOffset         0x1E00L
#define setienumOffset      0x1EDCL
#define clrieOffset         0x1F00L
#define clrienumOffset      0x1FDCL
#define setipnum_leOffset   0x2000L
#define setipnum_beOffset   0x2004L
#define genmsiOffset        0x3000L
#define targetOffset        0x3004L

#define idcOffset           0x4000L
#define idcGroupSize        0x20L
#define ideliveryOffset     0x00L
#define iforceOffset        0x04L
#define ithresholdOffset    0x08L
#define topiOffset          0x18L
#define claimiOffset        0x1cL

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
	return *((unsigned int *)(APLIC_BASE + setieOffset));
}

static inline void irq_setmask(unsigned int mask)
{
	*((unsigned int *)(APLIC_BASE + setieOffset)) = mask;
}

static inline unsigned int irq_pending(void)
{
	return *((unsigned int *)(APLIC_BASE + setipOffset));
}

static inline void init_aplic(void)
{
	*((unsigned int *)(APLIC_BASE + domaincfgOffset)) = 0x80000000L;

	for (int i = 0; i < 31; i++) {
		*((unsigned int *)(APLIC_BASE + sourcecfgOffset) + i) = 0x6; // edge1
		*((unsigned int *)(APLIC_BASE + targetOffset) + i) = 0x0;
	}
	*((unsigned int *)(APLIC_BASE + idcOffset + ideliveryOffset)) = 0x1;
	*((unsigned int *)(APLIC_BASE + idcOffset + ithresholdOffset)) = 0x0;
	*((unsigned int *)(APLIC_BASE + setipOffset)) = 0x0;
}

#endif

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
