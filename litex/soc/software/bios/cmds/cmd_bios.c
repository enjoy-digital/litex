// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>
#include <system.h>

#include <libbase/crc.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"
#include "../sim_debug.h"

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
				printf("%-24s - %s\n", (*cmd)->name, (*cmd)->help ? (*cmd)->help : "-");
				not_empty = 1;
			}
		}
		if (not_empty)
			printf("\n");
	}
}

define_command(help, help_handler, "Print this help", SYSTEM_CMDS);

/**
 * Command "ident"
 *
 * Identifier of the system
 *
 */
static void ident_handler(int nb_params, char **params)
{
	const int IDENT_SIZE = 256;
	char buffer[IDENT_SIZE];

#ifdef CSR_IDENTIFIER_MEM_BASE_VA
	int i;
	for(i=0;i<IDENT_SIZE;i++)
		buffer[i] = MMPTR(CSR_IDENTIFIER_MEM_BASE_VA + CONFIG_CSR_ALIGNMENT/8*i);
	/* Identifier memory may be smaller than IDENT_SIZE: force termination. */
	buffer[IDENT_SIZE-1] = 0;
#else
	buffer[0] = 0;
#endif

	printf("Ident: %s\n", *buffer ? buffer : "-");
}

define_command(ident, ident_handler, "Identifier of the system", SYSTEM_CMDS);

/**
 * Command "uptime"
 *
 * Uptime of the system
 *
 */
#ifdef CSR_TIMER0_UPTIME_CYCLES_ADDR
static void uptime_handler(int nb_params, char **params)
{
	uint64_t uptime;

	timer0_uptime_latch_write(1);
	uptime = timer0_uptime_cycles_read();
	printf("Uptime: %llu sys_clk cycles - %llu seconds\n",
		uptime,
		uptime / CONFIG_CLOCK_FREQUENCY
	);
}

define_command(uptime, uptime_handler, "Uptime of the system since power-up", SYSTEM_CMDS);
#endif

/**
 * Command "crc"
 *
 * Compute CRC32 over an address range
 *
 */
static void crc_handler(int nb_params, char **params)
{
	char *c;
	uintptr_t addr;
	size_t length;

	if (nb_params < 2) {
		printf("crc <address> <length>\n");
		return;
	}

	addr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid address\n");
		return;
	}

	length = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Error: invalid length\n");
		return;
	}

	flush_cpu_dcache_range((void *)addr, length);
	flush_l2_cache();
	printf("CRC32: %08x\n", crc32((unsigned char *)addr, length));
}

define_command(crc, crc_handler, "Compute CRC32 of a part of the address space", SYSTEM_CMDS);

/**
 * Command "flush_cpu_dcache"
 *
 * Flush CPU data cache
 *
 */

define_command(flush_cpu_dcache, flush_cpu_dcache, "Flush CPU data cache", SYSTEM_CMDS);

/**
 * Command "flush_l2_cache"
 *
 * Flush L2 cache
 *
 */
#ifdef CONFIG_L2_SIZE
define_command(flush_l2_cache, flush_l2_cache, "Flush L2 cache", SYSTEM_CMDS);
#endif

/**
 * Command "buttons"
 *
 * Get buttons value
 *
 */
#ifdef CSR_BUTTONS_BASE
static void buttons_handler(int nb_params, char **params)
{
	unsigned int value;
	value = buttons_in_read();
	printf("Buttons value: 0x%x\n", value);
}
define_command(buttons, buttons_handler, "Get buttons value", SYSTEM_CMDS);
#endif

/**
 * Command "leds"
 *
 * Set LEDs value
 *
 */
#ifdef CSR_LEDS_BASE
static void leds_handler(int nb_params, char **params)
{
	char *c;
	unsigned int value;

	if (nb_params < 1) {
		printf("leds <value>\n");
		return;
	}

	value = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid value\n");
		return;
	}

	printf("Setting LEDs to 0x%x\n", value);
	leds_out_write(value);
}

define_command(leds, leds_handler, "Set LEDs value", SYSTEM_CMDS);
#endif

/**
 * Command "trace"
 *
 * Start/stop simulation trace dump.
 *
 */
#ifdef CSR_SIM_TRACE_BASE
static void cmd_sim_trace_handler(int nb_params, char **params)
{
  sim_trace(!sim_trace_enable_read());
}
define_command(trace, cmd_sim_trace_handler, "Toggle simulation tracing", SYSTEM_CMDS);
#endif

/**
 * Command "finish"
 *
 * Finish simulation.
 *
 */
#ifdef CSR_SIM_FINISH_BASE
static void cmd_sim_finish_handler(int nb_params, char **params)
{
  sim_finish();
}
define_command(finish, cmd_sim_finish_handler, "Finish simulation", SYSTEM_CMDS);
#endif

/**
 * Command "mark"
 *
 * Set a debug marker value
 *
 */
#ifdef CSR_SIM_MARKER_BASE
static void cmd_sim_mark_handler(int nb_params, char **params)
{
  // cannot use param[1] as it is not a const string
  sim_mark(NULL);
}
define_command(mark, cmd_sim_mark_handler, "Set a debug simulation marker", SYSTEM_CMDS);
#endif
