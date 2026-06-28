#ifndef __SYSTEM_H
#define __SYSTEM_H
/* IRQ-driven UART stalls in the BIOS: PPC needs IRQ vectors set up first (done by Linux),
   so use polling UART until then (see litex#2306 / PowerCommons). */
#define UART_POLLING

#ifdef __cplusplus
extern "C" {
#endif

static inline void flush_cpu_icache(void)
{
	__asm__ volatile ("icbi 0,0; isync" : : : "memory");
}
static inline void flush_cpu_dcache(void){}; /* FIXME: do something useful here! */
void flush_l2_cache(void);

void busy_wait(unsigned int ms);
void busy_wait_us(unsigned int us);

#ifdef __cplusplus
}
#endif

#endif /* __SYSTEM_H */
