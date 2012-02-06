#include <hw/uart.h>

static void print(const char *s)
{
	while(*s) {
		while(CSR_UART_EV_STAT & UART_EV_TX);
		CSR_UART_RXTX = *s;
		s++;
	}
}

int main(void)
{
	print("Hello World\n");
	while(1);
}
