#include <uart.h>
#include <console.h>
#include <stdio.h>
#include <stdarg.h>

#include <generated/csr.h>

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

#ifdef CSR_UART_BASE
int putchar(int c)
{
	uart_write(c);
	if(write_hook != NULL)
		write_hook(c);
	if (c == '\n')
		putchar('\r');
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

int putchar(int c)
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

int puts(const char *s)
{
	putsnonl(s);
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

int skip_atoi(const char **s)
{
	int i=0;

	while (isdigit(**s))
		i = i*10 + *((*s)++) - '0';
	return i;
}

char *number(char *buf, char *end, unsigned long num, int base, int size, int precision, int type)
{
	char c,sign,tmp[66];
	const char *digits;
	static const char small_digits[] = "0123456789abcdefghijklmnopqrstuvwxyz";
	static const char large_digits[] = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
	int i;

	digits = (type & PRINTF_LARGE) ? large_digits : small_digits;
	if (type & PRINTF_LEFT)
		type &= ~PRINTF_ZEROPAD;
	if (base < 2 || base > 36)
		return NULL;
	c = (type & PRINTF_ZEROPAD) ? '0' : ' ';
	sign = 0;
	if (type & PRINTF_SIGN) {
		if ((signed long) num < 0) {
			sign = '-';
			num = - (signed long) num;
			size--;
		} else if (type & PRINTF_PLUS) {
			sign = '+';
			size--;
		} else if (type & PRINTF_SPACE) {
			sign = ' ';
			size--;
		}
	}
	if (type & PRINTF_SPECIAL) {
		if (base == 16)
			size -= 2;
		else if (base == 8)
			size--;
	}
	i = 0;
	if (num == 0)
		tmp[i++]='0';
	else while (num != 0) {
		tmp[i++] = digits[num % base];
		num = num / base;
	}
	if (i > precision)
		precision = i;
	size -= precision;
	if (!(type&(PRINTF_ZEROPAD+PRINTF_LEFT))) {
		while(size-->0) {
			if (buf < end)
				*buf = ' ';
			++buf;
		}
	}
	if (sign) {
		if (buf < end)
			*buf = sign;
		++buf;
	}
	if (type & PRINTF_SPECIAL) {
		if (base==8) {
			if (buf < end)
				*buf = '0';
			++buf;
		} else if (base==16) {
			if (buf < end)
				*buf = '0';
			++buf;
			if (buf < end)
				*buf = digits[33];
			++buf;
		}
	}
	if (!(type & PRINTF_LEFT)) {
		while (size-- > 0) {
			if (buf < end)
				*buf = c;
			++buf;
		}
	}
	while (i < precision--) {
		if (buf < end)
			*buf = '0';
		++buf;
	}
	while (i-- > 0) {
		if (buf < end)
			*buf = tmp[i];
		++buf;
	}
	while (size-- > 0) {
		if (buf < end)
			*buf = ' ';
		++buf;
	}
	return buf;
}

/**
 * vscnprintf - Format a string and place it in a buffer
 * @buf: The buffer to place the result into
 * @size: The size of the buffer, including the trailing null space
 * @fmt: The format string to use
 * @args: Arguments for the format string
 *
 * The return value is the number of characters which have been written into
 * the @buf not including the trailing '\0'. If @size is <= 0 the function
 * returns 0.
 *
 * Call this function if you are already dealing with a va_list.
 * You probably want scnprintf() instead.
 */
int vscnprintf(char *buf, size_t size, const char *fmt, va_list args)
{
        size_t i;

	i=vsnprintf(buf,size,fmt,args);
	return (i >= size) ? (size - 1) : i;
}

#define PRINTF_BUFFER_SIZE 256

int vprintf(const char *fmt, va_list args)
{
	int len;
	char outbuf[PRINTF_BUFFER_SIZE];
	len = vscnprintf(outbuf, sizeof(outbuf), fmt, args);
	outbuf[len] = 0;
	putsnonl(outbuf);
	return len;
}

int printf(const char *fmt, ...)
{
	int len;
	va_list args;
	va_start(args, fmt);
	len = vprintf(fmt, args);
	va_end(args);
	return len;
}
