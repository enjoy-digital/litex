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

#ifndef __HW_UART_H
#define __HW_UART_H

#include <hw/common.h>

#define CSR_UART_RXTX 		MMPTR(0xe0000000)
#define CSR_UART_DIVISORH	MMPTR(0xe0000004)
#define CSR_UART_DIVISORL	MMPTR(0xe0000008)

#define CSR_UART_EV_STAT	MMPTR(0xe000000c)
#define CSR_UART_EV_PENDING	MMPTR(0xe0000010)
#define CSR_UART_EV_ENABLE	MMPTR(0xe0000014)

#define UART_EV_TX		(0x1)
#define UART_EV_RX		(0x2)

#endif /* __HW_UART_H */
