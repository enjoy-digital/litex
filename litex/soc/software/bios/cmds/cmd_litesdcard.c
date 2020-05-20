// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include <liblitesdcard/sdcard.h>

#include "../command.h"
#include "../helpers.h"

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

define_command(sdclk, sdclk, "SDCard set clk frequency (Mhz)", LITESDCARD_CMDS);
#endif

/**
 * Command "sdinit"
 *
 * Initialize SDcard
 *
 */
#ifdef CSR_SDCORE_BASE
define_command(sdinit, sdcard_init, "SDCard initialization", LITESDCARD_CMDS);
#endif

/**
 * Command "sdtest"
 *
 * Perform SDcard read/write tests
 *
 */
#ifdef CSR_SDCORE_BASE
static void sdtest(int nb_params, char **params)
{
	unsigned int blocks;
	char *c;

	if (nb_params < 1) {
		printf("sdtest <number of blocks>");
		return;
	}

	blocks = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect number of blocks to write");
		return;
	}

	sdcard_test(blocks);
}

define_command(sdtest, sdtest, "SDCard test", LITESDCARD_CMDS);
#endif

/**
 * Command "sdtestread"
 *
 * Perform SDcard read test
 *
 */
#ifdef CSR_SDCORE_BASE
static void sdtestread(int nb_params, char **params)
{
	unsigned int block;
	char *c;

	if (nb_params < 1) {
		printf("sdtestread <block number>");
		return;
	}

	block = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect number of block to read");
		return;
	}

	sdcard_test_read(block);
}

define_command(sdtestread, sdtestread, "SDCard test read", LITESDCARD_CMDS);
#endif

/**
 * Command "sdtestwrite"
 *
 * Perform SDcard write test
 *
 */
#ifdef CSR_SDCORE_BASE
static void sdtestwrite(int nb_params, char **params)
{
	unsigned int block;
	char *c;

	if (nb_params < 2) {
		printf("sdtestread <block number> <str to write>");
		return;
	}

	block = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect number of block to write");
		return;
	}

	sdcard_test_write(block, params[1]);
}

define_command(sdtestwrite, sdtestwrite, "SDCard test write", LITESDCARD_CMDS);
#endif
