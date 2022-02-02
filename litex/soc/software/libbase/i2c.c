// This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
// This file is Copyright (c) 2022 Franck Jullien <franck.jullien@collshade.fr>
#include "i2c.h"

#include <stdio.h>

#include <generated/csr.h>
#include <generated/i2c.h>

#ifdef CSR_I2C_BASE

#define I2C_PERIOD_CYCLES (CONFIG_CLOCK_FREQUENCY / I2C_FREQ_HZ)
#define I2C_DELAY(n)	  cdelay((n)*I2C_PERIOD_CYCLES/4)

i2c_write_t current_i2c_write = i2c_w_write;
i2c_read_t current_i2c_read = i2c_r_read;

static inline void cdelay(int i)
{
	while(i > 0) {
		__asm__ volatile(CONFIG_CPU_NOP);
		i--;
	}
}

int i2c_send_init_cmds(void)
{
#ifdef I2C_INIT
	struct i2c_cmds *i2c_cmd;
	int dev, i, len;
	uint8_t data[2];
	uint8_t addr;

	for (dev = 0; dev < I2C_INIT_DEVS; dev++) {
		i2c_cmd = &i2c_init[dev];
		current_i2c_write = i2c_cmd->ops.write;
		current_i2c_read = i2c_cmd->ops.read;

		for (i = 0; i < i2c_cmd->nb_cmds; i++) {

			if (i2c_cmd->addr_len == 2) {
				len     = 2;
				addr    = (i2c_cmd->init_table[i*2] >> 8) & 0xff;
				data[0] = i2c_cmd->init_table[i*2] & 0xff;
				data[1] = i2c_cmd->init_table[(i*2) + 1] & 0xff;
			} else {
				len     = 1;
				addr    = i2c_cmd->init_table[i*2] & 0xff;
				data[0] = i2c_cmd->init_table[(i*2) + 1] & 0xff;
			}

			if (!i2c_write(i2c_cmd->i2c_addr, addr, data, len))
				printf("Error during i2c write at address 0x%04x\n", addr);
		}
	}

	current_i2c_write = i2c_w_write;
	current_i2c_read = i2c_r_read;
#endif

	return 0;
}

static inline void i2c_oe_scl_sda(bool oe, bool scl, bool sda)
{
	current_i2c_write(
		((oe & 1)  << CSR_I2C_W_OE_OFFSET)	|
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
	value = current_i2c_read() & 1;
	I2C_DELAY(1);
	i2c_oe_scl_sda(0, 0, 0);
	I2C_DELAY(1);
	return value;
}

// Send data byte and return 1 if slave sends ACK
static bool i2c_transmit_byte(unsigned char data)
{
	int i;
	int ack;

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
static unsigned char i2c_receive_byte(bool ack)
{
	int i;
	unsigned char data = 0;

	for (i = 0; i < 8; ++i) {
		data <<= 1;
		data |= i2c_receive_bit();
	}
	i2c_transmit_bit(!ack);

	return data;
}

// Reset line state
void i2c_reset(void)
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

/*
 * Read slave memory over I2C starting at given address
 *
 * First writes the memory starting address, then reads the data:
 *   START WR(slaveaddr) WR(addr) STOP START WR(slaveaddr) RD(data) RD(data) ... STOP
 * Some chips require that after transmiting the address, there will be no STOP in between:
 *   START WR(slaveaddr) WR(addr) START WR(slaveaddr) RD(data) RD(data) ... STOP
 */
bool i2c_read(unsigned char slave_addr, unsigned char addr, unsigned char *data, unsigned int len, bool send_stop)
{
	int i;

	i2c_start();

	if(!i2c_transmit_byte(I2C_ADDR_WR(slave_addr))) {
		i2c_stop();
		return false;
	}
	if(!i2c_transmit_byte(addr)) {
		i2c_stop();
		return false;
	}

	if (send_stop) {
		i2c_stop();
	}
	i2c_start();

	if(!i2c_transmit_byte(I2C_ADDR_RD(slave_addr))) {
		i2c_stop();
		return false;
	}
	for (i = 0; i < len; ++i) {
		data[i] = i2c_receive_byte(i != len - 1);
	}

	i2c_stop();

	return true;
}

/*
 * Write slave memory over I2C starting at given address
 *
 * First writes the memory starting address, then writes the data:
 *   START WR(slaveaddr) WR(addr) WR(data) WR(data) ... STOP
 */
bool i2c_write(unsigned char slave_addr, unsigned char addr, const unsigned char *data, unsigned int len)
{
	int i;

	i2c_start();

	if(!i2c_transmit_byte(I2C_ADDR_WR(slave_addr))) {
		i2c_stop();
		return false;
	}
	if(!i2c_transmit_byte(addr)) {
		i2c_stop();
		return false;
	}
	for (i = 0; i < len; ++i) {
		if(!i2c_transmit_byte(data[i])) {
			i2c_stop();
			return false;
		}
	}

	i2c_stop();

	return true;
}

/*
 * Poll I2C slave at given address, return true if it sends an ACK back
 */
bool i2c_poll(unsigned char slave_addr)
{
    bool result;

    i2c_start();
    result = i2c_transmit_byte(I2C_ADDR_RD(slave_addr));
    i2c_stop();

    return result;
}

#endif /* CSR_I2C_BASE */
