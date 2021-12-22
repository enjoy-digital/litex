/*
 * LiteX stdio support for Picolibc.
 *
 * More info: picolibc/doc/os.md
 */

#include <stdio.h>

#include <libbase/console.h>
#include <libbase/uart.h>

#include <generated/csr.h>

static int
litex_putc(char c, FILE *file)
{
	(void) file; /* Not used in this function */
#ifdef CSR_UART_BASE
	uart_write(c);
	if (c == '\n')
		litex_putc('\r', NULL);
#endif
	return c;
}

static int
litex_getc(FILE *file)
{
	(void) file; /* Not used in this function */
	while(1) {
#ifdef CSR_UART_BASE
		if(uart_read_nonblock())
			return uart_read();
#endif
	}
	return -1;
}

static FILE __stdio = FDEV_SETUP_STREAM(litex_putc, litex_getc, NULL, _FDEV_SETUP_RW);

FILE *const stdout = &__stdio;
FILE *const stderr = &__stdio;
FILE *const stdin  = &__stdio;
