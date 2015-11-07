#include <uart.h>
#include <console.h>
#include <stdio.h>
#include <stdarg.h>

FILE *stdin, *stdout, *stderr;

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

int putchar(int c)
{
	uart_write(c);
	if(write_hook != NULL)
		write_hook(c);
	return c;
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
	while(*s) {
		putchar(*s);
		s++;
	}
	putchar('\n');
	return 1;
}

void putsnonl(const char *s)
{
	while(*s) {
		putchar(*s);
		s++;
	}
}

#define PRINTF_BUFFER_SIZE 256

int printf(const char *fmt, ...)
{
	va_list args;
	int len;
	char outbuf[PRINTF_BUFFER_SIZE];

	va_start(args, fmt);
	len = vscnprintf(outbuf, sizeof(outbuf), fmt, args);
	va_end(args);
	outbuf[len] = 0;
	putsnonl(outbuf);

	return len;
}
