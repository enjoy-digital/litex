#ifndef __UART_H
#define __UART_H

void uart_init(void);
void uart_isr(void);
void uart_sync(void);

void uart_write(char c);
char uart_read(void);
int uart_read_nonblock(void);

#endif
