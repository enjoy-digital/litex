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
		printf("sata_sec2mem <sector> <dst_addr> [count]");
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
		printf("sata_mem2sec <src_addr> <sector> [count]");
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

/* LiteSATA read/write test */
#if defined(CSR_SATA_SECTOR2MEM_BASE) && defined(CSR_SATA_MEM2SECTOR_BASE)
#include <string.h>
static int sata_rd(uint32_t sector, uint32_t count, void *mem)
{
	uint32_t done_cnt;
	uint8_t retry_cnt;

	for (retry_cnt = 8; retry_cnt > 0; retry_cnt--) {
		sata_sector2mem_base_write((uint64_t)(uintptr_t)mem);
		sata_sector2mem_sector_write(sector);
		sata_sector2mem_nsectors_write(count);
		sata_sector2mem_start_write(1);
		for (done_cnt = 0x0000ffff; done_cnt > 0; done_cnt --) {
			if ((sata_sector2mem_done_read() & 0x1) != 0) {
				if ((sata_sector2mem_error_read() & 0x1) == 0)
					return 0;
				else {
					printf("sata_rd: op failed, retry\n");
					break;
				}
			}
		}
		printf("sata_rd: op timeout (done_cnt)\n");
		busy_wait_us(10);
	}
	printf("sata_rd: out of retries\n");
	return -1;
}

static int sata_rd_1(uint32_t sector, uint32_t count, void *mem)
{
	while(count--) {
		sata_read(sector++, 1, mem);
		mem += 512;
	}
	return 0;
}

static int sata_wr(uint32_t sector, uint32_t count, void *mem)
{
	uint32_t done_cnt;
	uint8_t retry_cnt;

	for (retry_cnt = 8; retry_cnt > 0; retry_cnt--) {
		sata_mem2sector_base_write((uint64_t)(uintptr_t)mem);
		sata_mem2sector_sector_write(sector);
		sata_mem2sector_nsectors_write(count);
		sata_mem2sector_start_write(1);
		for (done_cnt = 0x000fffff; done_cnt > 0; done_cnt --) {
			if ((sata_mem2sector_done_read() & 0x1) != 0) {
				if ((sata_mem2sector_error_read() & 0x1) == 0)
					return 0;
				else {
					printf("sata_wr: op failed, retry\n");
					break;
				}
			}
		}
		printf("sata_wr: op timeout (done_cnt)\n");
		busy_wait_us(10);
	}
	printf("sata_wr: out of retries\n");
	return -1;
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
	if (sata_wr(sec, cnt, mem) < 0)
		return -1;
	if (sata_rd(sec, cnt, mem + 512*cnt) < 0)
		return -1;
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
		printf("sata_rwtest <sector> <address> <count> <str>");
		return;
	}

	sec = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("incorrect sector");
		return;
	}

	mem = (char *)strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("incorrect address");
		return;
	}

	cnt = strtoul(params[2], &c, 0);
	if (*c != 0) {
		printf("incorrect count");
		return;
	}

	if (sata_do_rwtest(sec, cnt, mem, params[3]))
		printf("Failure.");
	else
		printf("Success.");
}
define_command(sata_rwtest, sata_rwtest_handler, "SATA read/write test", LITESATA_CMDS);
#endif
