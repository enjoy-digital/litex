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

char sl[HIST_DEPTH][CMD_LINE_BUFFER_SIZE];
int sl_idx = 0;

char out[CMD_LINE_BUFFER_SIZE];

static void string_list_init(void)
{
	int i;
	for (i = 0; i < HIST_DEPTH; i++)
		sl[i][0] = 0;
}

static int string_list_add(const char *string)
{
	int i;
	for (i = 0; i < HIST_DEPTH; i++) {
		if (sl[i][0] == 0) {
			strncpy(&sl[i][0], string, CMD_LINE_BUFFER_SIZE);
			return 0;
		}
	}
	return -1;
}

static int string_list_empty(void)
{
	int i;
	for (i = 0; i < HIST_DEPTH; i++)
		if (sl[i][0] != 0)
			return 0;
	return 1;
}

static int string_list_count(void)
{
	int i, count = 0;
	for (i = 0; i < HIST_DEPTH; i++)
		if (sl[i][0] != 0)
			count++;
	return count;
}

static char *list_first_entry(void)
{
	int i;
	for (i = 0; i < HIST_DEPTH; i++)
		if (sl[i][0] != 0)
			return &sl[i][0];
	return NULL;
}

static void string_list_print_by_column(void)
{
	int len = 0, num, i, j;

	for (i = 0; i < HIST_DEPTH; i++) {
		if (sl[i][0] != 0) {
			int l = strlen(&sl[i][0]) + 4;
			if (l > len)
				len = l;
		}
	}

	if (!len)
		return;

	num = 80 / (len + 1);

	for (j = 0; j < HIST_DEPTH; j++) {
		if (sl[j][0] != 0) {
			if (!(++i % num))
				printf("%s\n", &sl[j][0]);
			else
				printf("%-*s", len, &sl[j][0]);
		}
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
	char *first_entry;
	char *entry;
	int i;

	string_list_init();
	command_complete(instr);

	pos = strlen(instr);

	*outstr = "";
	if (string_list_empty())
		reprint = 0;
	else
	{
		out[0] = 0;

		first_entry = list_first_entry();

		while (1) {
			entry = first_entry;
			ch = entry[pos];
			if (!ch)
				break;

			changed = 0;
			for (i = 0; i < HIST_DEPTH; i++) {
				if (sl[i][0] != 0) {
					if (!sl[i][pos])
						break;
					if (ch != sl[i][pos]) {
						changed = 1;
						break;
					}
				}
			}

			if (changed)
				break;
			out[outpos++] = ch;
			pos++;
		}

		if ((string_list_count() != 1) && !outpos && tab_pressed) {
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
