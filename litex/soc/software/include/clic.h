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

/* CLIC Register Offsets (per interrupt) */
#define CLIC_INTIP_OFFSET    0x000 /* Interrupt pending */
#define CLIC_INTIE_OFFSET    0x400 /* Interrupt enable */
#define CLIC_INTATTR_OFFSET  0x800 /* Interrupt attributes */
#define CLIC_INTPRIO_OFFSET  0xC00 /* Interrupt priority */

/* Per-HART register offsets */
#define CLIC_MITHRESHOLD_OFFSET 0x1000 /* Interrupt threshold */

/* Helper functions for CLIC register access */
static inline uint8_t clic_get_intip(unsigned int irq) {
    return *((volatile uint8_t *)(CSR_CLIC_BASE + CLIC_INTIP_OFFSET + irq));
}

static inline void clic_set_intip(unsigned int irq, uint8_t value) {
    *((volatile uint8_t *)(CSR_CLIC_BASE + CLIC_INTIP_OFFSET + irq)) = value;
}

static inline uint8_t clic_get_intie(unsigned int irq) {
    return *((volatile uint8_t *)(CSR_CLIC_BASE + CLIC_INTIE_OFFSET + irq));
}

static inline void clic_set_intie(unsigned int irq, uint8_t value) {
    *((volatile uint8_t *)(CSR_CLIC_BASE + CLIC_INTIE_OFFSET + irq)) = value;
}

static inline uint8_t clic_get_intattr(unsigned int irq) {
    return *((volatile uint8_t *)(CSR_CLIC_BASE + CLIC_INTATTR_OFFSET + irq));
}

static inline void clic_set_intattr(unsigned int irq, uint8_t value) {
    *((volatile uint8_t *)(CSR_CLIC_BASE + CLIC_INTATTR_OFFSET + irq)) = value;
}

static inline uint8_t clic_get_intprio(unsigned int irq) {
    return *((volatile uint8_t *)(CSR_CLIC_BASE + CLIC_INTPRIO_OFFSET + irq));
}

static inline void clic_set_intprio(unsigned int irq, uint8_t value) {
    *((volatile uint8_t *)(CSR_CLIC_BASE + CLIC_INTPRIO_OFFSET + irq)) = value;
}

static inline uint8_t clic_get_mithreshold(unsigned int hart) {
    return *((volatile uint8_t *)(CSR_CLIC_BASE + CLIC_MITHRESHOLD_OFFSET + (hart * 0x1000)));
}

static inline void clic_set_mithreshold(unsigned int hart, uint8_t value) {
    *((volatile uint8_t *)(CSR_CLIC_BASE + CLIC_MITHRESHOLD_OFFSET + (hart * 0x1000))) = value;
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

#endif /* CSR_CLIC_BASE */

#ifdef __cplusplus
}
#endif

#endif /* __HW_CLIC_H */