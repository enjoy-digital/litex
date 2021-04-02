#include <generated/csr.h>
#include <lxtimer.h>
#include <time.h>

void time_init(void)
{
	int t;

	lxtimer_en_write(0);
	t = 2*CONFIG_CLOCK_FREQUENCY;
	lxtimer_reload_write(t);
	lxtimer_load_write(t);
	lxtimer_en_write(1);
}

int elapsed(int *last_event, int period)
{
	int t, dt;

	lxtimer_update_value_write(1);
	t = lxtimer_reload_read() - lxtimer_value_read();
	if(period < 0) {
		*last_event = t;
		return 1;
	}
	dt = t - *last_event;
	if(dt < 0)
		dt += lxtimer_reload_read();
	if((dt > period) || (dt < 0)) {
		*last_event = t;
		return 1;
	} else
		return 0;
}
