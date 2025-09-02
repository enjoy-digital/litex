#ifndef __SYSTEM_H
#define __SYSTEM_H

#include <csr-defs.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ALT_CMO_OP(_op, _start, _size, _cachesize)             \
  asm volatile(                                                \
      "mv a0, %1\n\t"                                          \
      "j 2f\n\t"                                               \
      "3:\n\t"                                                 \
      "cbo." #_op " (a0)\n\t"                                  \
      "add a0, a0, %0\n\t"                                     \
      "2:\n\t"                                                 \
      "bltu a0, %2, 3b\n\t"                                    \
      : : "r"(_cachesize),                                     \
          "r"((unsigned int)(_start) & ~((_cachesize) - 1UL)), \
          "r"((unsigned int)(_start) + (_size))                \
      : "a0")

__attribute__((unused)) static void flush_cpu_icache(void)
{
  asm volatile(
    "fence.i\n"
  );
}

__attribute__((unused)) static void flush_cpu_dcache(void)
{
}

#ifdef __riscv_zicbom__

static inline void clean_cpu_dcache_range(void *start_addr, size_t size)
{
  ALT_CMO_OP(clean, (unsigned int)start_addr, size, 64);
}

#define HAS_CLEAN_CPU_DCACHE_RANGE 1

static inline void flush_cpu_dcache_range(void *start_addr, size_t size)
{
  ALT_CMO_OP(flush, (unsigned int)start_addr, size, 64);
}

#define HAS_FLUSH_CPU_DCACHE_RANGE 1

static inline void invd_cpu_dcache_range(void *start_addr, size_t size)
{
  ALT_CMO_OP(inval, (unsigned int)start_addr, size, 64);
}

#define HAS_INVD_CPU_DCACHE_RANGE 1

#endif /* __riscv_zicbom__ */

void flush_l2_cache(void);

void busy_wait(unsigned int ms);
void busy_wait_us(unsigned int us);

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

#ifdef __cplusplus
}
#endif

#endif /* __SYSTEM_H */
