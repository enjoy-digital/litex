#ifndef __SYSTEM_H
#define __SYSTEM_H

#ifdef __cplusplus
extern "C" {
#endif

#include "xuartps_hw.h"
#include "xil_cache.h"

__attribute__((unused)) static void flush_cpu_icache(void){};

__attribute__((unused)) static void flush_cpu_dcache(void) {
    Xil_DCacheFlush();
};

void flush_l2_cache(void); // TODO: use Xil_L2CacheFlush(); !

void busy_wait(unsigned int ms);
void busy_wait_us(unsigned int us);

#define CSR_UART_BASE
#define UART_POLLING

static inline void uart_rxtx_write(char c) {
    XUartPs_WriteReg(STDOUT_BASEADDRESS, XUARTPS_FIFO_OFFSET, (uint32_t) c);
}

static inline uint8_t uart_rxtx_read(void) {
    return XUartPs_ReadReg(STDOUT_BASEADDRESS, XUARTPS_FIFO_OFFSET);
}

static inline uint8_t uart_txfull_read(void) {
    return XUartPs_IsTransmitFull(STDOUT_BASEADDRESS);
}

static inline uint8_t uart_rxempty_read(void) {
    return !XUartPs_IsReceiveData(STDOUT_BASEADDRESS);
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
