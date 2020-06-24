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
		printf("sdclk <freq>");
		return;
	}

	frequ = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect freq");
		return;
	}

	sdcard_set_clk(frequ);
}

struct command_struct cmd_sdclk =
{
	.func = sdclk,
	.name = "sdclk",
	.help = "Set SDCard clk freq (Mhz)",
};

define_command(sdclk, sdclk, "Set SDCard clk freq (Mhz)", LITESDCARD_CMDS);
#endif

/**
 * Command "sdinit"
 *
 * Initialize SDcard
 *
 */
#ifdef CSR_SDCORE_BASE
define_command(sdinit, sdcard_init, "Initialize SDCard", LITESDCARD_CMDS);
#endif


/**
 * Command "sdread"
 *
 * Perform SDcard block read
 *
 */
#ifdef CSR_SDCORE_BASE
static void sdread(int nb_params, char **params)
{
	unsigned int block;
	char *c;
	uint8_t buf[512];

	if (nb_params < 1) {
		printf("sdread <block>");
		return;
	}

	block = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect block number");
		return;
	}

	sdcard_read(block*512, 1, buf);
	dump_bytes((uint32_t *)buf, 512, (unsigned long) buf);
}

define_command(sdread, sdread, "Read SDCard block", LITESDCARD_CMDS);
#endif

/**
 * Command "sdwrite"
 *
 * Perform SDcard block write
 *
 */
#ifdef CSR_SDCORE_BASE
static void sdwrite(int nb_params, char **params)
{
	int i;
	uint8_t buf[512];
	unsigned int block;
	char *c;

	if (nb_params < 2) {
		printf("sdwrite <block> <str>");
		return;
	}

	block = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect block number");
		return;
	}

	c = params[1];
	if (params[1] != NULL) {
		for(i=0; i<512; i++) {
			buf[i] = *c;
			if(*(++c) == 0) {
				c = params[1];
			}
		}
	}
	dump_bytes((uint32_t *)buf, 512, (unsigned long) buf);
	sdcard_write(block*512, 1, buf);
}

define_command(sdwrite, sdwrite, "Write SDCard block", LITESDCARD_CMDS);
#endif
