#ifndef CSR_DEFS__H
#define CSR_DEFS__H


#define CSR_MSTATUS_MIE 0x8

#define CSR_IRQ_MASK    0x344
#define CSR_IRQ_PENDING 0x304
#define FIRQ_OFFSET     16
#define CSR_DCACHE_INFO 0xCC0

#endif	/* CSR_DEFS__H */


/*
For CV32E41P from https://docs.openhwgroup.org/projects/openhw-group-cv32e41p/control_status_registers.html
Machine Interrupt Pending Register (mip): CSR_IRQ_MASK: 0x344
Machine Interrupt Enable Register (mie): CSR_IRQ_PENDING: 0x304
*/
