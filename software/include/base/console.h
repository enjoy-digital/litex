/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009, 2010 Sebastien Bourdeauducq
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

#ifndef __CONSOLE_H
#define __CONSOLE_H

typedef void (*console_write_hook)(char);
typedef char (*console_read_hook)(void);
typedef int (*console_read_nonblock_hook)(void);

void console_set_write_hook(console_write_hook h);
void console_set_read_hook(console_read_hook r, console_read_nonblock_hook rn);

char readchar(void);
int readchar_nonblock(void);

int puts(const char *s);
void putsnonl(const char *s);

#endif /* __CONSOLE_H */
