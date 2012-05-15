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
#include <stdlib.h>

#include <hw/dfii.h>
#include <hw/mem.h>

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
	CSR_DFII_AH_P0 = (a & 0x1fe0) >> 5;
	CSR_DFII_AL_P0 = a & 0x001f;
	CSR_DFII_AH_P1 = (a & 0x1fe0) >> 5;
	CSR_DFII_AL_P1 = a & 0x001f;
}

static void init_sequence(void)
{
	int i;
	
	/* Bring CKE high */
	setaddr(0x0000);
	CSR_DFII_BA_P0 = 0;
	CSR_DFII_CONTROL = DFII_CONTROL_CKE;
	
	/* Precharge All */
	setaddr(0x0400);
	CSR_DFII_COMMAND_P0 = DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
	
	/* Load Extended Mode Register */
	CSR_DFII_BA_P0 = 1;
	setaddr(0x0000);
	CSR_DFII_COMMAND_P0 = DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
	CSR_DFII_BA_P0 = 0;
	
	/* Load Mode Register */
	setaddr(0x0132); /* Reset DLL, CL=3, BL=4 */
	CSR_DFII_COMMAND_P0 = DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
	cdelay(200);
	
	/* Precharge All */
	setaddr(0x0400);
	CSR_DFII_COMMAND_P0 = DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
	
	/* 2x Auto Refresh */
	for(i=0;i<2;i++) {
		setaddr(0);
		CSR_DFII_COMMAND_P0 = DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_CS;
		cdelay(4);
	}
	
	/* Load Mode Register */
	setaddr(0x0032); /* CL=3, BL=4 */
	CSR_DFII_COMMAND_P0 = DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
	cdelay(200);
}

void ddrsw(void)
{
	CSR_DFII_CONTROL = DFII_CONTROL_CKE;
	printf("DDR now under software control\n");
}

void ddrhw(void)
{
	CSR_DFII_CONTROL = DFII_CONTROL_SEL|DFII_CONTROL_CKE;
	printf("DDR now under hardware control\n");
}

void ddrrow(char *_row)
{
	char *c;
	unsigned int row;
	
	if(*_row == 0) {
		setaddr(0x0000);
		CSR_DFII_BA_P0 = 0;
		CSR_DFII_COMMAND_P0 = DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS;
		cdelay(15);
		printf("Precharged\n");
	} else {
		row = strtoul(_row, &c, 0);
		if(*c != 0) {
			printf("incorrect row\n");
			return;
		}
		setaddr(row);
		CSR_DFII_BA_P0 = 0;
		CSR_DFII_COMMAND_P0 = DFII_COMMAND_RAS|DFII_COMMAND_CS;
		cdelay(15);
		printf("Activated row %d\n", row);
	}
}

void ddrrd(char *startaddr)
{
	char *c;
	unsigned int addr;
	int i;

	if(*startaddr == 0) {
		printf("ddrrd <address>\n");
		return;
	}
	addr = strtoul(startaddr, &c, 0);
	if(*c != 0) {
		printf("incorrect address\n");
		return;
	}
	
	setaddr(addr);
	CSR_DFII_BA_P0 = 0;
	CSR_DFII_COMMAND_P0 = DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA;
	cdelay(15);
	
	for(i=0;i<8;i++)
		printf("%02x", MMPTR(0xe0000834+4*i));
	for(i=0;i<8;i++)
		printf("%02x", MMPTR(0xe0000884+4*i));
	printf("\n");
}

void ddrwr(char *startaddr)
{
	char *c;
	unsigned int addr;
	int i;

	if(*startaddr == 0) {
		printf("ddrrd <address>\n");
		return;
	}
	addr = strtoul(startaddr, &c, 0);
	if(*c != 0) {
		printf("incorrect address\n");
		return;
	}
	
	for(i=0;i<8;i++) {
		MMPTR(0xe0000814+4*i) = i;
		MMPTR(0xe0000864+4*i) = 0xf0 + i;
	}
	
	setaddr(addr);
	CSR_DFII_BA_P1 = 0;
	CSR_DFII_COMMAND_P1 = DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS|DFII_COMMAND_WRDATA;
}

#define TEST_SIZE (4*1024*1024)

int memtest_silent(void)
{
	volatile unsigned int *array = (unsigned int *)SDRAM_BASE;
	int i;
	unsigned int prv;
	
	prv = 0;
	for(i=0;i<TEST_SIZE/4;i++) {
		prv = 1664525*prv + 1013904223;
		array[i] = prv;
	}
	
	prv = 0;
	for(i=0;i<TEST_SIZE/4;i++) {
		prv = 1664525*prv + 1013904223;
		if(array[i] != prv)
			return 0;
	}
	return 1;
}

void memtest(void)
{
	if(memtest_silent())
		printf("OK\n");
	else
		printf("Failed\n");
}

int ddrinit(void)
{
	printf("Initializing DDRAM...\n");
	
	init_sequence();
	CSR_DFII_CONTROL = DFII_CONTROL_SEL|DFII_CONTROL_CKE;
	if(!memtest_silent())
		return 0;
	
	return 1;
}
