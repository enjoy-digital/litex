// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include <libliteeth/mdio.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "mdiow"
 *
 * Write MDIO register
 *
 */
#ifdef CSR_ETHPHY_MDIO_W_ADDR
static void mdiow_handler(int nb_params, char **params)
{
	char *c;
	unsigned int phyadr2;
	unsigned int reg2;
	unsigned int val2;

	if (nb_params < 3) {
		printf("mdiow <phyadr> <reg> <value>");
		return;
	}

	phyadr2 = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect phyadr");
		return;
	}

	reg2 = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect reg");
		return;
	}

	val2 = strtoul(params[2], &c, 0);
	if (*c != 0) {
		printf("Incorrect val");
		return;
	}

	mdio_write(phyadr2, reg2, val2);
}

define_command(mdiow, mdiow_handler, "Write MDIO register", LITEETH_CMDS);
#endif

/**
 * Command "mdior"
 *
 * Read MDIO register
 *
 */
#ifdef CSR_ETHPHY_MDIO_W_ADDR
static void mdior_handler(int nb_params, char **params)
{
	char *c;
	unsigned int phyadr2;
	unsigned int reg2;
	unsigned int val;

	if (nb_params < 2) {
		printf("mdior <phyadr> <reg>");
		return;
	}

	phyadr2 = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect phyadr");
		return;
	}

	reg2 = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect reg");
		return;
	}

	val = mdio_read(phyadr2, reg2);
	printf("Reg %d: 0x%04x", reg2, val);
}

define_command(mdior, mdior_handler, "Read MDIO register", LITEETH_CMDS);
#endif

/**
 * Command "mdiod"
 *
 * Dump MDIO registers
 *
 */
#ifdef CSR_ETHPHY_MDIO_W_ADDR
static void mdiod_handler(int nb_params, char **params)
{
	char *c;
	unsigned int phyadr;
	unsigned int count;
	unsigned int val;
	int i;

	if (nb_params < 2) {
		printf("mdiod <phyadr> <count>");
		return;
	}

	phyadr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect phyadr");
		return;
	}

	count = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect count");
		return;
	}

	printf("MDIO dump @0x%x:\n", phyadr);
	for (i = 0; i < count; i++) {
		val = mdio_read(phyadr, i);
		printf("reg %d: 0x%04x", i, val);
	}
}

define_command(mdiod, mdiod_handler, "Dump MDIO registers", LITEETH_CMDS);
#endif
