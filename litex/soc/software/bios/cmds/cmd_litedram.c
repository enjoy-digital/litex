// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include <generated/csr.h>

#include "sdram.h"

#include "../command.h"
#include "../helpers.h"

/**
 * Command "sdrrow"
 *
 * Precharge/Activate row
 *
 */
#ifdef CSR_SDRAM_BASE
static void sdrrow_handler(int nb_params, char **params)
{
	char *c;
	unsigned int row;

	if (nb_params < 1) {
		sdrrow(0);
		printf("Precharged");
	}

	row = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect row");
		return;
	}

	sdrrow(row);
	printf("Activated row %d", row);
}
define_command(sdrrow, sdrrow_handler, "Precharge/Activate row", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrsw"
 *
 * Gives SDRAM control to SW
 *
 */
#ifdef CSR_SDRAM_BASE
define_command(sdrsw, sdrsw, "Gives SDRAM control to SW", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrhw"
 *
 * Gives SDRAM control to HW
 *
 */
#ifdef CSR_SDRAM_BASE
define_command(sdrhw, sdrhw, "Gives SDRAM control to HW", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrrdbuf"
 *
 * Dump SDRAM read buffer
 *
 */
#ifdef CSR_SDRAM_BASE
static void sdrrdbuf_handler(int nb_params, char **params)
{
	sdrrdbuf(-1);
}

define_command(sdrrdbuf, sdrrdbuf_handler, "Dump SDRAM read buffer", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrrd"
 *
 * Read SDRAM data
 *
 */
#ifdef CSR_SDRAM_BASE
static void sdrrd_handler(int nb_params, char **params)
{
	unsigned int addr;
	int dq;
	char *c;

	if (nb_params < 1) {
		printf("sdrrd <address>");
		return;
	}

	addr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}

	if (nb_params < 2)
		dq = -1;
	else {
		dq = strtoul(params[1], &c, 0);
		if (*c != 0) {
			printf("Incorrect DQ");
			return;
		}
	}

	sdrrd(addr, dq);
}

define_command(sdrrd, sdrrd_handler, "Read SDRAM data", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrrderr"
 *
 * Print SDRAM read errors
 *
 */
#ifdef CSR_SDRAM_BASE
static void sdrrderr_handler(int nb_params, char **params)
{
	int count;
	char *c;

	if (nb_params < 1) {
		printf("sdrrderr <count>");
		return;
	}

	count = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect count");
		return;
	}

	sdrrderr(count);
}

define_command(sdrrderr, sdrrderr_handler, "Print SDRAM read errors", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrwr"
 *
 * Write SDRAM test data
 *
 */
#ifdef CSR_SDRAM_BASE
static void sdrwr_handler(int nb_params, char **params)
{
	unsigned int addr;
	char *c;

	if (nb_params < 1) {
		printf("sdrwr <address>");
		return;
	}

	addr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}

	sdrwr(addr);
}

define_command(sdrwr, sdrwr_handler, "Write SDRAM test data", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrinit"
 *
 * Start SDRAM initialisation
 *
 */
#if defined(CSR_SDRAM_BASE) && defined(CSR_DDRPHY_BASE)
define_command(sdrinit, sdrinit, "Start SDRAM initialisation", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrwlon"
 *
 * Write leveling ON
 *
 */
#if defined(CSR_DDRPHY_BASE) && defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) && defined(CSR_SDRAM_BASE)
define_command(sdrwlon, sdrwlon, "Enable write leveling", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrwloff"
 *
 * Write leveling OFF
 *
 */
#if defined(CSR_DDRPHY_BASE) && defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) && defined(CSR_SDRAM_BASE)
define_command(sdrwloff, sdrwloff, "Disable write leveling", LITEDRAM_CMDS);
#endif

/**
 * Command "sdrlevel"
 *
 * Perform read/write leveling
 *
 */
#if defined(CSR_DDRPHY_BASE) && defined(CSR_SDRAM_BASE)
define_command(sdrlevel, sdrlevel, "Perform read/write leveling", LITEDRAM_CMDS);
#endif

/**
 * Command "memtest"
 *
 * Run a memory test
 *
 */
#ifdef CSR_SDRAM_BASE
define_command(memtest, memtest, "Run a memory test", LITEDRAM_CMDS);
#endif

/**
 * Command "i2creset"
 *
 * Reset I2C line state in case a slave locks the line.
 *
 */
#ifdef CSR_I2C_BASE
define_command(i2creset, i2c_reset, "Reset I2C line state", LITEDRAM_CMDS);
#endif

/**
 * Command "i2cwr"
 *
 * Write I2C slave memory using 7-bit slave address and 8-bit memory address.
 *
 */
#ifdef CSR_I2C_BASE
static void i2cwr_handler(int nb_params, char **params)
{
	int i;
	char *c;
	unsigned char write_params[32];  // also indirectly limited by CMD_LINE_BUFFER_SIZE

	if (nb_params < 2) {
		printf("i2cwr <slaveaddr7bit> <addr> [<data>, ...]");
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
define_command(i2cwr, i2cwr_handler, "Write over I2C", LITEDRAM_CMDS);
#endif

/**
 * Command "i2crd"
 *
 * Read I2C slave memory using 7-bit slave address and 8-bit memory address.
 *
 */
#ifdef CSR_I2C_BASE
static void i2crd_handler(int nb_params, char **params)
{
	char *c;
	int len;
	unsigned char slave_addr, addr;
	unsigned char buf[256];
	bool send_stop = true;

	if (nb_params < 3) {
		printf("i2crd <slaveaddr7bit> <addr> <len> [<send_stop>]");
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
define_command(i2crd, i2crd_handler, "Read over I2C", LITEDRAM_CMDS);
#endif

/**
 * Command "spdread"
 *
 * Read contents of SPD EEPROM memory.
 * SPD address is a 3-bit address defined by the pins A0, A1, A2.
 *
 */
#ifdef CSR_I2C_BASE
#define SPD_RW_PREAMBLE    0b1010
#define SPD_RW_ADDR(a210)  ((SPD_RW_PREAMBLE << 3) | ((a210) & 0b111))

static void spdread_handler(int nb_params, char **params)
{
	char *c;
	unsigned char spdaddr;
	unsigned char buf[256];
	int len = sizeof(buf);
	bool send_stop = true;

	if (nb_params < 1) {
		printf("spdread <spdaddr> [<send_stop>]");
		return;
	}

	spdaddr = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect address");
		return;
	}
	if (spdaddr > 0b111) {
		printf("SPD EEPROM max address is 0b111 (defined by A0, A1, A2 pins)");
		return;
	}

	if (nb_params > 1) {
		send_stop = strtoul(params[1], &c, 0) != 0;
		if (*c != 0) {
			printf("Incorrect send_stop value");
			return;
		}
	}

	if (!i2c_read(SPD_RW_ADDR(spdaddr), 0, buf, len, send_stop)) {
		printf("Error when reading SPD EEPROM");
		return;
	}

	dump_bytes((unsigned int *) buf, len, 0);
}
define_command(spdread, spdread_handler, "Read SPD EEPROM", LITEDRAM_CMDS);
#endif
