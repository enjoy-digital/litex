// SPDX-License-Identifier: BSD-2-Clause

#include <limits.h>
#include "parse.h"

int parse_ulong(const char *text, unsigned long *value)
{
	unsigned long result = 0;
	unsigned int base = 10;
	unsigned int digits = 0;

	if (text[0] == '0') {
		base = 8;
		if (text[1] == 'x' || text[1] == 'X') {
			base = 16;
			text += 2;
		}
	}
	while (*text) {
		unsigned int digit;
		char c = *text++;

		if (c >= '0' && c <= '9')
			digit = c - '0';
		else if (c >= 'a' && c <= 'f')
			digit = c - 'a' + 10;
		else if (c >= 'A' && c <= 'F')
			digit = c - 'A' + 10;
		else
			return 0;
		if (digit >= base || result > (ULONG_MAX - digit) / base)
			return 0;
		result = result * base + digit;
		digits++;
	}
	if (!digits)
		return 0;
	*value = result;
	return 1;
}

int parse_uint(const char *text, unsigned int *value)
{
	unsigned long result;

	if (!parse_ulong(text, &result) || result > UINT_MAX)
		return 0;
	*value = result;
	return 1;
}
