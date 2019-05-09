#ifndef __HW_COMMON_H
#define __HW_COMMON_H

#include <stdint.h>

/* To overwrite CSR accessors, define extern, non-inlined versions
 * of csr_read[bwl]() and csr_write[bwl](), and define
 * CSR_ACCESSORS_DEFINED.
 */

#ifndef CSR_ACCESSORS_DEFINED
#define CSR_ACCESSORS_DEFINED

#ifdef __ASSEMBLER__
#define MMPTR(x) x
#else /* ! __ASSEMBLER__ */
#define MMPTR(x) (*((volatile unsigned int *)(x)))

static inline void csr_writeb(uint8_t value, unsigned long addr)
{
	*((volatile uint8_t *)addr) = value;
}

static inline uint8_t csr_readb(unsigned long addr)
{
	return *(volatile uint8_t *)addr;
}

static inline void csr_writew(uint16_t value, unsigned long addr)
{
	*((volatile uint16_t *)addr) = value;
}

static inline uint16_t csr_readw(unsigned long addr)
{
	return *(volatile uint16_t *)addr;
}

static inline void csr_writel(uint32_t value, unsigned long addr)
{
	*((volatile uint32_t *)addr) = value;
}

static inline uint32_t csr_readl(unsigned long addr)
{
	return *(volatile uint32_t *)addr;
}
#endif /* ! __ASSEMBLER__ */

#endif /* ! CSR_ACCESSORS_DEFINED */

#endif /* __HW_COMMON_H */
