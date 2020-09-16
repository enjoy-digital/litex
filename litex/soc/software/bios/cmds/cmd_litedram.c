// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <i2c.h>

#include <liblitedram/sdram.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "sdrinit"
 *
 * Start SDRAM initialisation
 *
 */
#if defined(CSR_SDRAM_BASE) && defined(CSR_DDRPHY_BASE)
define_command(sdrinit, sdrinit, "Start SDRAM initialisation", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrwlon"
 *
 * Write leveling ON
 *
 */
#if defined(CSR_DDRPHY_BASE) && defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) && defined(CSR_SDRAM_BASE)
define_command(sdrwlon, sdrwlon, "Enable write leveling", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrwloff"
 *
 * Write leveling OFF
 *
 */
#if defined(CSR_DDRPHY_BASE) && defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) && defined(CSR_SDRAM_BASE)
define_command(sdrwloff, sdrwloff, "Disable write leveling", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrlevel"
 *
 * Perform read/write leveling
 *
 */
#if defined(CSR_DDRPHY_BASE) && defined(CSR_SDRAM_BASE)
define_command(sdrlevel, sdrlevel, "Perform read/write leveling", LITEDRAM_CMDS);
#endif

/**
 * Command "spdread"
 *
 * Read contents of SPD EEPROM memory.
 * SPD address is a 3-bit address defined by the pins A0, A1, A2.
 *
 */
#ifdef CSR_I2C_BASE
#define SPD_RW_PREAMBLE    0b1010
#define SPD_RW_ADDR(a210)  ((SPD_RW_PREAMBLE << 3) | ((a210) & 0b111))

static void spdread_handler(int nb_params, char **params)
{
	char *c;
	unsigned char spdaddr;
	unsigned char buf[256];
	int len = sizeof(buf);
	bool send_stop = true;

	if (nb_params < 1) {
		printf("spdread <spdaddr> [<send_stop>]");
		return;
	}

	spdaddr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}
	if (spdaddr > 0b111) {
		printf("SPD EEPROM max address is 0b111 (defined by A0, A1, A2 pins)");
		return;
	}

	if (nb_params > 1) {
		send_stop = strtoul(params[1], &c, 0) != 0;
		if (*c != 0) {
			printf("Incorrect send_stop value");
			return;
		}
	}

	if (!i2c_read(SPD_RW_ADDR(spdaddr), 0, buf, len, send_stop)) {
		printf("Error when reading SPD EEPROM");
		return;
	}

	dump_bytes((unsigned int *) buf, len, 0);

#ifdef SPD_BASE
	{
		int cmp_result;
		cmp_result = memcmp(buf, (void *) SPD_BASE, SPD_SIZE);
		if (cmp_result == 0) {
			printf("Memory conents matches the data used for gateware generation\n");
		} else {
			printf("\nWARNING: memory differs from the data used during gateware generation:\n");
			dump_bytes((void *) SPD_BASE, SPD_SIZE, 0);
		}
	}
#endif
}
define_command(spdread, spdread_handler, "Read SPD EEPROM", LITEDRAM_CMDS);
#endif
