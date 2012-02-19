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

#define CSR_DFII_COMMAND		MMPTR(0xe0001004)

#define DFII_COMMAND_CS			(0x01)
#define DFII_COMMAND_WE			(0x02)
#define DFII_COMMAND_CAS		(0x04)
#define DFII_COMMAND_RAS		(0x08)
#define DFII_COMMAND_RDDATA		(0x10)
#define DFII_COMMAND_WRDATA		(0x20)

#define CSR_DFII_AH			MMPTR(0xe0000808)
#define CSR_DFII_AL			MMPTR(0xe000080C)
#define CSR_DFII_BA			MMPTR(0xe0000810)

#define CSR_DFII_RDDELAY		MMPTR(0xe0000814)
#define CSR_DFII_RDDURATION		MMPTR(0xe0000818)
#define CSR_DFII_WRDELAY		MMPTR(0xe000081C)
#define CSR_DFII_WRDURATION		MMPTR(0xe0000820)

#endif /* __HW_DFII_H */
