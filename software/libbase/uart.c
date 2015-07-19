#include <uart.h>
#include <irq.h>
#include <generated/csr.h>
#include <hw/flags.h>

/*
 * Buffer sizes must be a power of 2 so that modulos can be computed
 * with logical AND.
 */

#define UART_RINGBUFFER_SIZE_RX 128
#define UART_RINGBUFFER_MASK_RX (UART_RINGBUFFER_SIZE_RX-1)

static char rx_buf[UART_RINGBUFFER_SIZE_RX];
static volatile unsigned int rx_produce;
static unsigned int rx_consume;

#define UART_RINGBUFFER_SIZE_TX 128
#define UART_RINGBUFFER_MASK_TX (UART_RINGBUFFER_SIZE_TX-1)

static char tx_buf[UART_RINGBUFFER_SIZE_TX];
static unsigned int tx_produce;
static volatile unsigned int tx_consume;

void uart_isr(void)
{
	unsigned int stat, rx_produce_next;

	stat = uart_ev_pending_read();

	if(stat & UART_EV_RX) {
		while(!uart_rxempty_read()) {
			rx_produce_next = (rx_produce + 1) & UART_RINGBUFFER_MASK_RX;
			if(rx_produce_next != rx_consume) {
				rx_buf[rx_produce] = uart_rxtx_read();
				rx_produce = rx_produce_next;
			}
			uart_ev_pending_write(UART_EV_RX);
		}
	}

	if(stat & UART_EV_TX) {
		uart_ev_pending_write(UART_EV_TX);
		while((tx_consume != tx_produce) && !uart_txfull_read()) {
			uart_rxtx_write(tx_buf[tx_consume]);
			tx_consume = (tx_consume + 1) & UART_RINGBUFFER_MASK_TX;
		}
	}
}

/* Do not use in interrupt handlers! */
char uart_read(void)
{
	char c;

	if(irq_getie()) {
		while(rx_consume == rx_produce);
	} else if (rx_consume == rx_produce) {
		return 0;
	}

	c = rx_buf[rx_consume];
	rx_consume = (rx_consume + 1) & UART_RINGBUFFER_MASK_RX;
	return c;
}

int uart_read_nonblock(void)
{
	return (rx_consume != rx_produce);
}

void uart_write(char c)
{
	unsigned int oldmask;
	unsigned int tx_produce_next = (tx_produce + 1) & UART_RINGBUFFER_MASK_TX;

	if(irq_getie()) {
		while(tx_produce_next == tx_consume);
	} else if(tx_produce_next == tx_consume) {
		return;
	}

	oldmask = irq_getmask();
	irq_setmask(oldmask & ~(1 << UART_INTERRUPT));
	if((tx_consume != tx_produce) || uart_txfull_read()) {
		tx_buf[tx_produce] = c;
		tx_produce = tx_produce_next;
	} else {
		uart_rxtx_write(c);
	}
	irq_setmask(oldmask);
}

void uart_init(void)
{
	rx_produce = 0;
	rx_consume = 0;

	tx_produce = 0;
	tx_consume = 0;

	uart_ev_pending_write(uart_ev_pending_read());
	uart_ev_enable_write(UART_EV_TX | UART_EV_RX);
	irq_setmask(irq_getmask() | (1 << UART_INTERRUPT));
}

void uart_sync(void)
{
	while(tx_consume != tx_produce);
}
