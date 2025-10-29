#ifndef __IRQ_H
#define __IRQ_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <generated/csr.h>
#include <generated/soc.h>

// Standard RISC-V interrupt control functions for VexRiscv
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
	asm volatile ("csrr %0, %1" : "=r"(mask) : "i"(CSR_IRQ_MASK));
	return mask;
}

static inline void irq_setmask(unsigned int mask)
{
	asm volatile ("csrw %0, %1" :: "i"(CSR_IRQ_MASK), "r"(mask));
}

static inline unsigned int irq_pending(void)
{
	unsigned int pending;
	asm volatile ("csrr %0, %1" : "=r"(pending) : "i"(CSR_IRQ_PENDING));
	return pending;
}

// Standard RISC-V CSR addresses
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
// VexRiscv External Interrupt Array Support
// ============================================================================

// VexRiscv uses a 32-bit external interrupt array for peripheral interrupts
// Enable external interrupt for VexRiscv
static inline void vexriscv_external_interrupt_enable(void)
{
	csrs(mie, CSR_MIE_MEIE);
}

// Disable external interrupt for VexRiscv
static inline void vexriscv_external_interrupt_disable(void)
{
	csrc(mie, CSR_MIE_MEIE);
}

// Check if external interrupt is pending
static inline int vexriscv_external_interrupt_pending(void)
{
	return (csrr(mip) & CSR_MIP_MEIP) != 0;
}

// ============================================================================
// CLINT (Core Local Interruptor) Support for VexRiscv
// ============================================================================

#ifdef CSR_CLINT_BASE

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

// Convenience functions for timer delays
static inline void clint_timer_set_us(uint64_t us, uint64_t cpu_freq)
{
	uint64_t cycles = (us * cpu_freq) / 1000000;
	clint_timer_set_delay(cycles);
}

static inline void clint_timer_set_ms(uint64_t ms, uint64_t cpu_freq)
{
	uint64_t cycles = (ms * cpu_freq) / 1000;
	clint_timer_set_delay(cycles);
}

static inline void clint_timer_set_s(uint64_t s, uint64_t cpu_freq)
{
	uint64_t cycles = s * cpu_freq;
	clint_timer_set_delay(cycles);
}

#endif /* CSR_CLINT_BASE */

// ============================================================================
// CLIC (Core Local Interrupt Controller) Support for VexRiscv
// ============================================================================

#ifdef CSR_CLIC_BASE

// Read current CLIC interrupt ID (if available via CSR)
#ifdef CSR_CLIC_INTERRUPT_ID_STATUS_ADDR
static inline uint16_t vexriscv_clic_interrupt_id_read(void)
{
	return clic_interrupt_id_status_read();
}
#endif

// Read current CLIC interrupt priority (if available via CSR)
#ifdef CSR_CLIC_INTERRUPT_PRIORITY_STATUS_ADDR
static inline uint8_t vexriscv_clic_interrupt_priority_read(void)
{
	return clic_interrupt_priority_status_read();
}
#endif

// Check if CLIC interrupt is active (if available via CSR)
#ifdef CSR_CLIC_INTERRUPT_ACTIVE_STATUS_ADDR
static inline int vexriscv_clic_interrupt_active(void)
{
	return clic_interrupt_active_status_read() & 1;
}
#endif

// CLIC interrupt threshold control
static inline uint8_t clic_mithreshold_read(void)
{
	// For VexRiscv with CLIC, threshold is managed by CPU internally
	// Reading from the CPU's threshold CSR if available
#ifdef CSR_CPU_CLIC_THRESHOLD_ADDR
	return cpu_clic_threshold_read();
#else
	// Return 0 as default threshold (allow all priorities)
	return 0;
#endif
}

static inline void clic_mithreshold_write(uint8_t threshold)
{
	// For VexRiscv with CLIC, threshold is managed by CPU internally
	// This would need to be implemented via custom CSR instruction
	// For now, this is a no-op as the CPU manages threshold internally
	(void)threshold;
}

// Enable/disable specific CLIC interrupts (first 16 with direct CSR access)
static inline void clic_interrupt_enable(unsigned int interrupt)
{
	if (interrupt >= 16) return;
	
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

static inline void clic_interrupt_disable(unsigned int interrupt)
{
	if (interrupt >= 16) return;
	
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

// Set interrupt priority
static inline void clic_interrupt_set_priority(unsigned int interrupt, uint8_t priority)
{
	if (interrupt >= 16) return;
	
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

// VexRiscv-specific CLIC helper functions
// Since VexRiscv maps CLIC interrupt to external interrupt array bit 31,
// we need to enable/disable external interrupts for CLIC functionality

// Enable CLIC interrupt handling for VexRiscv (enables external interrupt)
static inline void vexriscv_clic_enable(void)
{
	vexriscv_external_interrupt_enable();
}

// Disable CLIC interrupt handling for VexRiscv
static inline void vexriscv_clic_disable(void)
{
	vexriscv_external_interrupt_disable();
}

// Check if CLIC interrupt is pending via external interrupt array
static inline int vexriscv_clic_pending(void)
{
	return vexriscv_external_interrupt_pending();
}

// CLIC trigger type constants
#define CLIC_TRIGGER_POSITIVE_LEVEL  0x00
#define CLIC_TRIGGER_POSITIVE_EDGE   0x01
#define CLIC_TRIGGER_NEGATIVE_LEVEL  0x02
#define CLIC_TRIGGER_NEGATIVE_EDGE   0x03

#endif /* CSR_CLIC_BASE */

#ifdef __cplusplus
}
#endif

#endif /* __IRQ_H */
