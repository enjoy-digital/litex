#include <hw/csr.h>

#include "timer.h"

unsigned int get_system_frequency(void)
{
	return identifier_frequency_read();
}

void timer_enable(int en)
{
	timer0_en_write(en);
}

unsigned int timer_get(void)
{
	return timer0_value_read();
}

void timer_set_counter(unsigned int value)
{
	timer0_value_write(value);
}

void timer_set_reload(unsigned int value)
{
	timer0_reload_write(value);
}

void busy_wait(unsigned int ds)
{
	timer_enable(0);
	timer_set_reload(0);
	timer_set_counter(get_system_frequency()/10*ds);
	timer_enable(1);
	while(timer_get());
}
