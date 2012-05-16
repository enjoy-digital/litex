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
#include <csrbase.h>

#define UART_CSR(x)		MMPTR(UART_BASE+(x))

#define CSR_UART_RXTX		UART_CSR(0x00)
#define CSR_UART_DIVISORH	UART_CSR(0x04)
#define CSR_UART_DIVISORL	UART_CSR(0x08)

#define CSR_UART_EV_STAT	UART_CSR(0x0c)
#define CSR_UART_EV_PENDING	UART_CSR(0x10)
#define CSR_UART_EV_ENABLE	UART_CSR(0x14)

#define UART_EV_TX		0x1
#define UART_EV_RX		0x2

#endif /* __HW_UART_H */
