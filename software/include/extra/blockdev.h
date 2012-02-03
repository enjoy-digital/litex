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

#ifndef __BLOCKDEV_H
#define __BLOCKDEV_H

enum {
	BLOCKDEV_MEMORY_CARD
};

int bd_init(int devnr);
int bd_readblock(unsigned int block, void *buffer);
void bd_done(void);

int bd_has_part_table(int devnr);

#endif /* __BLOCKDEV_H */
