/*
 * Milkymist SoC (Software)
 * Copyright (C) 2012 Sebastien Bourdeauducq
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

#ifndef __HW_S6DDRPHY_H
#define __HW_S6DDRPHY_H

#include <hw/common.h>

#define CSR_DDRPHY_STATUS		MMPTR(0xe0000800)

#define DDRPHY_STATUS_RESETN		(0x1)
#define DDRPHY_STATUS_INIT_DONE		(0x2)
#define DDRPHY_STATUS_PHY_CAL_DONE	(0x4)

#define CSR_DDRPHY_REQUESTS		MMPTR(0xe0000804)

#define DDRPHY_REQUEST_READ		(0x1)
#define DDRPHY_REQUEST_WRITE		(0x2)

#define CSR_DDRPHY_REQADDR		MMPTR(0xe0000808)

#endif /* __HW_S6DDRPHY_H */
