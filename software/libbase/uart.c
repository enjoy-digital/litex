/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009, 2010, 2012 Sebastien Bourdeauducq
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <uart.h>
#include <irq.h>
#include <hw/uart.h>
#include <interrupt.h>

/*
 * Buffer sizes must be a power of 2 so that modulos can be computed
 * with logical AND.
 */

#define UART_RINGBUFFER_SIZE_RX 128
#define UART_RINGBUFFER_MASK_RX (UART_RINGBUFFER_SIZE_RX-1)

static char rx_buf[UART_RINGBUFFER_SIZE_RX];
static volatile unsigned int rx_produce;
static volatile unsigned int rx_consume;

#define UART_RINGBUFFER_SIZE_TX 128
#define UART_RINGBUFFER_MASK_TX (UART_RINGBUFFER_SIZE_TX-1)

static char tx_buf[UART_RINGBUFFER_SIZE_TX];
static unsigned int tx_produce;
static unsigned int tx_consume;
static volatile int tx_cts;
static volatile int tx_level;

void uart_isr(void)
{
	unsigned int stat;
	
	stat = CSR_UART_EV_PENDING;

	if(stat & UART_EV_RX) {
		rx_buf[rx_produce] = CSR_UART_RXTX;
		rx_produce = (rx_produce + 1) & UART_RINGBUFFER_MASK_RX;
	}

	if(stat & UART_EV_TX) {
		if(tx_level > 0) {
			CSR_UART_RXTX = tx_buf[tx_consume];
			tx_consume = (tx_consume + 1) & UART_RINGBUFFER_MASK_TX;
			tx_level--;
		} else
			tx_cts = 1;
	}

	CSR_UART_EV_PENDING = stat;
}

/* Do not use in interrupt handlers! */
char uart_read(void)
{
	char c;
	
	while(rx_consume == rx_produce);
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
	
	if(irq_getie()) {
		while(tx_level == UART_RINGBUFFER_SIZE_TX);
	}
	
	oldmask = irq_getmask();
	irq_setmask(0);

	if(tx_cts) {
		tx_cts = 0;
		CSR_UART_RXTX = c;
	} else {
		tx_buf[tx_produce] = c;
		tx_produce = (tx_produce + 1) & UART_RINGBUFFER_MASK_TX;
		tx_level++;
	}
	irq_setmask(oldmask);
}

void uart_init(void)
{
	unsigned int mask;
	
	rx_produce = 0;
	rx_consume = 0;
	
	tx_produce = 0;
	tx_consume = 0;
	tx_cts = 1;
	tx_level = 0;

	/* ack any events */
	CSR_UART_EV_PENDING = CSR_UART_EV_PENDING;

	/* enable interrupts */
	CSR_UART_EV_ENABLE = UART_EV_TX | UART_EV_RX;

	mask = irq_getmask();
	mask |= UART_INTERRUPT;
	irq_setmask(mask);
}

void uart_sync(void)
{
	while(!tx_cts);
}
