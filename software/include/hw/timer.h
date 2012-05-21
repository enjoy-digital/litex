/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009, 2010, 2012 Sebastien Bourdeauducq
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

#ifndef __HW_TIMER_H
#define __HW_TIMER_H

#include <hw/common.h>
#include <csrbase.h>

#define TIMER0_CSR(x)		MMPTR(TIMER0_BASE+(x))

#define CSR_TIMER0_EN		TIMER0_CSR(0x00)

#define CSR_TIMER0_COUNT3	TIMER0_CSR(0x04)
#define CSR_TIMER0_COUNT2	TIMER0_CSR(0x08)
#define CSR_TIMER0_COUNT1	TIMER0_CSR(0x0C)
#define CSR_TIMER0_COUNT0	TIMER0_CSR(0x10)

#define CSR_TIMER0_RELOAD3	TIMER0_CSR(0x14)
#define CSR_TIMER0_RELOAD2	TIMER0_CSR(0x18)
#define CSR_TIMER0_RELOAD1	TIMER0_CSR(0x1C)
#define CSR_TIMER0_RELOAD0	TIMER0_CSR(0x20)

#define CSR_TIMER0_EV_STAT	TIMER0_CSR(0x24)
#define CSR_TIMER0_EV_PENDING	TIMER0_CSR(0x28)
#define CSR_TIMER0_EV_ENABLE	TIMER0_CSR(0x2C)

#define TIMER0_EV		0x1

#endif /* __HW_TIMER_H */
