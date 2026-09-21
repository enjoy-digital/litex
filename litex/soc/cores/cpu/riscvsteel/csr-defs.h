#ifndef CSR_DEFS__H
#define CSR_DEFS__H

/*Reference : https://github.com/riscv-steel/libsteel/blob/main/libsteel/csr.h */

#define CSR_MSTATUS_MIE 0x8

#define CSR_IRQ_MASK    0x304
#define CSR_IRQ_PENDING 0x344
#define FIRQ_OFFSET     16

#endif	/* CSR_DEFS__H */
