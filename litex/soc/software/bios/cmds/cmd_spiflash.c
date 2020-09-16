// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "flash_write"
 *
 * Write data from a memory buffer to SPI flash
 *
 */
#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)
static void flash_write_handler(int nb_params, char **params)
{
	char *c;
	unsigned int addr;
	unsigned int value;
	unsigned int count;
	unsigned int i;

	if (nb_params < 2) {
		printf("flash_write <offset> <value> [count]");
		return;
	}

	addr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect offset");
		return;
	}

	value = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	if (nb_params == 2) {
		count = 1;
	} else {
		count = strtoul(params[2], &c, 0);
		if (*c != 0) {
			printf("Incorrect count");
			return;
		}
	}

	for (i = 0; i < count; i++)
		write_to_flash(addr + i * 4, (unsigned char *)&value, 4);
}

define_command(flash_write, flash_write_handler, "Write to flash", SPIFLASH_CMDS);
#endif

/**
 * Command "flash_erase"
 *
 * Flash erase
 *
 */
#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)
static void flash_erase_handler(int nb_params, char **params)
{
	erase_flash();
	printf("Flash erased\n");
}

define_command(flash_erase, flash_erase_handler, "Erase whole flash", SPIFLASH_CMDS);
#endif

