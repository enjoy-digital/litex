#ifndef __SYSTEM_H
#define __SYSTEM_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

__attribute__((unused)) static void flush_cpu_icache(void){};

__attribute__((unused)) static void flush_cpu_dcache(void){};

void flush_l2_cache(void);

void busy_wait(unsigned int ms);
void busy_wait_us(unsigned int us);

#define CSR_UART_BASE
#define UART_POLLING

/* HPS UART0 (Synopsys DW 16550, configured by the Preloader/U-Boot). Base is family-dependent:
   Agilex 7 exposes HPS peripherals in the 0xFFxx_xxxx region, Agilex 5/3 (A55) in 0x10xx_xxxx. */
#if defined(__agilex7_hps__)
#define HPS_UART0_BASE 0xffc02000L
#elif defined(__agilex5_hps__) || defined(__agilex3_hps__)
#define HPS_UART0_BASE 0x10c02000L
#else
#error "Unknown Agilex HPS variant."
#endif

#define HPS_UART_RBR_THR_OFFSET 0x00
#define HPS_UART_LSR_OFFSET     0x14
#define HPS_UART_LSR_DR         (1 << 0)
#define HPS_UART_LSR_THRE       (1 << 5)

static inline uint32_t hps_uart_read(uint32_t offset) {
    return *(volatile uint32_t *)(HPS_UART0_BASE + offset);
}

static inline void hps_uart_write(uint32_t offset, uint32_t value) {
    *(volatile uint32_t *)(HPS_UART0_BASE + offset) = value;
}

static inline void uart_rxtx_write(char c) {
    hps_uart_write(HPS_UART_RBR_THR_OFFSET, (uint32_t) c);
}

static inline uint8_t uart_rxtx_read(void) {
    return hps_uart_read(HPS_UART_RBR_THR_OFFSET);
}

static inline uint8_t uart_txfull_read(void) {
    return !(hps_uart_read(HPS_UART_LSR_OFFSET) & HPS_UART_LSR_THRE);
}

static inline uint8_t uart_rxempty_read(void) {
    return !(hps_uart_read(HPS_UART_LSR_OFFSET) & HPS_UART_LSR_DR);
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
