#ifndef __UART_H
#define __UART_H

#ifdef __cplusplus
extern "C" {
#endif

#include <generated/csr.h>

#ifdef CSR_UART0_BASE
#define CSR_UART_BASE           CSR_UART0_BASE
#define UART_INTERRUPT          UART0_INTERRUPT
#define uart_txfull_read        uart0_txfull_read
#define uart_rxtx_read        	uart0_rxtx_read
#define uart_rxtx_write       	uart0_rxtx_write
#define uart_ev_enable_write  	uart0_ev_enable_write
#define uart_rxempty_read     	uart0_rxempty_read
#define uart_rxempty_write    	uart0_rxempty_write
#define uart_ev_pending_read  	uart0_ev_pending_read
#define uart_ev_pending_write 	uart0_ev_pending_write
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
