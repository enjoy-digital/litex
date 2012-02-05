#include <hw/uart.h>

static void print(const char *s)
{
	while(*s) {
		while(!(CSR_UART_STAT & UART_STAT_THRE));
		CSR_UART_RXTX = *s;
		s++;
	}
}

int main(void)
{
	print("Hello World\n");
	while(1);
}
