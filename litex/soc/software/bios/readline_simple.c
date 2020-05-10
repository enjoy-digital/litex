// This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
// This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>

// SPDX-License-Identifier: BSD-Source-Code

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <ctype.h>

#include <console.h>
#include <uart.h>

#include "readline.h"

int readline(char *s, int size)
{
	static char skip = 0;
	char c[2];
	int ptr;

	c[1] = 0;
	ptr = 0;
	while(1) {
		c[0] = readchar();
		if (c[0] == skip)
			continue;
		skip = 0;
		switch(c[0]) {
			case 0x7f:
			case 0x08:
				if(ptr > 0) {
					ptr--;
					putsnonl("\x08 \x08");
				}
				break;
			case 0x07:
				break;
			case '\r':
				skip = '\n';
				s[ptr] = 0x00;
				putsnonl("\n");
				return 0;
			case '\n':
				skip = '\r';
				s[ptr] = 0x00;
				putsnonl("\n");
				return 0;
			default:
				putsnonl(c);
				s[ptr] = c[0];
				ptr++;
				break;
		}
	}

	return 0;
}

