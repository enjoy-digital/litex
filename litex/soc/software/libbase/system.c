#include <irq.h>
#include <uart.h>

#include <system.h>
#include <lxtimer.h>
#include <generated/mem.h>
#include <generated/csr.h>

void flush_l2_cache(void)
{
#ifdef CONFIG_L2_SIZE
	unsigned int i;
	for(i=0;i<2*CONFIG_L2_SIZE/4;i++) {
		((volatile unsigned int *) MAIN_RAM_BASE)[i];
	}
#endif
}

void busy_wait(unsigned int ms)
{
	lxtimer_en_write(0);
	lxtimer_reload_write(0);
	lxtimer_load_write(CONFIG_CLOCK_FREQUENCY/1000*ms);
	lxtimer_en_write(1);
	lxtimer_update_value_write(1);
	while(lxtimer_value_read()) lxtimer_update_value_write(1);
}

void busy_wait_us(unsigned int us)
{
	lxtimer_en_write(0);
	lxtimer_reload_write(0);
	lxtimer_load_write(CONFIG_CLOCK_FREQUENCY/1000000*us);
	lxtimer_en_write(1);
	lxtimer_update_value_write(1);
	while(lxtimer_value_read()) lxtimer_update_value_write(1);
}
