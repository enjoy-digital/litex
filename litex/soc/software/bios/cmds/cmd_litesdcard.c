// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include <liblitesdcard/sdcard.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "sdcard_detect"
 *
 * Detect SDcard
 *
 */
#ifdef CSR_SDPHY_BASE
static void sdcard_detect_handler(int nb_params, char **params)
{
	uint8_t cd = sdphy_card_detect_read();
	printf("SDCard %sinserted.\n", cd ? "not " : "");
}

define_command(sdcard_detect, sdcard_detect_handler, "Detect SDCard", LITESDCARD_CMDS);
#endif

/**
 * Command "sdcard_init"
 *
 * Initialize SDcard
 *
 */
#ifdef CSR_SDCORE_BASE
static void sdcard_init_handler(int nb_params, char **params)
{
	printf("Initialize SDCard... ");
	if (sdcard_init())
		printf("Successful.\n");
	else
		printf("Failed.\n");
}

define_command(sdcard_init, sdcard_init_handler, "Initialize SDCard", LITESDCARD_CMDS);
#endif

/**
 * Command "sdcard_freq"
 *
 * Set SDcard clock frequency
 *
 */
#ifdef CSR_SDCORE_BASE
static void sdcard_freq_handler(int nb_params, char **params)
{
	unsigned int freq;
	char *c;

	if (nb_params < 1) {
		printf("sdcard_freq <freq>");
		return;
	}

	freq = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect freq");
		return;
	}
	sdcard_set_clk_freq(freq, 1);
}

define_command(sdcard_freq, sdcard_freq_handler, "Set SDCard clock freq", LITESDCARD_CMDS);
#endif

/**
 * Command "sdcard_read"
 *
 * Perform SDcard block read
 *
 */
#ifdef CSR_SDBLOCK2MEM_BASE
static void sdcard_read_handler(int nb_params, char **params)
{
	unsigned int block;
	char *c;
	uint8_t buf[512];

	if (nb_params < 1) {
		printf("sdcard_read <block>");
		return;
	}

	block = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect block number");
		return;
	}

	sdcard_read(block, 1, buf);
	dump_bytes((unsigned int *)buf, 512, (unsigned long) buf);
}

define_command(sdcard_read, sdcard_read_handler, "Read SDCard block", LITESDCARD_CMDS);
#endif

/**
 * Command "sdwrite"
 *
 * Perform SDcard block write
 *
 */
#ifdef CSR_SDMEM2BLOCK_BASE
static void sdcard_write_handler(int nb_params, char **params)
{
	int i;
	uint8_t buf[512];
	unsigned int block;
	char *c;

	if (nb_params < 2) {
		printf("sdcard_write <block> <str>");
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
	dump_bytes((unsigned int *)buf, 512, (unsigned long) buf);
	sdcard_write(block, 1, buf);
}

define_command(sdcard_write, sdcard_write_handler, "Write SDCard block", LITESDCARD_CMDS);
#endif
