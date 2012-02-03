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

#ifndef __HW_FLASH_H
#define __HW_FLASH_H

#define FLASH_OFFSET_STANDBY_BITSTREAM	(0x00000000) /* 640k */

#define FLASH_OFFSET_RESCUE_BITSTREAM	(0x000A0000) /* 1536k */
#define FLASH_OFFSET_RESCUE_BIOS	(0x00220000) /* 128k */
#define FLASH_OFFSET_MAC_ADDRESS	(0x002200E0) /* within rescue BIOS */
#define FLASH_OFFSET_RESCUE_SPLASH	(0x00240000) /* 640k */
#define FLASH_OFFSET_RESCUE_APP		(0x002E0000) /* 4096k */

#define FLASH_OFFSET_REGULAR_BITSTREAM	(0x006E0000) /* 1536k */
#define FLASH_OFFSET_REGULAR_BIOS	(0x00860000) /* 128k */
#define FLASH_OFFSET_REGULAR_SPLASH	(0x00880000) /* 640k */
#define FLASH_OFFSET_REGULAR_APP	(0x00920000) /* remaining space (23424k) */

#endif /* __HW_FLASH_H */
