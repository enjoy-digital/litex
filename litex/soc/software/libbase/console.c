#include <base/uart.h>
#include <base/console.h>
#include <stdio.h>
#include <stdarg.h>

#include <generated/csr.h>

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

#ifdef CSR_UART_BASE
int base_putchar(int c)
{
	uart_write(c);
	if(write_hook != NULL)
		write_hook(c);
	if (c == '\n')
		base_putchar('\r');
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

#else

int base_putchar(int c)
{
	if(write_hook != NULL)
		write_hook(c);
	return c;
}

char readchar(void)
{
	while(1) {
		if((read_nonblock_hook != NULL) && read_nonblock_hook())
			return read_hook();
	}
}

int readchar_nonblock(void)
{
	return ((read_nonblock_hook != NULL) && read_nonblock_hook());
}

#endif

