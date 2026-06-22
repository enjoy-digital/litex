#ifndef CSR_DEFS__H
#define CSR_DEFS__H

#define CSR_MSTATUS_MIE 	0x8

#define CSR_MXSTATUS	0x7C0
#define CSR_MXSTATUS_THEADISAEE	(1 << 22)
#define CSR_MHCR	0x7C1
#define CSR_MHCR_IE		(1 << 0)
#define CSR_MHCR_DE		(1 << 1)
#define CSR_MHCR_BPE		(1 << 5)
#define CSR_MHCR_BTB		(1 << 6)
#define CSR_MCOR	0x7C2
#define CSR_MCOR_CACHE_SEL_I	(1 << 0)
#define CSR_MCOR_CACHE_SEL_D	(1 << 1)
#define CSR_MCOR_INV		(1 << 4)
#define CSR_MCOR_CLR		(1 << 5)
#define CSR_MCOR_BHT_INV	(1 << 16)
#define CSR_MCOR_BTB_INV	(1 << 17)

#endif	/* CSR_DEFS__H */
