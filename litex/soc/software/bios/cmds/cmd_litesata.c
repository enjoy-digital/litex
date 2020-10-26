// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include <liblitesata/sata.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "sata_read"
 *
 * Perform SATA block read
 *
 */
#ifdef CSR_SATA_BLOCK2MEM_BASE
static void sata_read_handler(int nb_params, char **params)
{
	unsigned int block;
	char *c;
	uint8_t buf[512];

	if (nb_params < 1) {
		printf("sata_read <block>");
		return;
	}

	block = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect block number");
		return;
	}

	sata_read(block, 1, buf);
	dump_bytes((uint32_t *)buf, 512, (unsigned long) buf);
}

define_command(sata_read, sata_read_handler, "Read SATA block", LITESATA_CMDS);
#endif

