// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"
#include "../sdram.h"

/**
 * Command "sdram_cdly"
 *
 * Set SDRAM clk/cmd delay
 *
 */
#ifdef USDDRPHY_DEBUG
static void sdram_cdly(int nb_params, char **params)
{
	unsigned int delay;
	char *c;

	if (nb_params < 1) {
		printf("sdram_cdly <delay>");
		return;
	}

	delay = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect delay");
		return;
	}

	ddrphy_cdly(delay);
}

define_command(sdram_cdly, sdram_cdly, "Set SDRAM clk/cmd delay", DDR_CMDS);
#endif

/**
 * Command "sdram_cdly"
 *
 * Run SDRAM calibration
 *
 */
#ifdef USDDRPHY_DEBUG
define_command(sdram_cal, sdram_cal, "Run SDRAM calibration", DDR_CMDS);
#endif

/**
 * Command "sdram_mpr"
 *
 * Read SDRAM MPR
 *
 */
#ifdef USDDRPHY_DEBUG
define_command(sdram_mpr, sdram_mpr, "Read SDRAM MPR", DDR_CMDS);
#endif


/**
 * Command "sdram_mrwr"
 *
 * Write SDRAM mode registers
 *
 */
#ifdef USDDRPHY_DEBUG
static void sdram_mrwr(int nb_params, char **params)
{
	unsigned int reg;
	unsigned int value;
	char *c;

	if (nb_params < 2) {
		printf("sdram_mrwr <reg> <value>");
		return;
	}

	reg = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect register value");
		return;
	}

	value = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	sdrsw();
	printf("Writing 0x%04x to SDRAM mode register %d\n", value, reg);
	sdrmrwr(reg, value);
	sdrhw();
}

define_command(sdram_mrwr, sdram_mrwr, "Write SDRAM mode registers", DDR_CMDS);
#endif

/**
 * Command "sdram_cdly_scan"
 *
 * Enable/disable cdly scan
 *
 */
#ifdef USDDRPHY_DEBUG
static void sdram_cdly_scan(int nb_params, char **params)
{
	unsigned int value;
	char *c;

	if (nb_params < 1) {
		printf("sdram_cdly_scan <value>");
		return;
	}

	value = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	sdr_cdly_scan(value);
}

define_command(sdram_cdly_scan, sdram_cdly_scan, "Enable/disable cdly scan", DDR_CMDS);
#endif
