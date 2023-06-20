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
	if (sata_init(1))
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

static void sata_sec2mem_handler(int nb_params, char **params)
{
	char *c;
	unsigned int sec, cnt;
	uint8_t *dst;

	if (nb_params < 2) {
		printf("sata_s2m <sector> <dst_addr> [count]");
		return;
	}

	sec = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect sector number");
		return;
	}

	dst = (uint8_t *)strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect destination address");
		return;
	}

	if (nb_params == 2) {
		cnt = 1;
	} else {
		cnt = strtoul(params[2], &c, 0);
		if (*c != 0) {
			printf("Incorrect count");
			return;
		}
	}

	sata_read(sec, cnt, dst);
}

define_command(sata_sec2mem, sata_sec2mem_handler, "Read SATA into memory", LITESATA_CMDS);
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

static void sata_mem2sec_handler(int nb_params, char **params)
{
	char *c;
	unsigned int sec, cnt;
	uint8_t *src;

	if (nb_params < 2) {
		printf("sata_s2m <src_addr> <sector> [count]");
		return;
	}

	src = (uint8_t *)strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect source address");
		return;
	}

	sec = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect sector number");
		return;
	}

	if (nb_params == 2) {
		cnt = 1;
	} else {
		cnt = strtoul(params[2], &c, 0);
		if (*c != 0) {
			printf("Incorrect count");
			return;
		}
	}

	sata_write(sec, cnt, src);
}

define_command(sata_mem2sec, sata_mem2sec_handler, "Write SATA from memory", LITESATA_CMDS);
#endif
