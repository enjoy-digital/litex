#ifndef CSR_DEFS__H
#define CSR_DEFS__H

#define CSR_MSTATUS_MIE 0x8

// mie
#define CSR_IRQ_MASK 0x304

// mip
#define CSR_IRQ_PENDING 0x344

// first platform irq - enables offset in internal software
#define FIRQ_OFFSET     16

#endif	/* CSR_DEFS__H */
