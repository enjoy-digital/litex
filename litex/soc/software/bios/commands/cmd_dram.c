// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"
#include "../sdram.h"

/**
 * Command "sdrrow"
 *
 * Precharge/Activate row
 *
 */
#ifdef CSR_SDRAM_BASE
static void sdrrow_handler(int nb_params, char **params)
{
	char *c;
	unsigned int row;

	if (nb_params < 1) {
		sdrrow(0);
		printf("Precharged");
	}
	
	row = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect row");
		return;
	}

	sdrrow(row);
	printf("Activated row %d", row);
}
define_command(sdrrow, sdrrow_handler, "Precharge/Activate row", DRAM_CMDS);
#endif

/**
 * Command "sdrsw"
 *
 * Gives SDRAM control to SW
 *
 */
#ifdef CSR_SDRAM_BASE
define_command(sdrsw, sdrsw, "Gives SDRAM control to SW", DRAM_CMDS);
#endif

/**
 * Command "sdrhw"
 *
 * Gives SDRAM control to HW
 *
 */
#ifdef CSR_SDRAM_BASE
define_command(sdrhw, sdrhw, "Gives SDRAM control to HW", DRAM_CMDS);
#endif

/**
 * Command "sdrrdbuf"
 *
 * Dump SDRAM read buffer
 *
 */
#ifdef CSR_SDRAM_BASE
static void sdrrdbuf_handler(int nb_params, char **params)
{
	sdrrdbuf(-1);
}

define_command(sdrrdbuf, sdrrdbuf_handler, "Dump SDRAM read buffer", DRAM_CMDS);
#endif

/**
 * Command "sdrrd"
 *
 * Read SDRAM data
 *
 */
#ifdef CSR_SDRAM_BASE
static void sdrrd_handler(int nb_params, char **params)
{
	unsigned int addr;
	int dq;
	char *c;

	if (nb_params < 1) {
		printf("sdrrd <address>");
		return;
	}

	addr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}

	if (nb_params < 2)
		dq = -1;
	else {
		dq = strtoul(params[1], &c, 0);
		if (*c != 0) {
			printf("Incorrect DQ");
			return;
		}
	}

	sdrrd(addr, dq);
}

define_command(sdrrd, sdrrd_handler, "Read SDRAM data", DRAM_CMDS);
#endif

/**
 * Command "sdrrderr"
 *
 * Print SDRAM read errors
 *
 */
#ifdef CSR_SDRAM_BASE
static void sdrrderr_handler(int nb_params, char **params)
{
	int count;
	char *c;

	if (nb_params < 1) {
		printf("sdrrderr <count>");
		return;
	}

	count = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect count");
		return;
	}

	sdrrderr(count);
}

define_command(sdrrderr, sdrrderr_handler, "Print SDRAM read errors", DRAM_CMDS);
#endif

/**
 * Command "sdrwr"
 *
 * Write SDRAM test data
 *
 */
#ifdef CSR_SDRAM_BASE
static void sdrwr_handler(int nb_params, char **params)
{
	unsigned int addr;
	char *c;

	if (nb_params < 1) {
		printf("sdrwr <address>");
		return;
	}

	addr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}

	sdrwr(addr);
}

define_command(sdrwr, sdrwr_handler, "Write SDRAM test data", DRAM_CMDS);
#endif

/**
 * Command "sdrinit"
 *
 * Start SDRAM initialisation
 *
 */
#if defined(CSR_SDRAM_BASE) && defined(CSR_DDRPHY_BASE)
define_command(sdrinit, sdrinit, "Start SDRAM initialisation", DRAM_CMDS);
#endif

/**
 * Command "sdrwlon"
 *
 * Write leveling ON
 *
 */
#if defined(CSR_DDRPHY_BASE) && defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) && defined(CSR_SDRAM_BASE)
define_command(sdrwlon, sdrwlon, "Enable write leveling", DRAM_CMDS);
#endif

/**
 * Command "sdrwloff"
 *
 * Write leveling OFF
 *
 */
#if defined(CSR_DDRPHY_BASE) && defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) && defined(CSR_SDRAM_BASE)
define_command(sdrwloff, sdrwloff, "Disable write leveling", DRAM_CMDS);
#endif

/**
 * Command "sdrlevel"
 *
 * Perform read/write leveling
 *
 */
#if defined(CSR_DDRPHY_BASE) && defined(CSR_SDRAM_BASE)
define_command(sdrlevel, sdrlevel, "Perform read/write leveling", DRAM_CMDS);
#endif

/**
 * Command "memtest"
 *
 * Run a memory test
 *
 */
#ifdef CSR_SDRAM_BASE
define_command(memtest, memtest, "Run a memory test", DRAM_CMDS);
#endif
