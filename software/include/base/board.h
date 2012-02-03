/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009, 2010, 2011 Sebastien Bourdeauducq
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

#ifndef __BOARD_H
#define __BOARD_H

#define BOARD_NAME_LEN 32

struct board_desc {
	unsigned short int id;
	char name[BOARD_NAME_LEN];
	unsigned int ethernet_phyadr;
};

const struct board_desc *get_board_desc_id(unsigned short int id);
const struct board_desc *get_board_desc(void);
int get_pcb_revision(void);
void get_soc_version(unsigned int *major, unsigned int *minor, unsigned int *subminor, unsigned int *rc);
void get_soc_version_formatted(char *version);

#endif /* __BOARD_H */
