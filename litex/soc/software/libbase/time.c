#include <generated/csr.h>
#include <time.h>

void time_init(void)
{
	int t;

	timer0_en_write(0);
	t = 2*SYSTEM_CLOCK_FREQUENCY;
	timer0_reload_write(t);
	timer0_load_write(t);
	timer0_en_write(1);
}

int elapsed(int *last_event, int period)
{
	int t, dt;

	timer0_update_value_write(1);
	t = timer0_reload_read() - timer0_value_read();
	if(period < 0) {
		*last_event = t;
		return 1;
	}
	dt = t - *last_event;
	if(dt < 0)
		dt += timer0_reload_read();
	if((dt > period) || (dt < 0)) {
		*last_event = t;
		return 1;
	} else
		return 0;
}
