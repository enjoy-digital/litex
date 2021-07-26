#include <base/console.h>
#include <stdio.h>
//#include <sys/cdefs.h>


static int
dummy_putc(char c, FILE *file)
{
	(void) file;
	return base_putchar(c);
}

static int
dummy_getc(FILE *file)
{
	(void) file;
	return readchar();
}

static int
dummy_flush(FILE *file)
{
	(void) file;
	return 0;
}

static FILE __stdio = FDEV_SETUP_STREAM(dummy_putc, dummy_getc, dummy_flush, _FDEV_SETUP_RW);

FILE *const __iob[3] = { &__stdio, &__stdio, &__stdio };

