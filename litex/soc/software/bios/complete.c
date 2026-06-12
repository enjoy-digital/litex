// This file is Copyright (c) 2020 Franck Jullien <franck.jullien@gmail.com>
//
//     Largely inspired/copied from U-boot and Barebox projects wich are:
//         Sascha Hauer, Pengutronix, <s.hauer@pengutronix.de>

// License: BSD

#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "readline.h"
#include "helpers.h"
#include "command.h"
#include "complete.h"

static int tab_pressed = 0;

static int command_match(const char *instr, const char *name)
{
	return !strncmp(instr, name, strlen(instr));
}

static int command_complete_suffix(char *instr, char *outstr, int outlen)
{
	struct command_struct * const *cmd;
	const char *name;
	int pos = strlen(instr);
	int outpos = 0;
	int count = 0;

	outstr[0] = 0;
	for (cmd = __bios_cmd_start; cmd != __bios_cmd_end; cmd++) {
		name = (*cmd)->name;
		if (!command_match(instr, name))
			continue;
		count++;
		if (count == 1) {
			while ((outpos < outlen - 1) && name[pos + outpos]) {
				outstr[outpos] = name[pos + outpos];
				outpos++;
			}
			outstr[outpos] = 0;
		} else {
			int common = 0;
			while ((common < outpos) && name[pos + common] &&
			       (outstr[common] == name[pos + common]))
				common++;
			outpos = common;
			outstr[outpos] = 0;
		}
	}

	return count;
}

static void command_matches_print_by_column(char *instr)
{
	struct command_struct * const *cmd;
	int len = 0, num, i = 0;

	for (cmd = __bios_cmd_start; cmd != __bios_cmd_end; cmd++) {
		const char *name = (*cmd)->name;
		if (command_match(instr, name)) {
			int l = strlen(name) + 4;
			if (l > len)
				len = l;
		}
	}

	if (!len)
		return;

	num = 80 / (len + 1);
	if (num == 0)
		num = 1;

	for (cmd = __bios_cmd_start; cmd != __bios_cmd_end; cmd++) {
		const char *name = (*cmd)->name;
		if (command_match(instr, name)) {
			if (!(++i % num))
				printf("%s\n", name);
			else
				printf("%-*s", len, name);
		}
	}
	if (i % num)
		printf("\n");
}

int complete(char *instr, char *outstr, int outlen)
{
	int reprint = 0;
	int count;

	if (outlen <= 0)
		return 0;

	outstr[0] = 0;
	count = command_complete_suffix(instr, outstr, outlen);
	if (count == 0)
		reprint = 0;
	else
	{
		if ((count != 1) && !outstr[0] && tab_pressed) {
			printf("\n");
			command_matches_print_by_column(instr);
			reprint = 1;
			tab_pressed = 0;
		}

		if (outstr[0] == 0)
			tab_pressed = 1;
		else
			tab_pressed = 0;
	}

	return reprint;
}
