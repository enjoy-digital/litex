#ifndef __SYSTEM_H
#define __SYSTEM_H

#include <csr-defs.h>

#ifdef __cplusplus
extern "C" {
#endif

__attribute__((unused)) static void flush_cpu_icache(void)
{
  asm volatile(
    ".word(0x400F)\n"
    "nop\n"
    "nop\n"
    "nop\n"
    "nop\n"
    "nop\n"
  );
}

__attribute__((unused)) static void flush_cpu_dcache(void)
{
  unsigned long cache_info;
  asm volatile ("csrr %0, %1" : "=r"(cache_info) : "i"(CSR_DCACHE_INFO));
  unsigned long cache_way_size = cache_info & 0xFFFFF;
  unsigned long cache_line_size = (cache_info >> 20) & 0xFFF;
  for(register unsigned long idx = 0;idx < cache_way_size;idx += cache_line_size){
    asm volatile("mv x10, %0 \n .word(0b01110000000001010101000000001111)"::"r"(idx));
  }
}

void flush_l2_cache(void);

void busy_wait(unsigned int ms);

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
