/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009 Sebastien Bourdeauducq
 * Copyright (C) Linux kernel developers
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <ctype.h>

#define fabsf(x) ((x) > 0.0 ? x : -x)

/**
 * vsnprintf - Format a string and place it in a buffer
 * @buf: The buffer to place the result into
 * @size: The size of the buffer, including the trailing null space
 * @fmt: The format string to use
 * @args: Arguments for the format string
 *
 * The return value is the number of characters which would
 * be generated for the given input, excluding the trailing
 * '\0', as per ISO C99. If you want to have the exact
 * number of characters written into @buf as return value
 * (not including the trailing '\0'), use vscnprintf(). If the
 * return is greater than or equal to @size, the resulting
 * string is truncated.
 *
 * Call this function if you are already dealing with a va_list.
 * You probably want snprintf() instead.
 */
int vsnprintf(char *buf, size_t size, const char *fmt, va_list args)
{
	int len;
	unsigned long long num;
	int i, base;
	char *str, *end, c;
	const char *s;

	int flags;		/* flags to number() */

	int field_width;	/* width of output field */
	int precision;		/* min. # of digits for integers; max
				   number of chars for from string */
	int qualifier;		/* 'h', 'l', or 'L' for integer fields */
				/* 'z' support added 23/7/1999 S.H.    */
				/* 'z' changed to 'Z' --davidm 1/25/99 */
				/* 't' added for ptrdiff_t */

	/* Reject out-of-range values early.  Large positive sizes are
	   used for unknown buffer sizes. */
	if (unlikely((int) size < 0))
		return 0;

	str = buf;
	end = buf + size;

	/* Make sure end is always >= buf */
	if (end < buf) {
		end = ((void *)-1);
		size = end - buf;
	}

	for (; *fmt ; ++fmt) {
		if (*fmt != '%') {
			if (str < end)
				*str = *fmt;
			++str;
			continue;
		}

		/* process flags */
		flags = 0;
		repeat:
			++fmt;		/* this also skips first '%' */
			switch (*fmt) {
				case '-': flags |= PRINTF_LEFT; goto repeat;
				case '+': flags |= PRINTF_PLUS; goto repeat;
				case ' ': flags |= PRINTF_SPACE; goto repeat;
				case '#': flags |= PRINTF_SPECIAL; goto repeat;
				case '0': flags |= PRINTF_ZEROPAD; goto repeat;
			}

		/* get field width */
		field_width = -1;
		if (isdigit(*fmt))
			field_width = skip_atoi(&fmt);
		else if (*fmt == '*') {
			++fmt;
			/* it's the next argument */
			field_width = va_arg(args, int);
			if (field_width < 0) {
				field_width = -field_width;
				flags |= PRINTF_LEFT;
			}
		}

		/* get the precision */
		precision = -1;
		if (*fmt == '.') {
			++fmt;	
			if (isdigit(*fmt))
				precision = skip_atoi(&fmt);
			else if (*fmt == '*') {
				++fmt;
				/* it's the next argument */
				precision = va_arg(args, int);
			}
			if (precision < 0)
				precision = 0;
		}

		/* get the conversion qualifier */
		qualifier = -1;
		if (*fmt == 'h' || *fmt == 'l' || *fmt == 'L' ||
		    *fmt =='Z' || *fmt == 'z' || *fmt == 't') {
			qualifier = *fmt;
			++fmt;
			if (qualifier == 'l' && *fmt == 'l') {
				qualifier = 'L';
				++fmt;
			}
		}

		/* default base */
		base = 10;

		switch (*fmt) {
			case 'c':
				if (!(flags & PRINTF_LEFT)) {
					while (--field_width > 0) {
						if (str < end)
							*str = ' ';
						++str;
					}
				}
				c = (unsigned char) va_arg(args, int);
				if (str < end)
					*str = c;
				++str;
				while (--field_width > 0) {
					if (str < end)
						*str = ' ';
					++str;
				}
				continue;

			case 's':
				s = va_arg(args, char *);
				if (s == NULL)
					s = "<NULL>";

				len = strnlen(s, precision);

				if (!(flags & PRINTF_LEFT)) {
					while (len < field_width--) {
						if (str < end)
							*str = ' ';
						++str;
					}
				}
				for (i = 0; i < len; ++i) {
					if (str < end)
						*str = *s;
					++str; ++s;
				}
				while (len < field_width--) {
					if (str < end)
						*str = ' ';
					++str;
				}
				continue;

			case 'p':
				if (field_width == -1) {
					field_width = 2*sizeof(void *);
					flags |= PRINTF_ZEROPAD;
				}
				str = number(str, end,
						(unsigned long) va_arg(args, void *),
						16, field_width, precision, flags);
				continue;

			case 'f': {
				int m;
				float f;
				int integer;
				
				/* until I sort out how to disable this stupid promotion to double ... */
				f = *(va_arg(args, float *));
				if((f <= 0.0f) && (f != 0.0f)) { /* TODO: fix that |[#{'"é! '<' operator */
					*str = '-';
					str++;
					f = -f;
				}

				integer = f;
				if(integer > 0) {
					m = 1;
					while(integer > (m*10)) m *= 10;
					while((m >= 1) && (str < end)) {
						int n;
						n = integer/m;
						*str = '0' + n;
						str++;
						f = f - m*n;
						integer = integer - m*n;
						m /= 10;
					}
				} else if(str < end) {
					*str = '0';
					str++;
				}

				if(str < end) {
					*str = '.';
					str++;
				}

				for(i=0;i<6;i++) {
					int n;

					f = f*10.0f;
					n = f;
					f = f - n;
					if(str >= end) break;
					*str = '0' + n;
					str++;
				}
				
				continue;
			}

			case 'n':
				/* FIXME:
				 * What does C99 say about the overflow case here? */
				if (qualifier == 'l') {
					long * ip = va_arg(args, long *);
					*ip = (str - buf);
				} else if (qualifier == 'Z' || qualifier == 'z') {
					size_t * ip = va_arg(args, size_t *);
					*ip = (str - buf);
				} else {
					int * ip = va_arg(args, int *);
					*ip = (str - buf);
				}
				continue;

			case '%':
				if (str < end)
					*str = '%';
				++str;
				continue;

				/* integer number formats - set up the flags and "break" */
			case 'o':
				base = 8;
				break;

			case 'X':
				flags |= PRINTF_LARGE;
			case 'x':
				base = 16;
				break;

			case 'd':
			case 'i':
				flags |= PRINTF_SIGN;
			case 'u':
				break;

			default:
				if (str < end)
					*str = '%';
				++str;
				if (*fmt) {
					if (str < end)
						*str = *fmt;
					++str;
				} else {
					--fmt;
				}
				continue;
		}
		if (qualifier == 'L')
			num = va_arg(args, long long);
		else if (qualifier == 'l') {
			num = va_arg(args, unsigned long);
			if (flags & PRINTF_SIGN)
				num = (signed long) num;
		} else if (qualifier == 'Z' || qualifier == 'z') {
			num = va_arg(args, size_t);
		} else if (qualifier == 't') {
			num = va_arg(args, ptrdiff_t);
		} else if (qualifier == 'h') {
			num = (unsigned short) va_arg(args, int);
			if (flags & PRINTF_SIGN)
				num = (signed short) num;
		} else {
			num = va_arg(args, unsigned int);
			if (flags & PRINTF_SIGN)
				num = (signed int) num;
		}
		str = number(str, end, num, base,
				field_width, precision, flags);
	}
	if (size > 0) {
		if (str < end)
			*str = '\0';
		else
			end[-1] = '\0';
	}
	/* the trailing null byte doesn't count towards the total */
	return str-buf;
}
