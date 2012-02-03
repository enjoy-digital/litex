/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009, 2010 Sebastien Bourdeauducq
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

#ifndef __HW_SYSCTL_H
#define __HW_SYSCTL_H

#include <hw/common.h>

#define CSR_GPIO_IN		MMPTR(0xe0001000)
#define CSR_GPIO_OUT		MMPTR(0xe0001004)
#define CSR_GPIO_INTEN		MMPTR(0xe0001008)

#define CSR_TIMER0_CONTROL	MMPTR(0xe0001010)
#define CSR_TIMER0_COMPARE	MMPTR(0xe0001014)
#define CSR_TIMER0_COUNTER	MMPTR(0xe0001018)

#define CSR_TIMER1_CONTROL	MMPTR(0xe0001020)
#define CSR_TIMER1_COMPARE	MMPTR(0xe0001024)
#define CSR_TIMER1_COUNTER	MMPTR(0xe0001028)

#define TIMER_ENABLE		(0x01)
#define TIMER_AUTORESTART	(0x02)

#define CSR_ICAP		MMPTR(0xe0001040)

#define ICAP_READY		(0x01)

#define ICAP_CE			(0x10000)
#define ICAP_WRITE		(0x20000)

#define CSR_DBG_SCRATCHPAD	MMPTR(0xe0001050)
#define CSR_DBG_CTRL		MMPTR(0xe0001054)

#define DBG_CTRL_GDB_ROM_LOCK	(0x01)
#define DBG_CTRL_BUS_ERR_EN	(0x02)

#define CSR_FREQUENCY		MMPTR(0xe0001074)
#define CSR_CAPABILITIES	MMPTR(0xe0001078)
#define CSR_SYSTEM_ID		MMPTR(0xe000107c)

#endif /* __HW_SYSCTL_H */
