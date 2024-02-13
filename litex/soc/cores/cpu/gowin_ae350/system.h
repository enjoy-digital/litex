#ifndef __SYSTEM_H
#define __SYSTEM_H

#ifdef __cplusplus
extern "C" {
#endif

__attribute__((unused)) static void flush_cpu_icache(void){}; /* FIXME */
__attribute__((unused)) static void flush_cpu_dcache(void){}; /* FIXME */
void flush_l2_cache(void);

void busy_wait(unsigned int ms);
void busy_wait_us(unsigned int us);

#ifdef __cplusplus
}
#endif

#endif /* __SYSTEM_H */
