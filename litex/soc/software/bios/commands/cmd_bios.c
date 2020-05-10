// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <id.h>
#include <generated/csr.h>
#include <crc.h>
#include <system.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "help"
 *
 * Print a list of available commands with their help text
 *
 */
static void help_handler(int nb_params, char **params)
{
	struct command_struct * const *cmd;
	int i, not_empty;

	puts("\nLiteX BIOS, available commands:\n");

	for (i = 0; i < NB_OF_GROUPS; i++) {
		not_empty = 0;
		for (cmd = __bios_cmd_start; cmd != __bios_cmd_end; cmd++) {
			if ((*cmd)->group == i) {
				printf("%-16s - %s\n", (*cmd)->name, (*cmd)->help ? (*cmd)->help : "-");
				not_empty = 1;
			}
		}
		if (not_empty)
			printf("\n");
	}
}

define_command(help, help_handler, "Print this help", MISC_CMDS);

/**
 * Command "ident"
 *
 * Print SoC identyifier if available
 *
 */
static void ident_helper(int nb_params, char **params)
{
	char buffer[IDENT_SIZE];

	get_ident(buffer);
	printf("Ident: %s", *buffer ? buffer : "-");
}

define_command(ident, ident_helper, "Display identifier", SYSTEM_CMDS);

/**
 * Command "reboot"
 *
 * Reboot the system
 *
 */
#ifdef CSR_CTRL_BASE
static void reboot(int nb_params, char **params)
{
	ctrl_reset_write(1);
}

define_command(reboot, reboot, "Reset processor", SYSTEM_CMDS);
#endif

/**
 * Command "crc"
 *
 * Compute CRC32 over an address range
 *
 */
static void crc(int nb_params, char **params)
{
	char *c;
	unsigned int addr;
	unsigned int length;

	if (nb_params < 2) {
		printf("crc <address> <length>");
		return;
	}

	addr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}

	length = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect length");
		return;
	}

	printf("CRC32: %08x", crc32((unsigned char *)addr, length));
}

define_command(crc, crc, "Compute CRC32 of a part of the address space", MISC_CMDS);

/**
 * Command "flush_cpu_dcache"
 *
 * Flush CPU data cache
 *
 */

define_command(flush_cpu_dcache, flush_cpu_dcache, "Flush CPU data cache", CACHE_CMDS);

/**
 * Command "flush_l2_cache"
 *
 * Flush L2 cache
 *
 */
#ifdef CONFIG_L2_SIZE
define_command(flush_l2_cache, flush_l2_cache, "Flush L2 cache", CACHE_CMDS);
#endif

