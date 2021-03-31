/*
 * LiteX timer abstraction layer
 * Copyright (C) 2021 Raptor Engineering, LLC <sales@raptorengineering.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef _LXTIMER_H_
#define _LXTIMER_H_

#ifdef __PPC64__

#include <ppc/timer.h>

static inline void lxtimer_load_write(uint32_t v) {
	ppc_arch_timer_load_write(v);
}

static inline void lxtimer_reload_write(uint32_t v) {
	ppc_arch_timer_reload_write(v);
}

static inline uint32_t lxtimer_reload_read(void) {
	return ppc_arch_timer_reload_read();
}

static inline void lxtimer_en_write(uint8_t v) {
	ppc_arch_timer_en_write(v);
}

static inline void lxtimer_update_value_write(uint8_t v) {
	ppc_arch_timer_update_value_write(v);
}

static inline uint32_t lxtimer_value_read(void) {
	return ppc_arch_timer_value_read();
}
#else

#include <generated/csr.h>

static inline void lxtimer_load_write(uint32_t v) {
	timer0_load_write(v);
}

static inline void lxtimer_reload_write(uint32_t v) {
	timer0_reload_write(v);
}

static inline uint32_t lxtimer_reload_read(void) {
	return timer0_reload_read();
}

static inline void lxtimer_en_write(uint8_t v) {
	timer0_en_write(v);
}

static inline void lxtimer_update_value_write(uint8_t v) {
	timer0_update_value_write(v);
}

static inline uint32_t lxtimer_value_read(void) {
	return timer0_value_read();
}
#endif

#endif // _LXTIMER_H_
