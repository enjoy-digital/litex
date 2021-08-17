/* Most of the code here is ported from console.c
 * with slightly changed function signatures and 
 * names. Picolibc requires providing __iob array
 * which contains stdin, stdout and stderr files.
 * To simpify things, we can create one file
 * which can be both read from and written to,
 * and assign it to all three of them.
 *
 * It does mean, that in future it is possible to
 * provide stderr for example which could be non-
 * blocking for example.
 *
 * For more information on __iob and how to create
 * it look into picolibc/doc/os.md.
 */

#include <stdio.h>

#include <libutils/console.h>
#include <libcomm/uart.h>

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
static int
dummy_putc(char c, FILE *file)
{
	(void) file;
	uart_write(c);
	if(write_hook != NULL)
		write_hook(c);
	if (c == '\n')
		dummy_putc('\r', NULL);
	return c;
}

static int
dummy_getc(FILE *file)
{
	(void) file;
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

static int
dummy_putc(char c, FILE *file)
{
	(void) file;
	if(write_hook != NULL)
		write_hook(c);
	return c;
}

static int
dummy_getc(FILE *file)
{
	(void) file;
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

static FILE __stdio = FDEV_SETUP_STREAM(dummy_putc, dummy_getc, NULL, _FDEV_SETUP_RW);

FILE *const __iob[3] = { &__stdio, &__stdio, &__stdio };

