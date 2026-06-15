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
 * Detect SDCard
 *
 */
#ifdef CSR_SDCARD_PHY_CARD_DETECT_ADDR
static void sdcard_detect_handler(int nb_params, char **params)
{
	uint8_t cd = sdcard_phy_card_detect_read();
	printf("SDCard %sinserted.\n", cd ? "not " : "");
}

define_command(sdcard_detect, sdcard_detect_handler, "Detect SDCard", LITESDCARD_CMDS);
#endif

/**
 * Command "sdcard_init"
 *
 * Initialize SDCard
 *
 */
#ifdef CSR_SDCARD_BASE
static void sdcard_init_handler(int nb_params, char **params)
{
	bios_print_status("Initialize SDCard", sdcard_init());
}

define_command(sdcard_init, sdcard_init_handler, "Initialize SDCard", LITESDCARD_CMDS);
#endif

/**
 * Command "sdcard_freq"
 *
 * Set SDCard clock frequency
 *
 */
#ifdef CSR_SDCARD_BASE
static void sdcard_freq_handler(int nb_params, char **params)
{
	unsigned int freq;
	char *c;

	if (nb_params < 1) {
		printf("sdcard_freq <freq>\n");
		return;
	}

	freq = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid freq\n");
		return;
	}
	sdcard_set_clk_freq(freq, 1);
}

define_command(sdcard_freq, sdcard_freq_handler, "Set SDCard clock freq", LITESDCARD_CMDS);
#endif

/**
 * Command "sdcard_read"
 *
 * Perform SDCard block read
 *
 */
#ifdef CSR_SDCARD_BLOCK2MEM_DMA_BASE_ADDR
static void sdcard_read_handler(int nb_params, char **params)
{
	unsigned int block;
	unsigned int count = 1;
	unsigned long addr;
	char *c;
	uint8_t buf[512];
	uint8_t *dst = buf;

	if (nb_params < 1) {
		printf("sdcard_read <block> [addr] [count]\n");
		return;
	}

	block = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid block number\n");
		return;
	}
	if (nb_params >= 2) {
		addr = strtoul(params[1], &c, 0);
		if (*c != 0) {
			printf("Error: invalid destination address\n");
			return;
		}
		dst = (uint8_t *)(uintptr_t)addr;
	}
	if (nb_params >= 3) {
		count = strtoul(params[2], &c, 0);
		if (*c != 0) {
			printf("Error: invalid count\n");
			return;
		}
	}

	if (sdcard_read(block, count, dst) != SD_OK) {
		printf("Error: SDCard read failed\n");
		return;
	}
	/* Only dump single-block reads (multi-block reads are memory loads) */
	if (count == 1)
		dump_bytes((unsigned int *)dst, 512, (unsigned long)dst);
}

define_command(sdcard_read, sdcard_read_handler, "Read SDCard block", LITESDCARD_CMDS);
#endif

/**
 * Command "sdcard_write"
 *
 * Perform SDCard block write
 *
 */
#ifdef CSR_SDCARD_MEM2BLOCK_DMA_BASE_ADDR
static void sdcard_write_handler(int nb_params, char **params)
{
	int i;
	uint8_t buf[512];
	unsigned int block;
	char *c;

	if (nb_params < 2) {
		printf("sdcard_write <block> <str>\n");
		return;
	}

	block = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid block number\n");
		return;
	}

	c = params[1];
	for(i=0; i<512; i++) {
		buf[i] = *c;
		if(*(++c) == 0) {
			c = params[1];
		}
	}
	dump_bytes((unsigned int *)buf, 512, (unsigned long) buf);
	if (sdcard_write(block, 1, buf) != SD_OK)
		printf("Error: SDCard write failed\n");
}

define_command(sdcard_write, sdcard_write_handler, "Write SDCard block", LITESDCARD_CMDS);
#endif
