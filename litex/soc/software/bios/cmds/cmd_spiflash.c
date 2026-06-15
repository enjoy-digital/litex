// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"

#include <libbase/progress.h>
#include <liblitespi/spiflash.h>
#include <libfatfs/ff.h>

/**
 * Command "flash_write"
 *
 * Write data from a memory buffer to SPI flash
 *
 */
#if (defined CSR_SPIFLASH_MASTER_CS_ADDR)
static void flash_write_handler(int nb_params, char **params)
{
	char *c;
	unsigned int addr;
	unsigned int mem_addr;
	unsigned int count;

	if (nb_params < 2) {
		printf("flash_write <offset> <mem_addr> [count]\n");
		return;
	}

	addr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid offset\n");
		return;
	}

	mem_addr = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Error: invalid mem_addr\n");
		return;
	}

	if (nb_params == 2) {
		count = 1;
	} else {
		count = strtoul(params[2], &c, 0);
		if (*c != 0) {
			printf("Error: invalid count\n");
			return;
		}
	}

	if (spiflash_write_stream(addr, (unsigned char *)mem_addr, count) != (int)count)
		printf("Error: flash write failed (is the region erased? see flash_erase_range)\n");
}

define_command(flash_write, flash_write_handler, "Write to flash", SPIFLASH_CMDS);

static void flash_from_sdcard_handler(int nb_params, char **params)
{
	FRESULT fr;
	FATFS fs;
	FIL file;
	uint32_t br;
	uint32_t offset;
	unsigned long length;
	uint8_t buf[512];

	if (nb_params < 1) {
		printf("flash_from_sdcard <filename>\n");
		return;
	}

	char* filename = params[0];

	fr = f_mount(&fs, "", 1);
	if (fr != FR_OK) {
		printf("Error: filesystem mount failed (FatFs error %d)\n", fr);
		return;
	}
	fr = f_open(&file, filename, FA_READ);
	if (fr != FR_OK) {
		printf("%s file not found.\n", filename);
		f_mount(0, "", 0);
		return;
	}

	length = f_size(&file);
	printf("Copying %s to SPI flash (%ld bytes)...\n", filename, length);
	init_progression_bar(length);
	offset = 0;
	for (;;) {
		fr = f_read(&file, (void*) buf, 512, (UINT *)&br);
		if (fr != FR_OK) {
			printf("Error: file read failed\n");
			f_close(&file);
			f_mount(0, "", 0);
			return;
		}
		if (br == 0) {
			break;
		} else {
			if (spiflash_write_stream(offset, buf, br) != (int)br) {
				printf("Error: flash write failed (is the region erased? see flash_erase_range)\n");
				f_close(&file);
				f_mount(0, "", 0);
				return;
			}
		}

		offset += br;
		show_progress(offset);
	}
	show_progress(offset);
	printf("\n");

	f_close(&file);
	f_mount(0, "", 0);
}
define_command(flash_from_sdcard, flash_from_sdcard_handler, "Write file from SD card to flash", SPIFLASH_CMDS);

static void flash_erase_range_handler(int nb_params, char **params)
{
	char *c;
	uint32_t addr;
	uint32_t count;

	if (nb_params < 2) {
		printf("flash_erase_range <offset> <count>\n");
		return;
	}

	addr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Error: invalid offset\n");
		return;
	}

	count = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Error: invalid count\n");
		return;
	}

	spiflash_erase_range(addr, count);
}

define_command(flash_erase_range, flash_erase_range_handler, "Erase flash range", SPIFLASH_CMDS);
#endif
