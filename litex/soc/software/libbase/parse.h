// SPDX-License-Identifier: BSD-2-Clause

#ifndef __LIBBASE_PARSE_H
#define __LIBBASE_PARSE_H

/* Parse a complete unsigned integer, using the same decimal/octal/hexadecimal
 * prefixes as strtoul(..., 0). Reject signs, whitespace and overflow; leave the
 * destination unchanged on failure. */
int parse_ulong(const char *text, unsigned long *value);
int parse_uint(const char *text, unsigned int *value);

#endif
