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

#ifndef __STDARG_H
#define __STDARG_H

#include <stdlib.h>

#if (__GNUC__ > 4) || ((__GNUC__ == 4) && (__GNUC_MINOR__ >= 4))
#define va_start(v,l) __builtin_va_start((v),l)
#else
#define va_start(v,l) __builtin_stdarg_start((v),l)
#endif

#define va_arg(ap, type) \
	__builtin_va_arg((ap), type)

#define va_end(ap) \
	__builtin_va_end(ap)

#define va_list \
	__builtin_va_list

int vsnprintf(char *buf, size_t size, const char *fmt, va_list args);
int vscnprintf(char *buf, size_t size, const char *fmt, va_list args);
int vsprintf(char *buf, const char *fmt, va_list args);

#endif /* __STDARG_H */
