// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include <liblitesata/sata.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "sata_init"
 *
 * Initialize SATA
 *
 */
#ifdef CSR_SATA_PHY_BASE
static void sata_init_handler(int nb_params, char **params)
{
	printf("Initialize SATA... ");
	if (sata_init())
		printf("Successful.\n");
	else
		printf("Failed.\n");
}

define_command(sata_init, sata_init_handler, "Initialize SATA", LITESATA_CMDS);
#endif

/**
 * Command "sata_read"
 *
 * Perform SATA sector read
 *
 */
#ifdef CSR_SATA_SECTOR2MEM_BASE
static void sata_read_handler(int nb_params, char **params)
{
	unsigned int sector;
	char *c;
	uint8_t buf[512];

	if (nb_params < 1) {
		printf("sata_read <sector>");
		return;
	}

	sector = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect sector number");
		return;
	}

	sata_read(sector, 1, buf);
	dump_bytes((unsigned int *)buf, 512, (unsigned long) buf);
}

define_command(sata_read, sata_read_handler, "Read SATA sector", LITESATA_CMDS);
#endif

/**
 * Command "sata_write"
 *
 * Perform SATA sector write
 *
 */
#ifdef CSR_SATA_MEM2SECTOR_BASE
static void sata_write_handler(int nb_params, char **params)
{
	int i;
	uint8_t buf[512];
	unsigned int sector;
	char *c;

	if (nb_params < 2) {
		printf("sata_write <sector> <str>");
		return;
	}

	sector = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect sector number");
		return;
	}

	c = params[1];
	if (params[1] != NULL) {
		for(i=0; i<512; i++) {
			buf[i] = *c;
			if(*(++c) == 0) {
				c = params[1];
			}
		}
	}
	dump_bytes((unsigned int *)buf, 512, (unsigned long) buf);
	sata_write(sector, 1, buf);
}

define_command(sata_write, sata_write_handler, "Write SATA sector", LITESATA_CMDS);
#endif
