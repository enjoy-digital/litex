#ifndef __SYSTEM_H
#define __SYSTEM_H

#ifdef __cplusplus
extern "C" {
#endif

__attribute__((unused)) static void flush_cpu_icache(void){};
__attribute__((unused)) static void flush_cpu_dcache(void){};
void flush_l2_cache(void);

void busy_wait(unsigned int ms);
void busy_wait_us(unsigned int us);

#include <stdint.h>

// FIXME
#define CSR_UART_BASE
#define UART_POLLING

struct EMCU_UART
{
  volatile uint32_t data;
  volatile uint32_t state;
  volatile uint32_t ctrl;
  volatile uint32_t int_ctrl;
  volatile uint32_t baud_div;
};

#define PERIPHERALS_BASE 0x40000000
#define UART0 ((struct EMCU_UART *) (PERIPHERALS_BASE + 0x4000))

static inline char uart_txfull_read(void);
static inline char uart_rxempty_read(void);
static inline void uart_ev_enable_write(char c);
static inline void uart_rxtx_write(char c);
static inline char uart_rxtx_read(void);
static inline void uart_ev_pending_write(char);
static inline char uart_ev_pending_read(void);

static inline char uart_txfull_read(void) {
  return UART0->state & 0b01;
}

static inline char uart_rxempty_read(void) {
  return !(UART0->state & 0b10);
}

static inline void uart_ev_enable_write(char c) {
  // FIXME
}

static inline void uart_rxtx_write(char c) {
  UART0->data = (uint32_t) c;
}

static inline char uart_rxtx_read(void)
{
  return (char)(UART0->data);
}

static inline void uart_ev_pending_write(char x) {}
static inline char uart_ev_pending_read(void) {
  return 0;
}


#ifdef __cplusplus
}
#endif

#endif /* __SYSTEM_H */
