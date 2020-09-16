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
 * Command "sdram_init"
 *
 * Initialize SDRAM (Init + Calibration)
 *
 */
#if defined(CSR_SDRAM_BASE) && defined(CSR_DDRPHY_BASE)
define_command(sdram_init, sdram_init, "Initialize SDRAM (Init + Calibration)", LITEDRAM_CMDS);
#endif

/**
 * Command "sdram_calibration"
 *
 * Calibrate SDRAM
 *
 */
#if defined(CSR_SDRAM_BASE) && defined(CSR_DDRPHY_BASE)
define_command(sdram_cal, sdram_calibration, "Calibrate SDRAM", LITEDRAM_CMDS);
#endif

/**
 * Command "sdram_mrw"
 *
 * Write SDRAM Mode Register
 *
 */
#if defined(CSR_SDRAM_BASE) && defined(CSR_DDRPHY_BASE)
static void sdram_mrw_handler(int nb_params, char **params)
{
	char *c;
	uint8_t reg;
	uint16_t value;

	if (nb_params < 2) {
		printf("sdram_mrw <reg> <value>");
		return;
	}
	reg = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect reg");
		return;
	}
	value = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}
	printf("Writing 0x%04x to MR%d", value, reg);
	sdram_mode_register_write(reg, value);
}
define_command(sdram_mrw, sdram_mrw_handler, "Write SDRAM Mode Register", LITEDRAM_CMDS);
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
