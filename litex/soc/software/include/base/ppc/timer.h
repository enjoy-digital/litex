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
#include <ppc/ppc64_asm.h>

void ppc_arch_timer_load_write(uint32_t v);
void ppc_arch_timer_reload_write(uint32_t v);
uint32_t ppc_arch_timer_reload_read(void);
void ppc_arch_timer_en_write(uint8_t v);
void ppc_arch_timer_update_value_write(uint8_t v);
uint32_t ppc_arch_timer_value_read(void);

void ppc_arch_timer_isr_dec(void);

#endif // _PPCTIME_H_
