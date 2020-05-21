// This file is Copyright (c) 2020 Antmicro <www.antmicro.com>

#include <stdio.h>
#include "spd.h"

#ifdef CSR_I2C_BASE

// SMBus uses frequency 10-100 kHz
#define I2C_FREQ_HZ       50000
#define I2C_PERIOD_CYCLES (CONFIG_CLOCK_FREQUENCY / I2C_FREQ_HZ)
#define I2C_DELAY(n)      cdelay((n)*I2C_PERIOD_CYCLES/4)

static void cdelay(int i)
{
	while(i > 0) {
		__asm__ volatile(CONFIG_CPU_NOP);
		i--;
	}
}

static void i2c_oe_scl_sda(int oe, int scl, int sda)
{
	i2c_w_write(
		((oe & 1)  << CSR_I2C_W_OE_OFFSET)  |
		((scl & 1) << CSR_I2C_W_SCL_OFFSET) |
		((sda & 1) << CSR_I2C_W_SDA_OFFSET)
	);
}


// START condition: 1-to-0 transition of SDA when SCL is 1
static void i2c_start(void)
{
	i2c_oe_scl_sda(1, 1, 1);
	I2C_DELAY(1);
	i2c_oe_scl_sda(1, 1, 0);
	I2C_DELAY(1);
	i2c_oe_scl_sda(1, 0, 0);
	I2C_DELAY(1);
}

// STOP condition: 0-to-1 transition of SDA when SCL is 1
static void i2c_stop(void)
{
	i2c_oe_scl_sda(1, 0, 0);
	I2C_DELAY(1);
	i2c_oe_scl_sda(1, 1, 0);
	I2C_DELAY(1);
	i2c_oe_scl_sda(1, 1, 1);
	I2C_DELAY(1);
	i2c_oe_scl_sda(0, 1, 1);
}

// Reset line state
static void i2c_reset(void)
{
	int i;
	i2c_oe_scl_sda(1, 1, 1);
	I2C_DELAY(8);
	for (i = 0; i < 9; ++i) {
		i2c_oe_scl_sda(1, 0, 1);
		I2C_DELAY(2);
		i2c_oe_scl_sda(1, 1, 1);
		I2C_DELAY(2);
	}
	i2c_oe_scl_sda(0, 0, 1);
	I2C_DELAY(1);
	i2c_stop();
	i2c_oe_scl_sda(0, 1, 1);
	I2C_DELAY(8);
}

// Call when in the middle of SCL low, advances one clk period
static void i2c_transmit_bit(int value)
{
	i2c_oe_scl_sda(1, 0, value);
	I2C_DELAY(1);
	i2c_oe_scl_sda(1, 1, value);
	I2C_DELAY(2);
	i2c_oe_scl_sda(1, 0, value);
	I2C_DELAY(1);
	i2c_oe_scl_sda(0, 0, 0);  // release line
}

// Call when in the middle of SCL low, advances one clk period
static int i2c_receive_bit(void)
{
	int value;
	i2c_oe_scl_sda(0, 0, 0);
	I2C_DELAY(1);
	i2c_oe_scl_sda(0, 1, 0);
	I2C_DELAY(1);
	// read in the middle of SCL high
	value = i2c_r_read() & 1;
	I2C_DELAY(1);
	i2c_oe_scl_sda(0, 0, 0);
	I2C_DELAY(1);
	return value;
}

// Send data byte and return 1 if slave sends ACK
static int i2c_transmit(unsigned char data)
{
	int ack;
	int i;

	// SCL should have already been low for 1/4 cycle
	i2c_oe_scl_sda(0, 0, 0);
	for (i = 0; i < 8; ++i) {
		// MSB first
		i2c_transmit_bit((data & (1 << 7)) != 0);
		data <<= 1;
	}
	ack = i2c_receive_bit();

	// 0 from slave means ack
	return ack == 0;
}

// Read data byte and send ACK if ack=1
static unsigned char i2c_receive(int ack)
{
	unsigned char data = 0;
	int i;

	i2c_oe_scl_sda(0, 0, 0);
	I2C_DELAY(1);
	for (i = 0; i < 8; ++i) {
		data <<= 1;
		data |= i2c_receive_bit();
	}
	i2c_transmit_bit(!ack);

	return data;
}


#define ADDR_PREAMBLE_RW  0b1010
#define ADDR_7BIT(addr)   ((ADDR_PREAMBLE_RW << 3) | ((addr) & 0b111))
#define ADDR_WRITE(addr)  ((ADDR_7BIT(addr) << 1) & (~1u))
#define ADDR_READ(addr)   ((ADDR_7BIT(addr) << 1) | 1u)

/*
 * Read SPD memory content
 *
 * spdaddr: address of SPD EEPROM defined by pins A0, A1, A2
 * addr: memory starting address
 */
int spdread(unsigned int spdaddr, unsigned int addr, unsigned char *buf, unsigned int len) {
	int i;

	i2c_reset();

	// To read from random address, we have to first send a "data-less" WRITE,
	// followed by START condition with a READ (no STOP condition)
	i2c_start();

	if(!i2c_transmit(ADDR_WRITE(spdaddr))) {
		i2c_reset();
		return 0;
	}
	if(!i2c_transmit(addr)) {
		i2c_reset();
		return 0;
	}

	I2C_DELAY(1);
	i2c_start();
	if(!i2c_transmit(ADDR_READ(spdaddr))) {
		i2c_reset();
		return 0;
	}
	for (i = 0; i < len; ++i) {
		buf[i] = i2c_receive(i != len - 1);
	}
	i2c_stop();

	return 1;
}
#endif /* CSR_I2C_BASE */
