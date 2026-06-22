#ifndef __SYSTEM_H
#define __SYSTEM_H

#include <stdint.h>
#include <csr-defs.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CSR_ACCESSORS_DEFINED

#ifdef __ASSEMBLER__
#define MMPTR(x) x
#else /* ! __ASSEMBLER__ */
#define MMPTR(a) (*((volatile uint32_t *)(a)))

//As CVA5 will attempt to re-order loads before stores, a fence after I/O writes is required to ensure
//that subsequent loads (to different addresses) are not completed before this store
static inline void csr_write_simple(unsigned long v, unsigned long a)
{
  MMPTR(a) = v;
  asm volatile ("fence;");
}

static inline unsigned long csr_read_simple(unsigned long a)
{
  return MMPTR(a);
}
#endif /* ! __ASSEMBLER__ */

__attribute__((unused)) static void flush_cpu_icache(void) { };
__attribute__((unused)) static void flush_cpu_dcache(void) { };

void flush_l2_cache(void);

void busy_wait(unsigned int ms);
void busy_wait_us(unsigned int us);

#define csrr(reg) ({ unsigned long __tmp; \
  asm volatile ("csrr %0, " #reg : "=r"(__tmp)); \
  __tmp; })

#define csrw(reg, val) ({ \
  if (__builtin_constant_p(val) && (unsigned long)(val) < 32) \
	asm volatile ("csrw " #reg ", %0" :: "i"(val)); \
  else \
	asm volatile ("csrw " #reg ", %0" :: "r"(val)); })

#define csrs(reg, bit) ({ \
  if (__builtin_constant_p(bit) && (unsigned long)(bit) < 32) \
	asm volatile ("csrrs x0, " #reg ", %0" :: "i"(bit)); \
  else \
	asm volatile ("csrrs x0, " #reg ", %0" :: "r"(bit)); })

#define csrc(reg, bit) ({ \
  if (__builtin_constant_p(bit) && (unsigned long)(bit) < 32) \
	asm volatile ("csrrc x0, " #reg ", %0" :: "i"(bit)); \
  else \
	asm volatile ("csrrc x0, " #reg ", %0" :: "r"(bit)); })

#ifdef __cplusplus
}
#endif

#endif /* __SYSTEM_H */
