#ifndef __SYSTEM_H
#define __SYSTEM_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

__attribute__((unused)) static void flush_cpu_icache(void){};
__attribute__((unused)) static void flush_cpu_dcache(void){};
void flush_l2_cache(void);

void busy_wait(unsigned int ms);
void busy_wait_us(unsigned int us);

#define CSR_UART_BASE
#define UART_POLLING
#define UART_ID_HW 1 // hard UART on the S3
#define UART_ID UART_ID_HW

void uart_tx(int uartid, int c);
int uart_rx(int uartid);
int uart_rx_available(int uartid);
int uart_tx_is_fifo_full(int uart_id);

static inline void uart_rxtx_write(char c) {
    uart_tx(UART_ID, c);
}

static inline uint8_t uart_rxtx_read(void) {
    return uart_rx(UART_ID);
}

static inline uint8_t uart_txfull_read(void) {
    return uart_tx_is_fifo_full(UART_ID);
}

static inline uint8_t uart_rxempty_read(void) {
    return uart_rx_available(UART_ID);
}

static inline void uart_ev_pending_write(uint8_t x) {}

static inline uint8_t uart_ev_pending_read(void) {
    return 0;
}

static inline void uart_ev_enable_write(uint8_t x) {}


#ifdef __cplusplus
}
#endif

#endif /* __SYSTEM_H */
