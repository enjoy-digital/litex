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

#ifndef __HW_CAPABILITIES
#define __HW_CAPABILITIES

#define CAP_MEMORYCARD		(0x00000001)
#define CAP_AC97		(0x00000002)
#define CAP_PFPU		(0x00000004)
#define CAP_TMU			(0x00000008)
#define CAP_ETHERNET		(0x00000010)
#define CAP_FMLMETER		(0x00000020)
#define CAP_VIDEOIN		(0x00000040)
#define CAP_MIDI		(0x00000080)
#define CAP_DMX			(0x00000100)
#define CAP_IR			(0x00000200)
#define CAP_USB			(0x00000400)
#define CAP_MEMTEST		(0x00000800)

#endif /* __HW_CAPABILITIES */
