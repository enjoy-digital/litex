// SPDX-License-Identifier: BSD-2-Clause

#ifndef __LIBBASE_TIMEOUT_H
#define __LIBBASE_TIMEOUT_H

#include <stdint.h>

struct timeout {
	uint64_t remaining;
	uint64_t last;
};

/* Nested deadlines share the uptime counter, or timer0 in free-running mode.
 * Without uptime, do not reprogram timer0 (e.g. busy_wait) while a deadline is
 * active, and poll at least once per 2^32 system-clock cycles. */
void timeout_start(struct timeout *timeout, unsigned int us);
int timeout_expired(struct timeout *timeout);

#endif
