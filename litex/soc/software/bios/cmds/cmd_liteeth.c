// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include <libliteeth/mdio.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "mdio_write"
 *
 * Write MDIO register
 *
 */
#ifdef CSR_ETHPHY_MDIO_W_ADDR
static void mdio_write_handler(int nb_params, char **params)
{
	char *c;
	unsigned int phyadr2;
	unsigned int reg2;
	unsigned int val2;

	if (nb_params < 3) {
		printf("mdio_write <phyadr> <reg> <value>");
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

	printf("MDIO write @0x%x: 0x%02x 0x%04x\n", phyadr2, reg2, val2);
	mdio_write(phyadr2, reg2, val2);
}

define_command(mdio_write, mdio_write_handler, "Write MDIO register", LITEETH_CMDS);
#endif

/**
 * Command "mdio_read"
 *
 * Read MDIO register
 *
 */
#ifdef CSR_ETHPHY_MDIO_W_ADDR
static void mdio_read_handler(int nb_params, char **params)
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

	printf("MDIO read @0x%x:\n", phyadr2);
	val = mdio_read(phyadr2, reg2);
	printf("0x%02x 0x%04x", reg2, val);
}

define_command(mdio_read, mdio_read_handler, "Read MDIO register", LITEETH_CMDS);
#endif

/**
 * Command "mdio_dump"
 *
 * Dump MDIO registers
 *
 */
#ifdef CSR_ETHPHY_MDIO_W_ADDR
static void mdio_dump_handler(int nb_params, char **params)
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
		printf("0x%02x 0x%04x\n", i, val);
	}
}

define_command(mdio_dump, mdio_dump_handler, "Dump MDIO registers", LITEETH_CMDS);
#endif
