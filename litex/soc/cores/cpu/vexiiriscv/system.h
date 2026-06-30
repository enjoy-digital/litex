#ifndef __SYSTEM_H
#define __SYSTEM_H

#include <csr-defs.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* CBO opcodes with rs1=a0, encoded directly for older toolchains without
 * Zicbom assembler support. */
#define VEXII_CBO_INVAL 0x0005200f
#define VEXII_CBO_CLEAN 0x0015200f
#define VEXII_CBO_FLUSH 0x0025200f

#define VEXII_STRINGIFY_HELPER(_v) #_v
#define VEXII_STRINGIFY(_v) VEXII_STRINGIFY_HELPER(_v)

#define ALT_CMO_OP(_op, _start, _size, _cachesize)             \
  asm volatile(                                                \
      "fence rw, rw\n\t"                                       \
      "mv a0, %1\n\t"                                          \
      "j 2f\n\t"                                               \
      "3:\n\t"                                                 \
      ".word " VEXII_STRINGIFY(_op) "\n\t"                     \
      "add a0, a0, %0\n\t"                                     \
      "2:\n\t"                                                 \
      "bltu a0, %2, 3b\n\t"                                    \
      "fence rw, rw\n\t"                                       \
      : : "r"(_cachesize),                                     \
          "r"((unsigned long)(_start) & ~((_cachesize) - 1UL)), \
          "r"((unsigned long)(_start) + (_size))                \
      : "a0", "memory")

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
  ALT_CMO_OP(VEXII_CBO_CLEAN, (unsigned long)start_addr, size, 64);
}

#define HAS_CLEAN_CPU_DCACHE_RANGE 1

static inline void flush_cpu_dcache_range(void *start_addr, size_t size)
{
  ALT_CMO_OP(VEXII_CBO_FLUSH, (unsigned long)start_addr, size, 64);
}

#define HAS_FLUSH_CPU_DCACHE_RANGE 1

static inline void invd_cpu_dcache_range(void *start_addr, size_t size)
{
  ALT_CMO_OP(VEXII_CBO_INVAL, (unsigned long)start_addr, size, 64);
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
