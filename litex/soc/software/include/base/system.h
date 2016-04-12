#ifndef __SYSTEM_H
#define __SYSTEM_H

#ifdef __cplusplus
extern "C" {
#endif

void flush_cpu_icache(void);
void flush_cpu_dcache(void);
void flush_l2_cache(void);

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

#ifdef __cplusplus
}
#endif

#endif /* __SYSTEM_H */
