/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009, 2011 Sebastien Bourdeauducq
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

#ifndef __STDLIB_H
#define __STDLIB_H

#include <stddef.h>

#define PRINTF_ZEROPAD	1		/* pad with zero */
#define PRINTF_SIGN	2		/* unsigned/signed long */
#define PRINTF_PLUS	4		/* show plus */
#define PRINTF_SPACE	8		/* space if plus */
#define PRINTF_LEFT	16		/* left justified */
#define PRINTF_SPECIAL	32		/* 0x */
#define PRINTF_LARGE	64		/* use 'ABCDEF' instead of 'abcdef' */

#define likely(x) x
#define unlikely(x) x

#define abs(x) ((x) > 0 ? (x) : -(x))

unsigned long strtoul(const char *nptr, char **endptr, int base);
int skip_atoi(const char **s);
static inline int atoi(const char *nptr) {
	return strtoul(nptr, NULL, 0);
}
static inline long atol(const char *nptr) {
	return (long)atoi(nptr);
}
char *number(char *buf, char *end, unsigned long num, int base, int size, int precision, int type);
long strtol(const char *nptr, char **endptr, int base);
double strtod(const char *str, char **endptr);

#define   RAND_MAX        2147483647

unsigned int rand(void);
void srand(unsigned int seed);
void abort(void);

/*
 * The following functions are not provided by this library.
 */

char *getenv(const char *name);

void *malloc(size_t size);
void free(void *ptr);
void *realloc(void *ptr, size_t size);

#endif /* __STDLIB_H */
