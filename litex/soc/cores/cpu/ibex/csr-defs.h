#ifndef CSR_DEFS__H
#define CSR_DEFS__H

/*Reference : https://ibex-core.readthedocs.io/en/latest/03_reference/cs_registers.html# */

#define CSR_MSTATUS_MIE 0x8

#define CSR_IRQ_MASK    0x304
#define CSR_IRQ_PENDING 0x344
#define FIRQ_OFFSET     16
#define CSR_DCACHE_INFO 0xCC0


#endif	/* CSR_DEFS__H */
