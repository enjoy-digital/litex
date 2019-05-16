#ifndef CSR_DEFS__H
#define CSR_DEFS__H

#define CSR_MSTATUS_MIE 0x8

#if defined (__vexriscv__)
#define CSR_IRQ_MASK 0xBC0
#define CSR_IRQ_PENDING 0xFC0
#endif

#if defined (__minerva__)
#define CSR_IRQ_MASK 0x330
#define CSR_IRQ_PENDING 0x360
#endif

#define CSR_DCACHE_INFO 0xCC0

#endif	/* CSR_DEFS__H */
