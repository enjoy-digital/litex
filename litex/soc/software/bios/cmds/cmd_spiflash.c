// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"
#include <spiflash.h>
#include <jsmn_helpers.h>
#include <bios/boot.h>

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

/**
 * Command "flash_save_env"
 *
 * Save environment parameters to SPI Flash storage
 *
 */
#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE && defined FLASH_SAVE_ENV)
static void flash_save_env_handler(int nb_params, char **params)
{
	char base_env_params[ENV_VAR_SIZE];
	memset(base_env_params, 0, sizeof(base_env_params));
	unsigned int addr;
	char *c;
	if (nb_params > 1)
	{
		printf("flash_save_env <address>");
		return;
	}
	if(nb_params == 0)
		addr = (unsigned int)FLASH_ENV_ADDRESS;
	else
	{
		addr = strtoul(params[0], &c, 0);
		if (*c != 0)
		{
			printf("Incorrect address");
			return;
		}
	}
	erase_flash_subsector(addr);
	get_env_params(base_env_params, sizeof(base_env_params)); /*Getting environment parameters in JSON format*/
	print_tokens(base_env_params, NULL);
	write_to_flash(addr, (const unsigned char *)base_env_params, sizeof(base_env_params));
}

define_command(flash_save_env, flash_save_env_handler, "Save environment parameters to flash storage ", SPIFLASH_CMDS);
#endif

/**
 * Command "flash_show_env"
 *
 * Print environment parameters from flash storage
 *
 */
#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE && defined FLASH_SAVE_ENV)
static void flash_show_env_handler(int nb_params, char **params)
{
	char flash_buffer[ENV_VAR_SIZE];
	memset(flash_buffer, 0, sizeof(flash_buffer));
	memcpy((void *)flash_buffer, (void *)FLASH_ENV_ADDRESS, ENV_VAR_SIZE);
	if(nb_params == 0)
	{
		printf("Printing all environment variables...\n");
		print_tokens(flash_buffer, NULL);
	}
	else if(nb_params == 1)
	{
		print_tokens(flash_buffer, params[0]);
	}
	else
		printf("flash_show_env <token> ");
}

define_command(flash_show_env, flash_show_env_handler, "Print environment parameters from flash", SPIFLASH_CMDS);
#endif
