// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"
#include "../sdcard.h"

/**
 * Command "sdclk"
 *
 * Configure SDcard clock frequency
 *
 */
#ifdef CSR_SDCORE_BASE
static void sdclk(int nb_params, char **params)
{
	unsigned int frequ;
	char *c;

	if (nb_params < 1) {
		printf("sdclk <frequ>");
		return;
	}

	frequ = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect frequency");
		return;
	}

	sdclk_set_clk(frequ);
}

struct command_struct cmd_sdclk =
{
	.func = sdclk,
	.name = "sdclk",
	.help = "SDCard set clk frequency (Mhz)",
};

define_command(sdclk, sdclk, "SDCard set clk frequency (Mhz)", SD_CMDS);
#endif

/**
 * Command "sdinit"
 *
 * Initialize SDcard
 *
 */
#ifdef CSR_SDCORE_BASE
define_command(sdinit, sdinit, "SDCard initialization", SD_CMDS);
#endif

/**
 * Command "sdtest"
 *
 * Perform SDcard access tests
 *
 */
#ifdef CSR_SDCORE_BASE
static void sdtest(int nb_params, char **params)
{
	unsigned int loops;
	char *c;

	if (nb_params < 1) {
		printf("sdtest <loops>");
		return;
	}

	loops = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect number of loops");
		return;
	}

	sdcard_test(loops);
}

define_command(sdtest, sdtest, "SDCard test", SD_CMDS);
#endif
