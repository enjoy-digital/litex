/*
 * MiSoC
 * Copyright (C) 2007, 2008, 2009, 2010 Sebastien Bourdeauducq
 * Copyright (C) Linus Torvalds and Linux kernel developers
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

#ifndef __STRING_H
#define __STRING_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

char *strchr(const char *s, int c);
char *strpbrk(const char *,const char *);
char *strrchr(const char *s, int c);
char *strnchr(const char *s, size_t count, int c);
char *strcpy(char *dest, const char *src);
char *strncpy(char *dest, const char *src, size_t count);
int strcmp(const char *cs, const char *ct);
int strncmp(const char *cs, const char *ct, size_t count);
char *strcat(char *dest, const char *src);
char *strncat(char *dest, const char *src, size_t n);
size_t strlen(const char *s);
size_t strnlen(const char *s, size_t count);
size_t strspn(const char *s, const char *accept);
int memcmp(const void *cs, const void *ct, size_t count);
void *memset(void *s, int c, size_t count);
void *memcpy(void *to, const void *from, size_t n);
void *memmove(void *dest, const void *src, size_t count);
char *strstr(const char *s1, const char *s2);
void *memchr(const void *s, int c, size_t n);

char *strerror(int errnum);

#ifdef __cplusplus
}
#endif

#endif /* __STRING_H */
