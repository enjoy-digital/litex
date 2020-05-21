#ifndef __SYSTEM_H
#define __SYSTEM_H

#ifdef __cplusplus
extern "C" {
#endif

#include <generated/csr.h>
#ifdef CSR_DEBUG_HELPER_TAG_SIZE
static void debug_helper_set_tag(const char *tag) {
	char val[CSR_DEBUG_HELPER_TAG_SIZE] = {0};
	int i;
	for(i = 0; i < CSR_DEBUG_HELPER_TAG_SIZE && tag[i] != 0; ++i) {
		val[i] = tag[i];
	}
	csr_wr_buf_uint8(CSR_DEBUG_HELPER_TAG_ADDR, val, CSR_DEBUG_HELPER_TAG_SIZE);
}
#else
#define debug_helper_set_tag(x)
#define debug_helper_arg_write(x)
#endif

void flush_cpu_icache(void);
void flush_cpu_dcache(void);
void flush_l2_cache(void);

void busy_wait(unsigned int ms);

#ifdef __or1k__
#include <spr-defs.h>
static inline unsigned long mfspr(unsigned long add)
{
	unsigned long ret;

	__asm__ __volatile__ ("l.mfspr %0,%1,0" : "=r" (ret) : "r" (add));

	return ret;
}

static inline void mtspr(unsigned long add, unsigned long val)
{
	__asm__ __volatile__ ("l.mtspr %0,%1,0" : : "r" (add), "r" (val));
}
#endif

#if defined(__vexriscv__) || defined(__minerva__) || defined(__rocket__) || defined(__blackparrot__)
#include <csr-defs.h>
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
#endif

#ifdef __cplusplus
}
#endif

#endif /* __SYSTEM_H */
