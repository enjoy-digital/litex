// SPDX-License-Identifier: BSD-2-Clause

#include <generated/csr.h>
#include <generated/soc.h>
#include "timeout.h"

static uint64_t timeout_cycles(void)
{
#ifdef CSR_TIMER0_UPTIME_CYCLES_ADDR
	timer0_uptime_latch_write(1);
	return timer0_uptime_cycles_read();
#else
	timer0_update_value_write(1);
	return timer0_value_read();
#endif
}

void timeout_start(struct timeout *timeout, unsigned int us)
{
#ifndef CSR_TIMER0_UPTIME_CYCLES_ADDR
	/* Keep the same time base for nested deadlines. busy_wait/serialboot may
	   have used timer0 since the previous operation, so check its mode. */
	if (!timer0_en_read() || timer0_reload_read() != UINT32_MAX) {
		timer0_en_write(0);
		timer0_reload_write(UINT32_MAX);
		timer0_load_write(UINT32_MAX);
		timer0_en_write(1);
	}
#endif
	timeout->remaining = ((uint64_t)CONFIG_CLOCK_FREQUENCY * us + 999999) / 1000000;
	timeout->last = timeout_cycles();
}

int timeout_expired(struct timeout *timeout)
{
	uint64_t now = timeout_cycles();
#ifdef CSR_TIMER0_UPTIME_CYCLES_ADDR
	uint64_t elapsed = now - timeout->last;
#else
	uint32_t elapsed = (uint32_t)timeout->last - (uint32_t)now;
#endif
	timeout->last = now;
	if (elapsed >= timeout->remaining) {
		timeout->remaining = 0;
		return 1;
	}
	timeout->remaining -= elapsed;
	return 0;
}
