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

#include <stdio.h>

#include <hw/s6ddrphy.h>

#include "ddrinit.h"

static void init_sequence(void)
{
	printf("Sending initialization sequence...\n");
	// TODO
}

static void calibrate_phy(void)
{
	int requests;
	int addr;
	
	printf("Calibrating PHY...\n");
	while(!(CSR_DDRPHY_STATUS & DDRPHY_STATUS_PHY_CAL_DONE)) {
		requests = CSR_DDRPHY_REQUESTS;
		addr = CSR_DDRPHY_REQADDR;
		
		if(requests & DDRPHY_REQUEST_READ) {
			printf("R %d\n", addr);
			// TODO
		}
		if(requests & DDRPHY_REQUEST_WRITE) {
			printf("W %d\n", addr);
			// TODO
		}
		
		CSR_DDRPHY_REQUESTS = requests;
	}
}

int ddrinit(void)
{
	printf("Initializing DDR SDRAM...\n");
	
	CSR_DDRPHY_STATUS = DDRPHY_STATUS_RESETN;
	init_sequence();
	CSR_DDRPHY_STATUS = DDRPHY_STATUS_RESETN|DDRPHY_STATUS_INIT_DONE;
	calibrate_phy();
	
	return 1;
}
