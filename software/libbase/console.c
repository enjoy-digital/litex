/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009 Sebastien Bourdeauducq
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

#include <uart.h>
#include <console.h>
#include <stdio.h>
#include <stdarg.h>
#include <irq.h>
#include <hw/interrupts.h>

static console_write_hook write_hook;
static console_read_hook read_hook;
static console_read_nonblock_hook read_nonblock_hook;

void console_set_write_hook(console_write_hook h)
{
	write_hook = h;
}

void console_set_read_hook(console_read_hook r, console_read_nonblock_hook rn)
{
	read_hook = r;
	read_nonblock_hook = rn;
}

static void writechar(char c)
{
	uart_write(c);
	if(write_hook != NULL)
		write_hook(c);
}

char readchar(void)
{
	while(1) {
		if(uart_read_nonblock())
			return uart_read();
		if((read_nonblock_hook != NULL) && read_nonblock_hook())
			return read_hook();
	}
}

int readchar_nonblock(void)
{
	return (uart_read_nonblock()
		|| ((read_nonblock_hook != NULL) && read_nonblock_hook()));
}

int puts(const char *s)
{
	unsigned int oldmask;

	oldmask = irq_getmask();
	irq_setmask(IRQ_UART); // HACK: prevent UART data loss

	while(*s) {
		writechar(*s);
		s++;
	}
	writechar('\n');
	
	irq_setmask(oldmask);
	return 1;
}

void putsnonl(const char *s)
{
	unsigned int oldmask;

	oldmask = irq_getmask();
	irq_setmask(IRQ_UART); // HACK: prevent UART data loss
	
	while(*s) {
		writechar(*s);
		s++;
	}
	
	irq_setmask(oldmask);
}

int printf(const char *fmt, ...)
{
	va_list args;
	int len;
	char outbuf[256];

	va_start(args, fmt);
	len = vscnprintf(outbuf, sizeof(outbuf), fmt, args);
	va_end(args);
	outbuf[len] = 0;
	putsnonl(outbuf);

	return len;
}
