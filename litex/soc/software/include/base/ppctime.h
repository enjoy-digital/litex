/*
 * OpenPOWER Timer Interface
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

#ifndef _PPCTIME_H_
#define _PPCTIME_H_

#include <stdint.h>
#include <ppc64_asm.h>

extern uint32_t ppc64_dec_timer_enabled;
extern uint32_t ppc64_dec_timer_single_shot_fired;
extern uint32_t ppc64_dec_timer_reload_enabled;
extern uint32_t ppc64_dec_timer_oneshot_value;
extern uint32_t ppc64_dec_timer_reload_value;
extern uint32_t ppc64_dec_timer_latched_value;

static inline void ppc_arch_timer_load_write(uint32_t v) {
	ppc64_dec_timer_reload_enabled = 0;
	ppc64_dec_timer_oneshot_value = v;
	if (v) {
		ppc64_dec_timer_single_shot_fired = 0;
	}
}

static inline void ppc_arch_timer_reload_write(uint32_t v) {
	if (v) {
		ppc64_dec_timer_reload_enabled = 1;
		ppc64_dec_timer_reload_value = v;
	}
	else {
		ppc64_dec_timer_reload_enabled = 0;
	}
}

static inline uint32_t ppc_arch_timer_reload_read(void) {
	return ppc64_dec_timer_reload_value;
}

static inline void ppc_arch_timer_en_write(uint8_t v) {
	if (v) {
		ppc64_dec_timer_enabled = 1;
		if (ppc64_dec_timer_reload_enabled) {
			mtdec(ppc64_dec_timer_reload_value);
		}
		else {
			mtdec(ppc64_dec_timer_oneshot_value);
		}
	}
	else {
		ppc64_dec_timer_enabled = 0;
	}
}

static inline void ppc_arch_timer_update_value_write(uint8_t v) {
	ppc64_dec_timer_latched_value = mfdec();
}

static inline uint32_t ppc_arch_timer_value_read(void) {
	int64_t value = mfdec();
	if ((value < 0) || (ppc64_dec_timer_single_shot_fired)) {
		// Overflow -- the timer expired and is now counting upward from negative values
		value = 0;
	}

	if (ppc64_dec_timer_enabled) {
		if (value == 0) {
			if (ppc64_dec_timer_reload_enabled) {
				// Reload timer
				mtdec(ppc64_dec_timer_reload_value);
			}
			else {
				// Lock timer value at zero
				mtdec(0);
				ppc64_dec_timer_single_shot_fired = 1;
			}
		}
	}

	return value;
}

#endif // _PPCTIME_H_
