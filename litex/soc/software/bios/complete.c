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

/* Maximum number of completion candidates: must cover all registered
   commands so that the common prefix is computed over the full match set. */
#define COMPLETE_MAX_MATCHES 128

static int tab_pressed = 0;

/* Candidates are pointers to the (static) command names, no copies needed. */
static const char *sl[COMPLETE_MAX_MATCHES];
static int sl_count = 0;

char out[CMD_LINE_BUFFER_SIZE];

static void string_list_init(void)
{
	sl_count = 0;
}

static int string_list_add(const char *string)
{
	if (sl_count >= COMPLETE_MAX_MATCHES)
		return -1;
	sl[sl_count++] = string;
	return 0;
}

static void string_list_print_by_column(void)
{
	int len = 0, num, i, j;

	for (i = 0; i < sl_count; i++) {
		int l = strlen(sl[i]) + 4;
		if (l > len)
			len = l;
	}

	if (!len)
		return;

	num = 80 / (len + 1);
	if (num == 0)
		num = 1;

	i = 0;
	for (j = 0; j < sl_count; j++) {
		if (!(++i % num))
			printf("%s\n", sl[j]);
		else
			printf("%-*s", len, sl[j]);
	}
	if (i % num)
		printf("\n");
}

static void command_complete(char *instr)
{
	struct command_struct * const *cmd;

	for (cmd = __bios_cmd_start; cmd != __bios_cmd_end; cmd++)
		if (!strncmp(instr, (*cmd)->name, strlen(instr)))
			string_list_add((*cmd)->name);
}

int complete(char *instr, char **outstr)
{
	int pos;
	char ch;
	int changed;
	int outpos = 0;
	int reprint = 0;
	const char *first_entry;
	const char *entry;
	int i;

	string_list_init();
	command_complete(instr);

	pos = strlen(instr);

	*outstr = "";
	if (sl_count == 0)
		reprint = 0;
	else
	{
		out[0] = 0;

		first_entry = sl[0];

		while (outpos < CMD_LINE_BUFFER_SIZE - 1) {
			entry = first_entry;
			ch = entry[pos];
			if (!ch)
				break;

			changed = 0;
			for (i = 0; i < sl_count; i++) {
				if ((!sl[i][pos]) || (ch != sl[i][pos])) {
					changed = 1;
					break;
				}
			}

			if (changed)
				break;
			out[outpos++] = ch;
			pos++;
		}

		if ((sl_count != 1) && !outpos && tab_pressed) {
			printf("\n");
			string_list_print_by_column();
			reprint = 1;
			tab_pressed = 0;
		}

		out[outpos++] = 0;
		*outstr = out;

		if (*out == 0)
			tab_pressed = 1;
		else
			tab_pressed = 0;
	}

	return reprint;
}
