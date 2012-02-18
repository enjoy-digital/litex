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
#include <hw/dfii.h>

#include "ddrinit.h"

static void cdelay(int i)
{
	while(i > 0) {
		__asm__ volatile("nop");
		i--;
	}
}

static void setaddr(int a)
{
	CSR_DFII_AH = (a & 0x1fe0) >> 5;
	CSR_DFII_AL = a & 0x001f;
}

static void init_sequence(void)
{
	int i;
	
	printf("Sending initialization sequence...\n");
	
	/* Bring CKE high */
	setaddr(0x0000);
	CSR_DFII_BA = 0;
	CSR_DFII_CONTROL = DFII_CONTROL_CKE;
	
	/* Precharge All */
	setaddr(0x0400);
	CSR_DFII_COMMAND = DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
	
	/* Load Extended Mode Register */
	CSR_DFII_BA = 1;
	setaddr(0x0000);
	CSR_DFII_COMMAND = DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
	CSR_DFII_BA = 0;
	
	/* Load Mode Register */
	setaddr(0x0132); /* Reset DLL, CL=3, BL=4 */
	CSR_DFII_COMMAND = DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
	cdelay(200);
	
	/* Precharge All */
	setaddr(0x0400);
	CSR_DFII_COMMAND = DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
	
	/* 2x Auto Refresh */
	for(i=0;i<2;i++) {
		setaddr(0);
		CSR_DFII_COMMAND = DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_CS;
		cdelay(4);
	}
	
	/* Load Mode Register */
	setaddr(0x0032); /* CL=3, BL=4 */
	CSR_DFII_COMMAND = DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
	cdelay(200);
}

static void calibrate_phy(void)
{
	int requests;
	int addr;
	
	printf("Calibrating PHY...\n");
	
	CSR_DFII_WRDELAY = 4;
	CSR_DFII_WRDURATION = 1;
	CSR_DFII_RDDELAY = 7;
	CSR_DFII_RDDURATION = 1;
	
	/* Use bank 0, activate row 0 */
	CSR_DFII_BA = 0;
	setaddr(0x0000);
	CSR_DFII_COMMAND = DFII_COMMAND_RAS|DFII_COMMAND_CS;
	
	while(!(CSR_DDRPHY_STATUS & DDRPHY_STATUS_PHY_CAL_DONE)) {
		cdelay(20);
		requests = CSR_DDRPHY_REQUESTS;
		addr = CSR_DDRPHY_REQADDR;
		
		setaddr(addr << 2);
		if(requests & DDRPHY_REQUEST_READ) {
			printf("R %d\n", addr);
			CSR_DFII_COMMAND = DFII_COMMAND_RDDATA|DFII_COMMAND_CAS|DFII_COMMAND_CS;
		}
		if(requests & DDRPHY_REQUEST_WRITE) {
			printf("W %d\n", addr);
			CSR_DFII_COMMAND = DFII_COMMAND_WRDATA|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
		}
		
		CSR_DDRPHY_REQUESTS = requests;
	}
	
	/* Precharge All */
	setaddr(0x0400);
	CSR_DFII_COMMAND = DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
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
