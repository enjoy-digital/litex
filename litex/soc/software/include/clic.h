#ifndef __HW_CLIC_H
#define __HW_CLIC_H

#ifdef __cplusplus
extern "C" {
#endif

#include <system.h>
#include <stdint.h>
#include <stdbool.h>
#include <generated/csr.h>

#ifdef CSR_CLIC_BASE

/* CLIC Configuration */
#define CLIC_NUM_INTERRUPTS  16    /* Number of interrupts exposed via CSR in hardware */

/* CLIC CSR Definitions */
#define CSR_MCLICBASE        0x341 /* Base address for CLIC memory-mapped registers */

/* CLIC Interrupt Attributes */
#define CLIC_ATTR_TRIG_MASK  0x03
#define CLIC_ATTR_TRIG_POS   0
#define CLIC_ATTR_TRIG_EDGE  0x02
#define CLIC_ATTR_TRIG_LEVEL 0x00
#define CLIC_ATTR_POL_MASK   0x04
#define CLIC_ATTR_POL_POS    2
#define CLIC_ATTR_POL_NEG    0x00
#define CLIC_ATTR_POL_POS    0x04

/* Hardware actual register layout (sequential per interrupt):
 * For each interrupt N:
 *   clicintieN   at offset (N * 0x10) + 0x0
 *   clicintipN   at offset (N * 0x10) + 0x4
 *   cliciprioN   at offset (N * 0x10) + 0x8
 *   clicintattr  at offset (N * 0x10) + 0xC
 */

/* Helper functions for CLIC register access - using generated CSR accessors */
static inline uint32_t clic_get_intip(unsigned int irq) {
    if (irq >= CLIC_NUM_INTERRUPTS) return 0;
    switch(irq) {
        case 0: return clic_clicintip0_read();
        case 1: return clic_clicintip1_read();
        case 2: return clic_clicintip2_read();
        case 3: return clic_clicintip3_read();
        case 4: return clic_clicintip4_read();
        case 5: return clic_clicintip5_read();
        case 6: return clic_clicintip6_read();
        case 7: return clic_clicintip7_read();
        case 8: return clic_clicintip8_read();
        case 9: return clic_clicintip9_read();
        case 10: return clic_clicintip10_read();
        case 11: return clic_clicintip11_read();
        case 12: return clic_clicintip12_read();
        case 13: return clic_clicintip13_read();
        case 14: return clic_clicintip14_read();
        case 15: return clic_clicintip15_read();
        default: return 0;
    }
}

static inline void clic_set_intip(unsigned int irq, uint32_t value) {
    if (irq >= CLIC_NUM_INTERRUPTS) return;
    switch(irq) {
        case 0: clic_clicintip0_write(value); break;
        case 1: clic_clicintip1_write(value); break;
        case 2: clic_clicintip2_write(value); break;
        case 3: clic_clicintip3_write(value); break;
        case 4: clic_clicintip4_write(value); break;
        case 5: clic_clicintip5_write(value); break;
        case 6: clic_clicintip6_write(value); break;
        case 7: clic_clicintip7_write(value); break;
        case 8: clic_clicintip8_write(value); break;
        case 9: clic_clicintip9_write(value); break;
        case 10: clic_clicintip10_write(value); break;
        case 11: clic_clicintip11_write(value); break;
        case 12: clic_clicintip12_write(value); break;
        case 13: clic_clicintip13_write(value); break;
        case 14: clic_clicintip14_write(value); break;
        case 15: clic_clicintip15_write(value); break;
    }
}

static inline uint32_t clic_get_intie(unsigned int irq) {
    if (irq >= CLIC_NUM_INTERRUPTS) return 0;
    switch(irq) {
        case 0: return clic_clicintie0_read();
        case 1: return clic_clicintie1_read();
        case 2: return clic_clicintie2_read();
        case 3: return clic_clicintie3_read();
        case 4: return clic_clicintie4_read();
        case 5: return clic_clicintie5_read();
        case 6: return clic_clicintie6_read();
        case 7: return clic_clicintie7_read();
        case 8: return clic_clicintie8_read();
        case 9: return clic_clicintie9_read();
        case 10: return clic_clicintie10_read();
        case 11: return clic_clicintie11_read();
        case 12: return clic_clicintie12_read();
        case 13: return clic_clicintie13_read();
        case 14: return clic_clicintie14_read();
        case 15: return clic_clicintie15_read();
        default: return 0;
    }
}

static inline void clic_set_intie(unsigned int irq, uint32_t value) {
    if (irq >= CLIC_NUM_INTERRUPTS) return;
    switch(irq) {
        case 0: clic_clicintie0_write(value); break;
        case 1: clic_clicintie1_write(value); break;
        case 2: clic_clicintie2_write(value); break;
        case 3: clic_clicintie3_write(value); break;
        case 4: clic_clicintie4_write(value); break;
        case 5: clic_clicintie5_write(value); break;
        case 6: clic_clicintie6_write(value); break;
        case 7: clic_clicintie7_write(value); break;
        case 8: clic_clicintie8_write(value); break;
        case 9: clic_clicintie9_write(value); break;
        case 10: clic_clicintie10_write(value); break;
        case 11: clic_clicintie11_write(value); break;
        case 12: clic_clicintie12_write(value); break;
        case 13: clic_clicintie13_write(value); break;
        case 14: clic_clicintie14_write(value); break;
        case 15: clic_clicintie15_write(value); break;
    }
}

static inline uint32_t clic_get_intattr(unsigned int irq) {
    if (irq >= CLIC_NUM_INTERRUPTS) return 0;
    switch(irq) {
        case 0: return clic_clicintattr0_read();
        case 1: return clic_clicintattr1_read();
        case 2: return clic_clicintattr2_read();
        case 3: return clic_clicintattr3_read();
        case 4: return clic_clicintattr4_read();
        case 5: return clic_clicintattr5_read();
        case 6: return clic_clicintattr6_read();
        case 7: return clic_clicintattr7_read();
        case 8: return clic_clicintattr8_read();
        case 9: return clic_clicintattr9_read();
        case 10: return clic_clicintattr10_read();
        case 11: return clic_clicintattr11_read();
        case 12: return clic_clicintattr12_read();
        case 13: return clic_clicintattr13_read();
        case 14: return clic_clicintattr14_read();
        case 15: return clic_clicintattr15_read();
        default: return 0;
    }
}

static inline void clic_set_intattr(unsigned int irq, uint32_t value) {
    if (irq >= CLIC_NUM_INTERRUPTS) return;
    switch(irq) {
        case 0: clic_clicintattr0_write(value); break;
        case 1: clic_clicintattr1_write(value); break;
        case 2: clic_clicintattr2_write(value); break;
        case 3: clic_clicintattr3_write(value); break;
        case 4: clic_clicintattr4_write(value); break;
        case 5: clic_clicintattr5_write(value); break;
        case 6: clic_clicintattr6_write(value); break;
        case 7: clic_clicintattr7_write(value); break;
        case 8: clic_clicintattr8_write(value); break;
        case 9: clic_clicintattr9_write(value); break;
        case 10: clic_clicintattr10_write(value); break;
        case 11: clic_clicintattr11_write(value); break;
        case 12: clic_clicintattr12_write(value); break;
        case 13: clic_clicintattr13_write(value); break;
        case 14: clic_clicintattr14_write(value); break;
        case 15: clic_clicintattr15_write(value); break;
    }
}

static inline uint32_t clic_get_intprio(unsigned int irq) {
    if (irq >= CLIC_NUM_INTERRUPTS) return 0;
    switch(irq) {
        case 0: return clic_cliciprio0_read();
        case 1: return clic_cliciprio1_read();
        case 2: return clic_cliciprio2_read();
        case 3: return clic_cliciprio3_read();
        case 4: return clic_cliciprio4_read();
        case 5: return clic_cliciprio5_read();
        case 6: return clic_cliciprio6_read();
        case 7: return clic_cliciprio7_read();
        case 8: return clic_cliciprio8_read();
        case 9: return clic_cliciprio9_read();
        case 10: return clic_cliciprio10_read();
        case 11: return clic_cliciprio11_read();
        case 12: return clic_cliciprio12_read();
        case 13: return clic_cliciprio13_read();
        case 14: return clic_cliciprio14_read();
        case 15: return clic_cliciprio15_read();
        default: return 0;
    }
}

static inline void clic_set_intprio(unsigned int irq, uint32_t value) {
    if (irq >= CLIC_NUM_INTERRUPTS) return;
    switch(irq) {
        case 0: clic_cliciprio0_write(value); break;
        case 1: clic_cliciprio1_write(value); break;
        case 2: clic_cliciprio2_write(value); break;
        case 3: clic_cliciprio3_write(value); break;
        case 4: clic_cliciprio4_write(value); break;
        case 5: clic_cliciprio5_write(value); break;
        case 6: clic_cliciprio6_write(value); break;
        case 7: clic_cliciprio7_write(value); break;
        case 8: clic_cliciprio8_write(value); break;
        case 9: clic_cliciprio9_write(value); break;
        case 10: clic_cliciprio10_write(value); break;
        case 11: clic_cliciprio11_write(value); break;
        case 12: clic_cliciprio12_write(value); break;
        case 13: clic_cliciprio13_write(value); break;
        case 14: clic_cliciprio14_write(value); break;
        case 15: clic_cliciprio15_write(value); break;
    }
}

/* Note: mithreshold is controlled by CPU, not exposed via CSR in this implementation */
static inline uint8_t clic_get_mithreshold(unsigned int hart) {
    /* Not implemented in this hardware configuration */
    return 0;
}

static inline void clic_set_mithreshold(unsigned int hart, uint8_t value) {
    /* Not implemented in this hardware configuration */
    /* The CPU controls threshold via clicThreshold signal */
}

/* Higher-level helper functions */
static inline void clic_enable_interrupt(unsigned int irq) {
    clic_set_intie(irq, 1);
}

static inline void clic_disable_interrupt(unsigned int irq) {
    clic_set_intie(irq, 0);
}

static inline bool clic_is_pending(unsigned int irq) {
    return clic_get_intip(irq) != 0;
}

static inline void clic_clear_pending(unsigned int irq) {
    clic_set_intip(irq, 0);
}

static inline void clic_set_pending(unsigned int irq) {
    clic_set_intip(irq, 1);
}

static inline void clic_configure_interrupt(unsigned int irq, uint8_t priority, bool edge_triggered, bool positive_polarity) {
    uint8_t attr = 0;
    if (edge_triggered) {
        attr |= CLIC_ATTR_TRIG_EDGE;
    }
    if (positive_polarity) {
        attr |= CLIC_ATTR_POL_POS;
    }
    clic_set_intattr(irq, attr);
    clic_set_intprio(irq, priority);
}

/* Alternative function names with more intuitive action-based interface */
static inline void clic_enable_interrupt_fixed(unsigned int irq) {
    clic_enable_interrupt(irq);
}

static inline void clic_disable_interrupt_fixed(unsigned int irq) {
    clic_disable_interrupt(irq);
}

static inline void clic_set_pending_fixed(unsigned int irq) {
    clic_set_pending(irq);
}

static inline void clic_clear_pending_fixed(unsigned int irq) {
    clic_clear_pending(irq);
}

static inline bool clic_is_pending_fixed(unsigned int irq) {
    return clic_is_pending(irq);
}

static inline void clic_set_priority_fixed(unsigned int irq, uint8_t priority) {
    clic_set_intprio(irq, priority);
}

static inline void clic_configure_interrupt_fixed(unsigned int irq, uint8_t priority, bool edge_triggered, bool positive_polarity) {
    clic_configure_interrupt(irq, priority, edge_triggered, positive_polarity);
}

#endif /* CSR_CLIC_BASE */

#ifdef __cplusplus
}
#endif

#endif /* __HW_CLIC_H */