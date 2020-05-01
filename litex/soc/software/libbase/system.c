#include <irq.h>
#include <uart.h>
#ifdef __or1k__
#include <spr-defs.h>
#endif

#if defined (__vexriscv__)
#include <csr-defs.h>
#endif

#include <system.h>
#include <generated/mem.h>
#include <generated/csr.h>

#ifdef CONFIG_L2_SIZE
void flush_l2_cache(void)
{
	unsigned int i;
	for(i=0;i<2*CONFIG_L2_SIZE/4;i++) {
		((volatile unsigned int *) MAIN_RAM_BASE)[i];
	}
}
#endif

void busy_wait(unsigned int ms)
{
	timer0_en_write(0);
	timer0_reload_write(0);
	timer0_load_write(CONFIG_CLOCK_FREQUENCY/1000*ms);
	timer0_en_write(1);
	timer0_update_value_write(1);
	while(timer0_value_read()) timer0_update_value_write(1);
}
