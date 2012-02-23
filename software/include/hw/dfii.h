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

#ifndef __HW_DFII_H
#define __HW_DFII_H

#include <hw/common.h>

#define CSR_DFII_CONTROL		MMPTR(0xe0000800)

#define DFII_CONTROL_SEL		(0x01)
#define DFII_CONTROL_CKE		(0x02)

#define CSR_DFII_COMMAND_P0		MMPTR(0xe0000804)
#define CSR_DFII_AH_P0			MMPTR(0xe0000808)
#define CSR_DFII_AL_P0			MMPTR(0xe000080C)
#define CSR_DFII_BA_P0			MMPTR(0xe0000810)
#define CSR_DFII_WD0_P0			MMPTR(0xe0000814)
#define CSR_DFII_WD1_P0			MMPTR(0xe0000818)
#define CSR_DFII_WD2_P0			MMPTR(0xe000081C)
#define CSR_DFII_WD3_P0			MMPTR(0xe0000820)
#define CSR_DFII_WD4_P0			MMPTR(0xe0000824)
#define CSR_DFII_WD5_P0			MMPTR(0xe0000828)
#define CSR_DFII_WD6_P0			MMPTR(0xe000082C)
#define CSR_DFII_WD7_P0			MMPTR(0xe0000830)
#define CSR_DFII_RD0_P0			MMPTR(0xe0000834)
#define CSR_DFII_RD1_P0			MMPTR(0xe0000838)
#define CSR_DFII_RD2_P0			MMPTR(0xe000083C)
#define CSR_DFII_RD3_P0			MMPTR(0xe0000840)
#define CSR_DFII_RD4_P0			MMPTR(0xe0000844)
#define CSR_DFII_RD5_P0			MMPTR(0xe0000848)
#define CSR_DFII_RD6_P0			MMPTR(0xe000084C)
#define CSR_DFII_RD7_P0			MMPTR(0xe0000850)

#define CSR_DFII_COMMAND_P1		MMPTR(0xe0000854)
#define CSR_DFII_AH_P1			MMPTR(0xe0000858)
#define CSR_DFII_AL_P1			MMPTR(0xe000085C)
#define CSR_DFII_BA_P1			MMPTR(0xe0000860)
#define CSR_DFII_WD0_P1			MMPTR(0xe0000864)
#define CSR_DFII_WD1_P1			MMPTR(0xe0000868)
#define CSR_DFII_WD2_P1			MMPTR(0xe000086C)
#define CSR_DFII_WD3_P1			MMPTR(0xe0000870)
#define CSR_DFII_WD4_P1			MMPTR(0xe0000874)
#define CSR_DFII_WD5_P1			MMPTR(0xe0000878)
#define CSR_DFII_WD6_P1			MMPTR(0xe000087C)
#define CSR_DFII_WD7_P1			MMPTR(0xe0000880)
#define CSR_DFII_RD0_P1			MMPTR(0xe0000884)
#define CSR_DFII_RD1_P1			MMPTR(0xe0000888)
#define CSR_DFII_RD2_P1			MMPTR(0xe000088C)
#define CSR_DFII_RD3_P1			MMPTR(0xe0000890)
#define CSR_DFII_RD4_P1			MMPTR(0xe0000894)
#define CSR_DFII_RD5_P1			MMPTR(0xe0000898)
#define CSR_DFII_RD6_P1			MMPTR(0xe000089C)
#define CSR_DFII_RD7_P1			MMPTR(0xe00008a0)

#define DFII_COMMAND_CS			(0x01)
#define DFII_COMMAND_WE			(0x02)
#define DFII_COMMAND_CAS		(0x04)
#define DFII_COMMAND_RAS		(0x08)
#define DFII_COMMAND_WRDATA		(0x10)
#define DFII_COMMAND_RDDATA		(0x20)

#endif /* __HW_DFII_H */
