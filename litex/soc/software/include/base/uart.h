#ifndef __UART_H
#define __UART_H

#ifdef __cplusplus
extern "C" {
#endif

#define UART_EV_TX	0x1
#define UART_EV_RX	0x2

void uart_init(void);
void uart_isr(void);
void uart_sync(void);

void uart_write(char c);
char uart_read(void);
int uart_read_nonblock(void);

#ifdef __cplusplus
}
#endif

#endif
