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

#ifndef __HW_MINIMAC_H
#define __HW_MINIMAC_H

#include <hw/common.h>
#include <csrbase.h>

#define MINIMAC_CSR(x)		MMPTR(MINIMAC_BASE+(x))

#define CSR_MINIMAC_PHYRST	MINIMAC_CSR(0x00)

#define CSR_MINIMAC_RXCOUNT0H	MINIMAC_CSR(0x04)
#define CSR_MINIMAC_RXCOUNT0L	MINIMAC_CSR(0x08)
#define CSR_MINIMAC_RXCOUNT1H	MINIMAC_CSR(0x0C)
#define CSR_MINIMAC_RXCOUNT1L	MINIMAC_CSR(0x10)

#define CSR_MINIMAC_TXCOUNTH	MINIMAC_CSR(0x14)
#define CSR_MINIMAC_TXCOUNTL	MINIMAC_CSR(0x18)
#define CSR_MINIMAC_TXSTART	MINIMAC_CSR(0x1C)

#define CSR_MINIMAC_EV_STAT	MINIMAC_CSR(0x20)
#define CSR_MINIMAC_EV_PENDING	MINIMAC_CSR(0x24)
#define CSR_MINIMAC_EV_ENABLE	MINIMAC_CSR(0x28)

#define MINIMAC_EV_RX0		0x1
#define MINIMAC_EV_RX1		0x2
#define MINIMAC_EV_TX		0x4

#define MINIMAC_RX0_BASE	0xb0000000
#define MINIMAC_RX1_BASE	0xb0000800
#define MINIMAC_TX_BASE		0xb0001000

#endif /* __HW_MINIMAC_H */
