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

#ifdef CSR_IDENTIFIER_MEM_BASE
	int i;
	for(i=0;i<IDENT_SIZE;i++)
		buffer[i] = MMPTR(CSR_IDENTIFIER_MEM_BASE + CONFIG_CSR_ALIGNMENT/8*i);
#else
	buffer[0] = 0;
#endif

	printf("Ident: %s", *buffer ? buffer : "-");
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
	unsigned long uptime;

	timer0_uptime_latch_write(1);
	uptime = timer0_uptime_cycles_read();
	printf("Uptime: %ld sys_clk cycles / %ld seconds",
		uptime,
		uptime/CONFIG_CLOCK_FREQUENCY
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
 * Set Buttons value
 *
 */
#ifdef CSR_BUTTONS_BASE
static void buttons_handler(int nb_params, char **params)
{
	unsigned int value;
	value = buttons_in_read();
	printf("Buttons value: 0x%x", value);
}
define_command(buttons, buttons_handler, "Get Buttons value", SYSTEM_CMDS);
#endif

/**
 * Command "leds"
 *
 * Set Leds value
 *
 */
#ifdef CSR_LEDS_BASE
static void leds_handler(int nb_params, char **params)
{
	char *c;
	unsigned int value;

	if (nb_params < 1) {
		printf("leds <value>");
		return;
	}

	value = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}

	printf("Settings Leds to 0x%x", value);
	leds_out_write(value);
}

define_command(leds, leds_handler, "Set Leds value", SYSTEM_CMDS);
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
