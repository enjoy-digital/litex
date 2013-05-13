#include <hw/csr.h>

#include "time.h"

void time_init(void)
{
	timer0_reload_write(2*identifier_frequency_read());
	timer0_en_write(1);
}

int elapsed(int *last_event, int period)
{
	int t, dt;

	t = timer0_reload_read() - timer0_value_read(); // TODO: atomic read
	dt = t - *last_event;
	if(dt < 0)
		dt += timer0_reload_read();
	if((dt > period) || (dt < 0)) {
		*last_event = t;
		return 1;
	} else
		return 0;
}
