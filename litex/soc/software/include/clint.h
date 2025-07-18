// This file is Copyright (c) 2025 LiteX Contributors
// License: BSD

#ifndef __CLINT_H
#define __CLINT_H

#include <stdint.h>
#include <generated/csr.h>
#include <generated/mem.h>

#ifdef CSR_CLINT_BASE

// CLINT register offsets (from CLINT base address)
#define CLINT_MSIP_OFFSET      0x0000  // Machine Software Interrupt Pending
#define CLINT_MTIMECMP_OFFSET  0x4000  // Machine Timer Compare
#define CLINT_MTIME_OFFSET     0xBFF8  // Machine Timer

// RISC-V standard interrupt numbers
#define RISCV_IRQ_SOFTWARE     3   // Machine software interrupt
#define RISCV_IRQ_TIMER        7   // Machine timer interrupt
#define RISCV_IRQ_EXTERNAL     11  // Machine external interrupt

// Helper functions to access CLINT registers
static inline void clint_set_msip(int hart_id, uint32_t value) {
    // Access MSIP register via memory-mapped CSR (Wishbone2CSR bridge handles translation)
    #ifdef CSR_CLINT_MSIP_ADDR
    volatile uint32_t *msip = (volatile uint32_t *)(CSR_CLINT_MSIP_ADDR);
    uint32_t msip_val = *msip;
    if (value) {
        msip_val |= (1 << hart_id);
    } else {
        msip_val &= ~(1 << hart_id);
    }
    *msip = msip_val;
    #endif
}

static inline uint32_t clint_get_msip(int hart_id) {
    // Access MSIP register via memory-mapped CSR
    #ifdef CSR_CLINT_MSIP_ADDR
    volatile uint32_t *msip = (volatile uint32_t *)(CSR_CLINT_MSIP_ADDR);
    return (*msip >> hart_id) & 0x1;
    #else
    return 0;
    #endif
}

static inline uint64_t clint_get_mtime(void) {
    // Access MTIME registers via memory-mapped CSR
    #ifdef CSR_CLINT_MTIME_LOW_ADDR
        uint32_t lo, hi;
        // Read high first to detect rollover
        do {
            hi = *(volatile uint32_t *)(CSR_CLINT_MTIME_HIGH_ADDR);
            lo = *(volatile uint32_t *)(CSR_CLINT_MTIME_LOW_ADDR);
        } while (*(volatile uint32_t *)(CSR_CLINT_MTIME_HIGH_ADDR) != hi);
        return ((uint64_t)hi << 32) | lo;
    #else
        return 0;
    #endif
}

static inline void clint_set_mtimecmp(int hart_id, uint64_t value) {
    // Access MTIMECMP registers via memory-mapped CSR
    // For now, only HART 0 is supported
    #ifdef CSR_CLINT_MTIMECMP0_LOW_ADDR
        if (hart_id == 0) {
            // Write high first to avoid spurious interrupts
            *(volatile uint32_t *)(CSR_CLINT_MTIMECMP0_HIGH_ADDR) = 0xFFFFFFFF;
            *(volatile uint32_t *)(CSR_CLINT_MTIMECMP0_LOW_ADDR) = (uint32_t)value;
            *(volatile uint32_t *)(CSR_CLINT_MTIMECMP0_HIGH_ADDR) = (uint32_t)(value >> 32);
        }
    #endif
}

static inline uint64_t clint_get_mtimecmp(int hart_id) {
    // Access MTIMECMP registers via memory-mapped CSR
    // For now, only HART 0 is supported
    #ifdef CSR_CLINT_MTIMECMP0_LOW_ADDR
        if (hart_id == 0) {
            uint32_t lo = *(volatile uint32_t *)(CSR_CLINT_MTIMECMP0_LOW_ADDR);
            uint32_t hi = *(volatile uint32_t *)(CSR_CLINT_MTIMECMP0_HIGH_ADDR);
            return ((uint64_t)hi << 32) | lo;
        }
    #endif
    return 0;
}

#endif /* CSR_CLINT_BASE */

#endif /* __CLINT_H */