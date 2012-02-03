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

#ifndef __HW_GPIO_H
#define __HW_GPIO_H

/* Inputs */
#define GPIO_BTN1	(0x00000001)
#define GPIO_BTN2	(0x00000002)
#define GPIO_BTN3	(0x00000004)

#define GPIO_PCBREV0	(0x00000008)
#define GPIO_PCBREV1	(0x00000010)
#define GPIO_PCBREV2	(0x00000020)
#define GPIO_PCBREV3	(0x00000040)

/* Outputs */
#define GPIO_LED1	(0x00000001)
#define GPIO_LED2	(0x00000002)

#endif /* __HW_GPIO_H */
