#include <libbase/console.h>
#include <libbase/uart.h>

#include <generated/csr.h>

int readchar_nonblock(void)
{
#ifdef CSR_UART_BASE
	return uart_read_nonblock();
#else
	return 1;
#endif
}
