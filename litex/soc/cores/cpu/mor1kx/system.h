#ifndef __SYSTEM_H
#define __SYSTEM_H

#ifdef __cplusplus
extern "C" {
#endif

void flush_cpu_icache(void);
void flush_cpu_dcache(void);
void flush_l2_cache(void);

void busy_wait(unsigned int ms);

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

#ifdef __cplusplus
}
#endif

#endif /* __SYSTEM_H */
