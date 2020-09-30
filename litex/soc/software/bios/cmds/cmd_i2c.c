// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include <generated/csr.h>
#include <i2c.h>

#include "../command.h"
#include "../helpers.h"


/**
 * Command "i2c_reset"
 *
 * Reset I2C line state in case a slave locks the line.
 *
 */
#ifdef CSR_I2C_BASE
define_command(i2c_reset, i2c_reset, "Reset I2C line state", I2C_CMDS);
#endif

/**
 * Command "i2c_write"
 *
 * Write I2C slave memory using 7-bit slave address and 8-bit memory address.
 *
 */
#ifdef CSR_I2C_BASE
static void i2c_write_handler(int nb_params, char **params)
{
	int i;
	char *c;
	unsigned char write_params[32];  // also indirectly limited by CMD_LINE_BUFFER_SIZE

	if (nb_params < 2) {
		printf("i2c_write <slaveaddr7bit> <addr> [<data>, ...]");
		return;
	}

	if (nb_params - 1 > sizeof(write_params)) {
		printf("Max data length is %d", sizeof(write_params));
		return;
	}

	for (i = 0; i < nb_params; ++i) {
		write_params[i] = strtoul(params[i], &c, 0);
		if (*c != 0) {
			printf("Incorrect value of parameter %d", i);
			return;
		}
	}

	if (!i2c_write(write_params[0], write_params[1], &write_params[2], nb_params - 2)) {
		printf("Error during I2C write");
		return;
	}
}
define_command(i2c_write, i2c_write_handler, "Write over I2C", I2C_CMDS);
#endif

/**
 * Command "i2crd"
 *
 * Read I2C slave memory using 7-bit slave address and 8-bit memory address.
 *
 */
#ifdef CSR_I2C_BASE
static void i2c_read_handler(int nb_params, char **params)
{
	char *c;
	int len;
	unsigned char slave_addr, addr;
	unsigned char buf[256];
	bool send_stop = true;

	if (nb_params < 3) {
		printf("i2c_read <slaveaddr7bit> <addr> <len> [<send_stop>]");
		return;
	}

	slave_addr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect slave address");
		return;
	}

	addr = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect memory address");
		return;
	}

	len = strtoul(params[2], &c, 0);
	if (*c != 0) {
		printf("Incorrect data length");
		return;
	}
	if (len > sizeof(buf)) {
		printf("Max data count is %d", sizeof(buf));
		return;
	}

	if (nb_params > 3) {
		send_stop = strtoul(params[3], &c, 0) != 0;
		if (*c != 0) {
			printf("Incorrect send_stop value");
			return;
		}
	}

	if (!i2c_read(slave_addr, addr, buf, len, send_stop)) {
		printf("Error during I2C read");
		return;
	}

	dump_bytes((unsigned int *) buf, len, addr);
}
define_command(i2c_read, i2c_read_handler, "Read over I2C", I2C_CMDS);
#endif
