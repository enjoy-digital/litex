// This file is Copyright (c) 2020 Franck Jullien <franck.jullien@gmail.com>
//
//     Largely inspired/copied from U-boot and Barebox projects wich are:
//         Wolfgang Denk, DENX Software Engineering, <wd@denx.de>
//         Sascha Hauer, Pengutronix, <s.hauer@pengutronix.de>
//     cmdline-editing related codes from vivi
//         Author: Janghoon Lyu <nandy@mizi.com>

// SPDX-License-Identifier: BSD-Source-Code

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <ctype.h>

#include "readline.h"
#include "complete.h"

#ifndef BIOS_CONSOLE_NO_HISTORY
static int hist_max = 0;
static int hist_add_idx = 0;
static int hist_cur = 0;
static int hist_num = 0;
static char hist_lines[HIST_MAX][CMD_LINE_BUFFER_SIZE];
#endif

#define ARRAY_SIZE(array)  (sizeof(array) / sizeof(array[0]))

static const struct esc_cmds esccmds[] = {
	{"OA", KEY_UP},       // cursor key Up
	{"OB", KEY_DOWN},     // cursor key Down
	{"OC", KEY_RIGHT},    // Cursor Key Right
	{"OD", KEY_LEFT},     // cursor key Left
	{"OH", KEY_HOME},     // Cursor Key Home
	{"OF", KEY_END},      // Cursor Key End
	{"[A", KEY_UP},       // cursor key Up
	{"[B", KEY_DOWN},     // cursor key Down
	{"[C", KEY_RIGHT},    // Cursor Key Right
	{"[D", KEY_LEFT},     // cursor key Left
	{"[H", KEY_HOME},     // Cursor Key Home
	{"[F", KEY_END},      // Cursor Key End
	{"[1~", KEY_HOME},    // Cursor Key Home
	{"[2~", KEY_INSERT},  // Cursor Key Insert
	{"[3~", KEY_DEL},     // Cursor Key Delete
	{"[4~", KEY_END},     // Cursor Key End
	{"[5~", KEY_PAGEUP},  // Cursor Key Page Up
	{"[6~", KEY_PAGEDOWN},// Cursor Key Page Down
};

static int read_key(void)
{
	char c;
	char esc[5];
	c = getchar();

	if (c == 27) {
		int i = 0;
		esc[i++] = getchar();
		esc[i++] = getchar();
		if (isdigit(esc[1])) {
			while(1) {
				esc[i] = getchar();
				if (esc[i++] == '~')
					break;
				if (i == ARRAY_SIZE(esc))
					return -1;
			}
		}
		esc[i] = 0;
		for (i = 0; i < ARRAY_SIZE(esccmds); i++){
			if (!strcmp(esc, esccmds[i].seq))
				return esccmds[i].val;
		}
		return -1;
	}
	return c;
}

#ifndef BIOS_CONSOLE_NO_HISTORY
static void cread_add_to_hist(char *line)
{
	strcpy(&hist_lines[hist_add_idx][0], line);

	if (++hist_add_idx >= HIST_MAX)
		hist_add_idx = 0;

	if (hist_add_idx > hist_max)
		hist_max = hist_add_idx;

	hist_num++;
}

static char* hist_prev(void)
{
	char *ret;
	int old_cur;

	if (hist_cur < 0)
		return NULL;

	old_cur = hist_cur;
	if (--hist_cur < 0)
		hist_cur = hist_max;

	if (hist_cur == hist_add_idx) {
		hist_cur = old_cur;
		ret = NULL;
	} else {
		ret = &hist_lines[hist_cur][0];
	}

	return ret;
}

static char* hist_next(void)
{
	char *ret;

	if (hist_cur < 0)
		return  NULL;

	if (hist_cur == hist_add_idx)
		return  NULL;

	if (++hist_cur > hist_max)
		hist_cur = 0;

	if (hist_cur == hist_add_idx)
		ret = "";
	else
		ret = &hist_lines[hist_cur][0];

	return ret;
}

void hist_init(void)
{
	int i;

	hist_max = 0;
	hist_add_idx = 0;
	hist_cur = -1;
	hist_num = 0;

	for (i = 0; i < HIST_MAX; i++)
		hist_lines[i][0] = '\0';
}
#endif

static void cread_add_char(char ichar, int insert, unsigned int *num,
			   unsigned int *eol_num, char *buf, unsigned int len)
{
	unsigned int wlen;

	if (insert || *num == *eol_num) {
		if (*eol_num > len - 1) {
			getcmd_cbeep();
			return;
		}
		(*eol_num)++;
	}

	if (insert) {
		wlen = *eol_num - *num;
		if (wlen > 1) {
			memmove(&buf[*num+1], &buf[*num], wlen-1);
		}

		buf[*num] = ichar;
		putnstr(buf + *num, wlen);
		(*num)++;
		while (--wlen) {
			getcmd_putch(CTL_BACKSPACE);
		}
	} else {
		/* echo the character */
		wlen = 1;
		buf[*num] = ichar;
		putnstr(buf + *num, wlen);
		(*num)++;
	}
}

int readline(char *buf, int len)
{
	unsigned int num = 0;
	unsigned int eol_num = 0;
	unsigned int wlen;
	int insert = 1;
	unsigned char ichar;

#ifndef BIOS_CONSOLE_NO_AUTOCOMPLETE
	char tmp;
	int reprint, i;
	char *completestr;
#endif

	while (1) {

		ichar = read_key();

		if ((ichar == '\n') || (ichar == '\r'))
			break;

		switch (ichar) {
		case '\t':
#ifndef BIOS_CONSOLE_NO_AUTOCOMPLETE
			buf[eol_num] = 0;
			tmp = buf[num];

			buf[num] = 0;
			reprint = complete(buf, &completestr);
			buf[num] = tmp;

			if (reprint) {
				printf("%s%s", PROMPT, buf);

				if (tmp)
					for (i = 0; i < eol_num - num; i++)
						getcmd_putch(CTL_BACKSPACE);
			}

			i = 0;
			while (completestr[i])
				cread_add_char(completestr[i++], insert, &num,
						&eol_num, buf, len);
#endif
			break;

		case KEY_HOME:
			BEGINNING_OF_LINE();
			break;
		case CTL_CH('c'):	/* ^C - break */
			*buf = 0;	/* discard input */
			return -1;
			break;
		case KEY_RIGHT:
			if (num < eol_num) {
				getcmd_putch(buf[num]);
				num++;
			}
			break;
		case KEY_LEFT:
			if (num) {
				getcmd_putch(CTL_BACKSPACE);
			 	num--;
			}
			break;
		case CTL_CH('d'):
			if (num < eol_num) {
				wlen = eol_num - num - 1;
				if (wlen) {
					memmove(&buf[num], &buf[num+1], wlen);
					putnstr(buf + num, wlen);
				}

				getcmd_putch(' ');
				do {
					getcmd_putch(CTL_BACKSPACE);
				} while (wlen--);
				eol_num--;
			}
			break;
		case KEY_ERASE_TO_EOL:
			ERASE_TO_EOL();
			break;
		case KEY_REFRESH_TO_EOL:
		case KEY_END:
			REFRESH_TO_EOL();
			break;
		case KEY_INSERT:
			insert = !insert;
			break;
		case KEY_ERASE_LINE:
			BEGINNING_OF_LINE();
			ERASE_TO_EOL();
			break;
		case DEL:
		case KEY_DEL7:
		case 8:
			if (num) {
				wlen = eol_num - num;
				num--;
				memmove(buf + num, buf + num + 1, wlen);
				getcmd_putch(CTL_BACKSPACE);
				putnstr(buf + num, wlen);
				getcmd_putch(' ');
				do {
					getcmd_putch(CTL_BACKSPACE);
				} while (wlen--);
				eol_num--;
			}
			break;
		case KEY_DEL:
			if (num < eol_num) {
				wlen = eol_num - num;
				memmove(buf + num, buf + num + 1, wlen);
				putnstr(buf + num, wlen - 1);
				getcmd_putch(' ');
				do {
					getcmd_putch(CTL_BACKSPACE);
				} while (--wlen);
				eol_num--;
			}
			break;
		case KEY_UP:
		case KEY_DOWN:
		{
#ifndef BIOS_CONSOLE_NO_HISTORY
			char * hline;
			if (ichar == KEY_UP)
			 	hline = hist_prev();
			else
			 	hline = hist_next();

			if (!hline) {
				getcmd_cbeep();
				break;
			}

			/* nuke the current line */
			/* first, go home */
			BEGINNING_OF_LINE();

			/* erase to end of line */
			ERASE_TO_EOL();

			/* copy new line into place and display */
			strcpy(buf, hline);
			eol_num = strlen(buf);
			REFRESH_TO_EOL();
#endif
			break;
		}

		default:
			if (isascii(ichar) && isprint(ichar))
				cread_add_char (ichar, insert, &num, &eol_num, buf, len);
			break;
		}
	}

	len = eol_num;
	buf[eol_num] = '\0';

#ifndef BIOS_CONSOLE_NO_HISTORY
	if (buf[0] && buf[0] != CREAD_HIST_CHAR) 
		cread_add_to_hist(buf);
	hist_cur = hist_add_idx;
#endif

	num = 0;
	eol_num = 0;

	return len;
}
