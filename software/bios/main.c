#include <stdio.h>
#include <irq.h>
#include <uart.h>

int main(void)
{
	char c;
	
	irq_setmask(0);
	irq_setie(1);
	uart_init();
	
	printf("Hello World with IRQs\n");
	
	while(1) {
		c = uart_read();
		printf("You typed: %c\n", c);
	}
}
