// (c) 2020 Raptor Engineering, LLC <sales@raptorengineering.com>

#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>
#include <generated/mem.h>

// Address of exception / IRQ handler routine
extern void * __rom_isr_address;
void isr(uint64_t vec);

// External interrupt enable bit
#define PPC_MSR_EE_SHIFT	15

// XICS registers
#define PPC_XICS_XIRR_POLL	0x0
#define PPC_XICS_XIRR		0x4
#define PPC_XICS_RESV		0x8
#define PPC_XICS_MFRR		0xc

// Must match corresponding XICS ICS HDL parameter
#define PPC_XICS_SRC_NUM	16

// Default external interrupt priority set by software during IRQ enable
#define PPC_EXT_INTERRUPT_PRIO	0x08

uint8_t inline xics_icp_readb(int reg)
{
	return *((uint8_t*)(HOSTXICSICP_BASE + reg));
}

void inline xics_icp_writeb(int reg, uint8_t value)
{
	*((uint8_t*)(HOSTXICSICP_BASE + reg)) = value;
}

uint32_t inline xics_icp_readw(int reg)
{
	return *((uint32_t*)(HOSTXICSICP_BASE + reg));
}

void inline xics_icp_writew(int reg, uint32_t value)
{
	*((uint32_t*)(HOSTXICSICP_BASE + reg)) = value;
}

uint32_t inline xics_ics_read_xive(int irq_number)
{
	return *((uint32_t*)(HOSTXICSICS_BASE + 0x800 + (irq_number << 2)));
}

void inline xics_ics_write_xive(int irq_number, uint32_t priority)
{
	*((uint32_t*)(HOSTXICSICS_BASE + 0x800 + (irq_number << 2))) = priority;
}

void inline mtmsrd(uint64_t val)
{
	__asm__ volatile("mtmsrd %0" : : "r" (val) : "memory");
}

uint64_t inline mfmsr(void)
{
	uint64_t rval;
	__asm__ volatile("mfmsr %0" : "=r" (rval) : : "memory");
	return rval;
}

void inline mtdec(uint64_t val)
{
	__asm__ volatile("mtdec %0" : : "r" (val) : "memory");
}

uint64_t inline mfdec(void)
{
	uint64_t rval;
	__asm__ volatile("mfdec %0" : "=r" (rval) : : "memory");
	return rval;
}

static inline unsigned int irq_getie(void)
{
	return (mfmsr() & (1 << PPC_MSR_EE_SHIFT)) != 0;
}

static inline void irq_setie(unsigned int ie)
{
	if (ie)
	{
		// Unmask all IRQs
		xics_icp_writeb(PPC_XICS_XIRR, 0xff);

		// Enable DEC + external interrupts
		mtmsrd(mfmsr() | (1 << PPC_MSR_EE_SHIFT));
	}
	else
	{
		// Disable DEC + external interrupts
		mtmsrd(mfmsr() & ~(1 << PPC_MSR_EE_SHIFT));

		// Mask all IRQs
		xics_icp_writeb(PPC_XICS_XIRR, 0x00);
	}
}

static inline unsigned int irq_getmask(void)
{
	// Compute mask from enabled external interrupts in ICS
	uint32_t mask;
	int irq;
	mask = 0;
	for (irq = PPC_XICS_SRC_NUM - 1; irq >= 0; irq--) {
		mask = mask << 1;
		if ((xics_ics_read_xive(irq) & 0xff) != 0xff)
			mask |= 0x1;
	}
	return mask;
}

static inline void irq_setmask(unsigned int mask)
{
	int irq;

	// Enable all interrupts at a fixed priority level for now
	int priority_level = PPC_EXT_INTERRUPT_PRIO;

	// Iterate over IRQs configured in mask, and enable / mask in ICS
	for (irq = 0; irq < PPC_XICS_SRC_NUM; irq++) {
		if ((mask >> irq) & 0x1)
			xics_ics_write_xive(irq, priority_level);
		else
			xics_ics_write_xive(irq, 0xff);
	}
}

static inline unsigned int irq_pending(void)
{
	// Compute pending interrupt bitmask from asserted external interrupts in ICS
	uint32_t pending;
	int irq;
	pending = 0;
	for (irq = PPC_XICS_SRC_NUM - 1; irq >= 0; irq--) {
		pending = pending << 1;
		if ((xics_ics_read_xive(irq) & (0x1 << 31)) != 0)
			pending |= 0x1;
	}
	return pending;
}

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
