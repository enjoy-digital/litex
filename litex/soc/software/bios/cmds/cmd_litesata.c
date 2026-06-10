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
	bios_print_status("Initialize SATA", sata_init(1));
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
		printf("sata_read <sector>\n");
		return;
	}

	sector = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid sector number\n");
		return;
	}

	if (sata_read(sector, 1, buf) != 0) {
		printf("Error: SATA read failed\n");
		return;
	}
	dump_bytes((unsigned int *)buf, 512, (unsigned long) buf);
}

define_command(sata_read, sata_read_handler, "Read SATA sector", LITESATA_CMDS);

static void sata_sec2mem_handler(int nb_params, char **params)
{
	char *c;
	unsigned int sec, cnt;
	uint8_t *dst;

	if (nb_params < 2) {
		printf("sata_sec2mem <sector> <dst_addr> [count]\n");
		return;
	}

	sec = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid sector number\n");
		return;
	}

	dst = (uint8_t *)strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Error: invalid destination address\n");
		return;
	}

	if (nb_params == 2) {
		cnt = 1;
	} else {
		cnt = strtoul(params[2], &c, 0);
		if (*c != 0) {
			printf("Error: invalid count\n");
			return;
		}
	}

	if (sata_read(sec, cnt, dst) != 0)
		printf("Error: SATA read failed\n");
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
		printf("sata_write <sector> <str>\n");
		return;
	}

	sector = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid sector number\n");
		return;
	}

	c = params[1];
	for(i=0; i<512; i++) {
		buf[i] = *c;
		if(*(++c) == 0) {
			c = params[1];
		}
	}
	dump_bytes((unsigned int *)buf, 512, (unsigned long) buf);
	if (sata_write(sector, 1, buf) != 0)
		printf("Error: SATA write failed\n");
}

define_command(sata_write, sata_write_handler, "Write SATA sector", LITESATA_CMDS);

static void sata_mem2sec_handler(int nb_params, char **params)
{
	char *c;
	unsigned int sec, cnt;
	uint8_t *src;

	if (nb_params < 2) {
		printf("sata_mem2sec <src_addr> <sector> [count]\n");
		return;
	}

	src = (uint8_t *)strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid source address\n");
		return;
	}

	sec = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Error: invalid sector number\n");
		return;
	}

	if (nb_params == 2) {
		cnt = 1;
	} else {
		cnt = strtoul(params[2], &c, 0);
		if (*c != 0) {
			printf("Error: invalid count\n");
			return;
		}
	}

	if (sata_write(sec, cnt, src) != 0)
		printf("Error: SATA write failed\n");
}

define_command(sata_mem2sec, sata_mem2sec_handler, "Write SATA from memory", LITESATA_CMDS);
#endif

/* LiteSATA read/write test */
#if defined(CSR_SATA_SECTOR2MEM_BASE) && defined(CSR_SATA_MEM2SECTOR_BASE)
#include <string.h>

static int sata_rd_1(uint32_t sector, uint32_t count, void *mem)
{
	while(count--) {
		if (sata_read(sector++, 1, mem) != 0) {
			printf("sata_rd_1: read failed at sector %lu\n", (unsigned long)(sector - 1));
			return -1;
		}
		mem += 512;
	}
	return 0;
}

static int sata_mem_cmp(char *mem1, char *mem2, uint32_t count)
{
	uint32_t i, j;

	for (i = 0; i < count; i++)
		for (j = 0; j < 512; j++)
			if (mem1[512*i + j] != mem2[512*i + j]) {
				printf("sata_mem_cmp: mismatch in sector %d "
					"byte %d: %d != %d\n",
					i, j, mem1[512*i + j], mem2[512*i + j]);
				return -1;
			}
	return 0;
}

static int sata_do_rwtest(uint32_t sec, uint32_t cnt, char *mem, char *str)
{
	char *c = str;
	int i;

	if (c != NULL) {
		for (i = 0; i < 512 * cnt; i++) {
			mem[i] = *c++;
			if (*c == 0)
				c = str;
		}
	}
	if (sata_write(sec, cnt, (uint8_t *)mem) != 0) {
		printf("sata_do_rwtest: write failed\n");
		return -1;
	}
	if (sata_read(sec, cnt, (uint8_t *)(mem + 512*cnt)) != 0) {
		printf("sata_do_rwtest: read failed\n");
		return -1;
	}
	if (sata_mem_cmp(mem, mem + 512*cnt, cnt) == 0)
		return 0;
	printf("compare failed, retrying with single-sector reads:\n");
	return sata_rd_1(sec, cnt, mem + 512*cnt);
}

static void sata_rwtest_handler(int nb_params, char **params)
{
	unsigned int sec, cnt;
	char *mem;
	char *c;

	if (nb_params < 4) {
		printf("sata_rwtest <sector> <address> <count> <str>\n");
		printf("  Warning: overwrites <count> disk sectors starting at <sector>\n");
		printf("  and 2*512*<count> bytes of memory at <address>.\n");
		return;
	}

	sec = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid sector\n");
		return;
	}

	mem = (char *)strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Error: invalid address\n");
		return;
	}

	cnt = strtoul(params[2], &c, 0);
	if (*c != 0) {
		printf("Error: invalid count\n");
		return;
	}

	if (sata_do_rwtest(sec, cnt, mem, params[3]))
		printf("Failure.\n");
	else
		printf("Success.\n");
}
define_command(sata_rwtest, sata_rwtest_handler, "SATA read/write test", LITESATA_CMDS);
#endif
