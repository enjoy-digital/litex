// This file is Copyright (c) 2017 Florent Kermarrec <florent@enjoy-digital.fr>

// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <string.h>

#include <libbase/console.h>
#include <libbase/crc.h>

#include "readline.h"
#include "helpers.h"
#include "command.h"
#include "init.h"

extern unsigned int _ftext, _edata_rom;

#define NUMBER_OF_BYTES_ON_A_LINE 16
void dump_bytes(unsigned int *ptr, int count, unsigned long addr)
{
	char *data = (char *)ptr;
	int line_bytes = 0, i = 0;

	fputs("Memory dump:", stdout);
	while (count > 0) {
		line_bytes =
			(count > NUMBER_OF_BYTES_ON_A_LINE)?
				NUMBER_OF_BYTES_ON_A_LINE : count;

		printf("\n0x%08lx  ", addr);
		for (i = 0; i < line_bytes; i++)
			printf("%02x ", *(unsigned char *)(data+i));

		for (; i < NUMBER_OF_BYTES_ON_A_LINE; i++)
			printf("   ");

		printf(" ");

		for (i = 0; i<line_bytes; i++) {
			if ((*(data+i) < 0x20) || (*(data+i) > 0x7e))
				printf(".");
			else
				printf("%c", *(data+i));
		}

		for (; i < NUMBER_OF_BYTES_ON_A_LINE; i++)
			printf(" ");

		data += (char)line_bytes;
		count -= line_bytes;
		addr += line_bytes;
	}
	printf("\n");
}

void crcbios(void)
{
	unsigned long offset_bios;
	unsigned long length;
	unsigned int expected_crc;
	unsigned int actual_crc;

	/*
	 * _edata_rom is located right after the end of the flat
	 * binary image. The CRC tool writes the 32-bit CRC here.
	 * We also use the address of _edata_rom to know the length
	 * of our code.
	 */
	offset_bios = (unsigned long)&_ftext;
	expected_crc = _edata_rom;
	length = (unsigned long)&_edata_rom - offset_bios;
	actual_crc = crc32((unsigned char *)offset_bios, length);
	if (expected_crc == actual_crc)
		printf(" BIOS CRC passed (%08x)\n", actual_crc);
	else {
		printf(" BIOS CRC failed (expected %08x, got %08x)\n", expected_crc, actual_crc);
		printf(" The system will continue, but expect problems.\n");
	}
}

int get_param(char *buf, char **cmd, char **params)
{
	int nb_param = 0;
	int i;

	for (i = 0; i < MAX_PARAM; i++)
		params[i] = NULL;

	*cmd = buf;

	while ((*buf != ' ') && (*buf !=0))
		buf++;

	if (*buf == 0)
		return nb_param;

	*buf++ = 0;

	while (1) {
		while ((*buf == ' ') && (*buf !=0))
			buf++;


		if (*buf == 0)
			return nb_param;

		params[nb_param++] = buf;

		while ((*buf != ' ') && (*buf !=0))
			buf++;

		if (*buf == 0)
			return nb_param;
		*buf++ = 0;
	}
}

struct command_struct *command_dispatcher(char *command, int nb_params, char **params)
{
	struct command_struct * const *cmd;

	for (cmd = __bios_cmd_start; cmd != __bios_cmd_end; cmd++) {
		if (!strcmp(command, (*cmd)->name)) {
			(*cmd)->func(nb_params, params);
			return (*cmd);
		}
	}

	return NULL;
}

void init_dispatcher(void)
{
	for (const init_func* fp = __bios_init_start; fp != __bios_init_end; fp++) {
		(*fp)();
	}
}
