/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009, 2011 Sebastien Bourdeauducq
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

#include <hw/sysctl.h>
#include <hw/gpio.h>
#include <stdio.h>
#include <stdlib.h>
#include <board.h>

static const struct board_desc boards[1] = {
	{
		.id = 0x4D31, /* M1 */
		.name = "Milkymist One",
		.ethernet_phyadr = 1
	},
};

const struct board_desc *get_board_desc_id(unsigned short int id)
{
	unsigned int i;

	for(i=0;i<sizeof(boards)/sizeof(boards[0]);i++)
		if(boards[i].id == id)
			return &boards[i];
	return NULL;
}

const struct board_desc *get_board_desc(void)
{
	return get_board_desc_id(CSR_SYSTEM_ID & 0xffff);
}

int get_pcb_revision(void)
{
	int r;
	unsigned int io;

	io = CSR_GPIO_IN;
	r = 0;
	if(io & GPIO_PCBREV0)
		r |= 0x1;
	if(io & GPIO_PCBREV1)
		r |= 0x2;
	if(io & GPIO_PCBREV2)
		r |= 0x4;
	if(io & GPIO_PCBREV3)
		r |= 0x8;
	return r;
}

void get_soc_version(unsigned int *major, unsigned int *minor, unsigned int *subminor, unsigned int *rc)
{
	unsigned int id;

	id = CSR_SYSTEM_ID;
	*major = (id & 0xf0000000) >> 28;
	*minor = (id & 0x0f000000) >> 24;
	*subminor = (id & 0x00f00000) >> 20;
	*rc = (id & 0x000f0000) >> 16;
}

void get_soc_version_formatted(char *version)
{
	unsigned int major, minor, subminor, rc;

	get_soc_version(&major, &minor, &subminor, &rc);

	version += sprintf(version, "%u.%u", major, minor);
	if(subminor != 0)
		version += sprintf(version, ".%u", subminor);
	if(rc != 0)
		sprintf(version, "RC%u", rc);
}
