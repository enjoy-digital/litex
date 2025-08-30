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
	return (csrr(mstatus) & CSR_MSTATUS_MIE) != 0;
}

static inline void irq_setie(unsigned int ie)
{
	if(ie) csrs(mstatus,CSR_MSTATUS_MIE); else csrc(mstatus,CSR_MSTATUS_MIE);
}

static inline unsigned int irq_getmask(void)
{
	unsigned int mask;
	asm volatile ("csrr %0, %1" : "=r"(mask) : "i"(CSR_MIE));
	return (mask >> FIRQ_OFFSET);
}

static inline void irq_setmask(unsigned int mask)
{
	asm volatile ("csrw %0, %1" :: "i"(CSR_MIE), "r"(mask << FIRQ_OFFSET));
}

static inline unsigned int irq_pending(void)
{
	unsigned int pending;
	asm volatile ("csrr %0, %1" : "=r"(pending) : "i"(CSR_MIP));
	return (pending >> FIRQ_OFFSET);
}


// Standard RISC-V CSR addresses for CLINT support
#ifndef CSR_MIE
#define CSR_MIE    0x304  // Machine Interrupt Enable
#endif
#ifndef CSR_MIP
#define CSR_MIP    0x344  // Machine Interrupt Pending
#endif

// MIP register bit definitions for CLINT
#ifndef CSR_MIP_MSIP
#define CSR_MIP_MSIP   (1 << 3)  // Machine Software Interrupt Pending
#endif
#ifndef CSR_MIP_MTIP
#define CSR_MIP_MTIP   (1 << 7)  // Machine Timer Interrupt Pending
#endif
#ifndef CSR_MIP_MEIP
#define CSR_MIP_MEIP   (1 << 11) // Machine External Interrupt Pending
#endif

// MIE register bit definitions for CLINT
#ifndef CSR_MIE_MSIE
#define CSR_MIE_MSIE   (1 << 3)  // Machine Software Interrupt Enable
#endif
#ifndef CSR_MIE_MTIE
#define CSR_MIE_MTIE   (1 << 7)  // Machine Timer Interrupt Enable
#endif
#ifndef CSR_MIE_MEIE
#define CSR_MIE_MEIE   (1 << 11) // Machine External Interrupt Enable
#endif

// ============================================================================
// CLINT (Core Local Interruptor) Support
// ============================================================================

#ifdef CSR_CLINT_BASE

// CLINT register access functions
// These functions provide access to CLINT registers when CLINT is enabled

// Read 64-bit MTIME counter
static inline uint64_t clint_mtime_read(void)
{
	uint32_t lo, hi;
	// Read high first to detect rollover
	do {
		hi = clint_mtime_high_status_read();
		lo = clint_mtime_low_status_read();
	} while (clint_mtime_high_status_read() != hi);
	return ((uint64_t)hi << 32) | lo;
}

// Write 64-bit MTIMECMP value for HART 0
static inline void clint_mtimecmp_write(uint64_t value)
{
	// Write high first to avoid spurious interrupts
	clint_mtimecmp0_high_storage_write(0xFFFFFFFF);
	clint_mtimecmp0_low_storage_write((uint32_t)value);
	clint_mtimecmp0_high_storage_write((uint32_t)(value >> 32));
}

// Read 64-bit MTIMECMP value for HART 0
static inline uint64_t clint_mtimecmp_read(void)
{
	uint32_t lo = clint_mtimecmp0_low_storage_read();
	uint32_t hi = clint_mtimecmp0_high_storage_read();
	return ((uint64_t)hi << 32) | lo;
}

// Trigger software interrupt
static inline void clint_software_interrupt_trigger(void)
{
	clint_msip_storage_write(1);
}

// Clear software interrupt
static inline void clint_software_interrupt_clear(void)
{
	clint_msip_storage_write(0);
}

// Check if software interrupt is pending
static inline int clint_software_interrupt_pending(void)
{
	return clint_msip_storage_read() & 1;
}

// Set timer interrupt for a specific delay (in clock cycles)
static inline void clint_timer_set_delay(uint64_t delay)
{
	uint64_t current = clint_mtime_read();
	clint_mtimecmp_write(current + delay);
}

// Set timer interrupt for a specific absolute time
static inline void clint_timer_set_absolute(uint64_t time)
{
	clint_mtimecmp_write(time);
}

// Disable timer interrupt (set to maximum value)
static inline void clint_timer_disable(void)
{
	clint_mtimecmp_write(0xFFFFFFFFFFFFFFFFULL);
}

// CLINT interrupt enable/disable functions
// These work with the standard RISC-V interrupt bits

// Enable timer interrupt (MTIE bit in MIE)
static inline void clint_timer_interrupt_enable(void)
{
	csrs(mie, CSR_MIE_MTIE);
}

// Disable timer interrupt (MTIE bit in MIE)
static inline void clint_timer_interrupt_disable(void)
{
	csrc(mie, CSR_MIE_MTIE);
}

// Enable software interrupt (MSIE bit in MIE)
static inline void clint_software_interrupt_enable(void)
{
	csrs(mie, CSR_MIE_MSIE);
}

// Disable software interrupt (MSIE bit in MIE)
static inline void clint_software_interrupt_disable(void)
{
	csrc(mie, CSR_MIE_MSIE);
}

// Check if timer interrupt is pending (MTIP bit in MIP)
static inline int clint_timer_interrupt_pending(void)
{
	return (csrr(mip) & CSR_MIP_MTIP) != 0;
}

// Convenience functions for common operations

// Set timer for microsecond delay (requires CPU frequency)
static inline void clint_timer_set_us(uint64_t us, uint64_t cpu_freq)
{
	uint64_t cycles = (us * cpu_freq) / 1000000;
	clint_timer_set_delay(cycles);
}

// Set timer for millisecond delay (requires CPU frequency)
static inline void clint_timer_set_ms(uint64_t ms, uint64_t cpu_freq)
{
	uint64_t cycles = (ms * cpu_freq) / 1000;
	clint_timer_set_delay(cycles);
}

// Set timer for second delay (requires CPU frequency)
static inline void clint_timer_set_s(uint64_t s, uint64_t cpu_freq)
{
	uint64_t cycles = s * cpu_freq;
	clint_timer_set_delay(cycles);
}

#endif /* CSR_CLINT_BASE */

// ============================================================================
// CLIC (Core Local Interrupt Controller) Support
// ============================================================================

#ifdef CSR_CLIC_BASE

// CLIC register access functions
// These functions provide access to CLIC registers when CLIC is enabled

// Read interrupt threshold
static inline uint8_t clic_mithreshold_read(void)
{
	return clic_mithreshold0_storage_read();
}

// Write interrupt threshold
static inline void clic_mithreshold_write(uint8_t threshold)
{
	clic_mithreshold0_storage_write(threshold);
}

// Get interrupt enable for a specific interrupt (for first 16 interrupts with direct CSR access)
static inline int clic_interrupt_enabled(unsigned int interrupt)
{
	if (interrupt >= 16) return 0;  // Only first 16 interrupts have direct CSR access
	
	switch(interrupt) {
#ifdef CSR_CLIC_CLICINTIE0_STORAGE_ADDR
		case 0: return clic_clicintie0_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE1_STORAGE_ADDR
		case 1: return clic_clicintie1_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE2_STORAGE_ADDR
		case 2: return clic_clicintie2_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE3_STORAGE_ADDR
		case 3: return clic_clicintie3_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE4_STORAGE_ADDR
		case 4: return clic_clicintie4_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE5_STORAGE_ADDR
		case 5: return clic_clicintie5_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE6_STORAGE_ADDR
		case 6: return clic_clicintie6_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE7_STORAGE_ADDR
		case 7: return clic_clicintie7_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE8_STORAGE_ADDR
		case 8: return clic_clicintie8_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE9_STORAGE_ADDR
		case 9: return clic_clicintie9_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE10_STORAGE_ADDR
		case 10: return clic_clicintie10_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE11_STORAGE_ADDR
		case 11: return clic_clicintie11_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE12_STORAGE_ADDR
		case 12: return clic_clicintie12_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE13_STORAGE_ADDR
		case 13: return clic_clicintie13_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE14_STORAGE_ADDR
		case 14: return clic_clicintie14_storage_read();
#endif
#ifdef CSR_CLIC_CLICINTIE15_STORAGE_ADDR
		case 15: return clic_clicintie15_storage_read();
#endif
		default: return 0;
	}
}

// Enable a specific interrupt
static inline void clic_interrupt_enable(unsigned int interrupt)
{
	if (interrupt >= 16) return;  // Only first 16 interrupts have direct CSR access
	
	switch(interrupt) {
#ifdef CSR_CLIC_CLICINTIE0_STORAGE_ADDR
		case 0: clic_clicintie0_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE1_STORAGE_ADDR
		case 1: clic_clicintie1_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE2_STORAGE_ADDR
		case 2: clic_clicintie2_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE3_STORAGE_ADDR
		case 3: clic_clicintie3_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE4_STORAGE_ADDR
		case 4: clic_clicintie4_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE5_STORAGE_ADDR
		case 5: clic_clicintie5_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE6_STORAGE_ADDR
		case 6: clic_clicintie6_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE7_STORAGE_ADDR
		case 7: clic_clicintie7_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE8_STORAGE_ADDR
		case 8: clic_clicintie8_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE9_STORAGE_ADDR
		case 9: clic_clicintie9_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE10_STORAGE_ADDR
		case 10: clic_clicintie10_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE11_STORAGE_ADDR
		case 11: clic_clicintie11_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE12_STORAGE_ADDR
		case 12: clic_clicintie12_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE13_STORAGE_ADDR
		case 13: clic_clicintie13_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE14_STORAGE_ADDR
		case 14: clic_clicintie14_storage_write(1); break;
#endif
#ifdef CSR_CLIC_CLICINTIE15_STORAGE_ADDR
		case 15: clic_clicintie15_storage_write(1); break;
#endif
	}
}

// Disable a specific interrupt
static inline void clic_interrupt_disable(unsigned int interrupt)
{
	if (interrupt >= 16) return;  // Only first 16 interrupts have direct CSR access
	
	switch(interrupt) {
#ifdef CSR_CLIC_CLICINTIE0_STORAGE_ADDR
		case 0: clic_clicintie0_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE1_STORAGE_ADDR
		case 1: clic_clicintie1_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE2_STORAGE_ADDR
		case 2: clic_clicintie2_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE3_STORAGE_ADDR
		case 3: clic_clicintie3_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE4_STORAGE_ADDR
		case 4: clic_clicintie4_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE5_STORAGE_ADDR
		case 5: clic_clicintie5_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE6_STORAGE_ADDR
		case 6: clic_clicintie6_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE7_STORAGE_ADDR
		case 7: clic_clicintie7_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE8_STORAGE_ADDR
		case 8: clic_clicintie8_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE9_STORAGE_ADDR
		case 9: clic_clicintie9_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE10_STORAGE_ADDR
		case 10: clic_clicintie10_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE11_STORAGE_ADDR
		case 11: clic_clicintie11_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE12_STORAGE_ADDR
		case 12: clic_clicintie12_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE13_STORAGE_ADDR
		case 13: clic_clicintie13_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE14_STORAGE_ADDR
		case 14: clic_clicintie14_storage_write(0); break;
#endif
#ifdef CSR_CLIC_CLICINTIE15_STORAGE_ADDR
		case 15: clic_clicintie15_storage_write(0); break;
#endif
	}
}

// Check if interrupt is pending
static inline int clic_interrupt_pending(unsigned int interrupt)
{
	if (interrupt >= 16) return 0;  // Only first 16 interrupts have direct CSR access
	
	switch(interrupt) {
#ifdef CSR_CLIC_CLICINTIP0_STATUS_ADDR
		case 0: return clic_clicintip0_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP1_STATUS_ADDR
		case 1: return clic_clicintip1_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP2_STATUS_ADDR
		case 2: return clic_clicintip2_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP3_STATUS_ADDR
		case 3: return clic_clicintip3_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP4_STATUS_ADDR
		case 4: return clic_clicintip4_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP5_STATUS_ADDR
		case 5: return clic_clicintip5_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP6_STATUS_ADDR
		case 6: return clic_clicintip6_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP7_STATUS_ADDR
		case 7: return clic_clicintip7_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP8_STATUS_ADDR
		case 8: return clic_clicintip8_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP9_STATUS_ADDR
		case 9: return clic_clicintip9_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP10_STATUS_ADDR
		case 10: return clic_clicintip10_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP11_STATUS_ADDR
		case 11: return clic_clicintip11_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP12_STATUS_ADDR
		case 12: return clic_clicintip12_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP13_STATUS_ADDR
		case 13: return clic_clicintip13_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP14_STATUS_ADDR
		case 14: return clic_clicintip14_status_read();
#endif
#ifdef CSR_CLIC_CLICINTIP15_STATUS_ADDR
		case 15: return clic_clicintip15_status_read();
#endif
		default: return 0;
	}
}

// Set interrupt priority
static inline void clic_interrupt_set_priority(unsigned int interrupt, uint8_t priority)
{
	if (interrupt >= 16) return;  // Only first 16 interrupts have direct CSR access
	
	switch(interrupt) {
#ifdef CSR_CLIC_CLICIPRIO0_STORAGE_ADDR
		case 0: clic_cliciprio0_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO1_STORAGE_ADDR
		case 1: clic_cliciprio1_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO2_STORAGE_ADDR
		case 2: clic_cliciprio2_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO3_STORAGE_ADDR
		case 3: clic_cliciprio3_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO4_STORAGE_ADDR
		case 4: clic_cliciprio4_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO5_STORAGE_ADDR
		case 5: clic_cliciprio5_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO6_STORAGE_ADDR
		case 6: clic_cliciprio6_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO7_STORAGE_ADDR
		case 7: clic_cliciprio7_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO8_STORAGE_ADDR
		case 8: clic_cliciprio8_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO9_STORAGE_ADDR
		case 9: clic_cliciprio9_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO10_STORAGE_ADDR
		case 10: clic_cliciprio10_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO11_STORAGE_ADDR
		case 11: clic_cliciprio11_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO12_STORAGE_ADDR
		case 12: clic_cliciprio12_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO13_STORAGE_ADDR
		case 13: clic_cliciprio13_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO14_STORAGE_ADDR
		case 14: clic_cliciprio14_storage_write(priority); break;
#endif
#ifdef CSR_CLIC_CLICIPRIO15_STORAGE_ADDR
		case 15: clic_cliciprio15_storage_write(priority); break;
#endif
	}
}

// Set interrupt attributes (trigger type and polarity)
// Bits 1:0 - trigger type: 00=pos level, 01=pos edge, 10=neg level, 11=neg edge
static inline void clic_interrupt_set_attributes(unsigned int interrupt, uint8_t attributes)
{
	if (interrupt >= 16) return;  // Only first 16 interrupts have direct CSR access
	
	switch(interrupt) {
#ifdef CSR_CLIC_CLICINTATTR0_STORAGE_ADDR
		case 0: clic_clicintattr0_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR1_STORAGE_ADDR
		case 1: clic_clicintattr1_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR2_STORAGE_ADDR
		case 2: clic_clicintattr2_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR3_STORAGE_ADDR
		case 3: clic_clicintattr3_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR4_STORAGE_ADDR
		case 4: clic_clicintattr4_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR5_STORAGE_ADDR
		case 5: clic_clicintattr5_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR6_STORAGE_ADDR
		case 6: clic_clicintattr6_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR7_STORAGE_ADDR
		case 7: clic_clicintattr7_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR8_STORAGE_ADDR
		case 8: clic_clicintattr8_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR9_STORAGE_ADDR
		case 9: clic_clicintattr9_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR10_STORAGE_ADDR
		case 10: clic_clicintattr10_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR11_STORAGE_ADDR
		case 11: clic_clicintattr11_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR12_STORAGE_ADDR
		case 12: clic_clicintattr12_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR13_STORAGE_ADDR
		case 13: clic_clicintattr13_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR14_STORAGE_ADDR
		case 14: clic_clicintattr14_storage_write(attributes); break;
#endif
#ifdef CSR_CLIC_CLICINTATTR15_STORAGE_ADDR
		case 15: clic_clicintattr15_storage_write(attributes); break;
#endif
	}
}

// Minerva-specific CLIC helper functions
// Since Minerva maps CLIC interrupt to fast interrupt array bit 15 (highest bit in 16-bit array),
// we need to enable/disable external interrupts for CLIC functionality

// Enable external interrupt for Minerva (MEIE bit in MIE)
static inline void minerva_external_interrupt_enable(void)
{
	csrs(mie, CSR_MIE_MEIE);
}

// Disable external interrupt for Minerva
static inline void minerva_external_interrupt_disable(void)
{
	csrc(mie, CSR_MIE_MEIE);
}

// Check if external interrupt is pending
static inline int minerva_external_interrupt_pending(void)
{
	return (csrr(mip) & CSR_MIP_MEIP) != 0;
}

// Enable CLIC interrupt handling for Minerva (enables external interrupt)
static inline void minerva_clic_enable(void)
{
	minerva_external_interrupt_enable();
}

// Disable CLIC interrupt handling for Minerva
static inline void minerva_clic_disable(void)
{
	minerva_external_interrupt_disable();
}

// Check if CLIC interrupt is pending via external interrupt array
static inline int minerva_clic_pending(void)
{
	return minerva_external_interrupt_pending();
}

// Attribute constants for convenience
#define CLIC_TRIGGER_POSITIVE_LEVEL  0x00
#define CLIC_TRIGGER_POSITIVE_EDGE   0x01
#define CLIC_TRIGGER_NEGATIVE_LEVEL  0x02
#define CLIC_TRIGGER_NEGATIVE_EDGE   0x03

#endif /* CSR_CLIC_BASE */

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
