// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <libbase/memtest.h>

#include <generated/soc.h>
#include <generated/csr.h>
#include <generated/mem.h>
#include <libbase/i2c.h>

#include <liblitedram/sdram.h>
#include <liblitedram/sdram_spd.h>
#include <liblitedram/bist.h>
#include <liblitedram/accessors.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "sdram_bist"
 *
 * Run SDRAM Build-In Self-Test
 *
 */
#if defined(CSR_SDRAM_GENERATOR_BASE) && defined(CSR_SDRAM_CHECKER_BASE)
static void sdram_bist_handler(int nb_params, char **params)
{
	char *c;
	int burst_length;
	int random;
	if (nb_params < 2) {
		printf("sdram_bist <burst_length> <random>");
		return;
	}
	burst_length = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect burst_length");
		return;
	}
	random = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect random");
		return;
	}
	sdram_bist(burst_length, random);
}
define_command(sdram_bist, sdram_bist_handler, "Run SDRAM Build-In Self-Test", LITEDRAM_CMDS);
#endif

/**
 * Command "sdram_hw_test"
 *
 * Run SDRAM HW-accelerated memtest
 *
 */
#if defined(CSR_SDRAM_GENERATOR_BASE) && defined(CSR_SDRAM_CHECKER_BASE)
static void sdram_hw_test_handler(int nb_params, char **params)
{
	char *c;
	uint64_t origin;
	uint64_t size;
	uint64_t burst_length = 1;
	if (nb_params < 2) {
		printf("sdram_hw_test <origin> <size> [<burst_length>]");
		return;
	}
	origin = strtoull(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect origin");
		return;
	}
	size = strtoull(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect size");
		return;
	}
	if (nb_params > 2) {
		burst_length = strtoull(params[2], &c, 0);
		if (*c != 0) {
			printf("Incorrect burst length");
			return;
		}
	}
	int errors = sdram_hw_test(origin, size, burst_length);
	printf("%d errors found\n", errors);
}
define_command(sdram_hw_test, sdram_hw_test_handler, "Run SDRAM HW-accelerated memtest", LITEDRAM_CMDS);
#endif

#ifdef CSR_DDRPHY_RDPHASE_ADDR
/**
 * Command "sdram_force_rdphase"
 *
 * Force read phase
 *
 */
static void sdram_force_rdphase_handler(int nb_params, char **params)
{
	char *c;
	int phase;
	if (nb_params < 1) {
		printf("sdram_force_rdphase <phase>");
		return;
	}
	phase = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect phase");
		return;
	}
	printf("Forcing read phase to %d\n", phase);
	ddrphy_rdphase_write(phase);
}
define_command(sdram_force_rdphase, sdram_force_rdphase_handler, "Force read phase", LITEDRAM_CMDS);
#endif

#ifdef CSR_DDRPHY_WRPHASE_ADDR
/**
 * Command "sdram_force_wrphase"
 *
 * Force write phase
 *
 */
static void sdram_force_wrphase_handler(int nb_params, char **params)
{
	char *c;
	int phase;
	if (nb_params < 1) {
		printf("sdram_force_wrphase <phase>");
		return;
	}
	phase = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect phase");
		return;
	}
	printf("Forcing write phase to %d\n", phase);
	ddrphy_wrphase_write(phase);
}
define_command(sdram_force_wrphase, sdram_force_wrphase_handler, "Force write phase", LITEDRAM_CMDS);
#endif

#ifdef CSR_DDRPHY_CDLY_RST_ADDR

/**
 * Command "sdram_rst_cmd_delay"
 *
 * Reset write leveling Cmd delay
 *
 */
#if defined(CSR_SDRAM_BASE) && defined(CSR_DDRPHY_BASE)
static void sdram_rst_cmd_delay_handler(int nb_params, char **params)
{
	sdram_software_control_on();
	sdram_write_leveling_rst_cmd_delay(1);
	sdram_software_control_off();
}
define_command(sdram_rst_cmd_delay, sdram_rst_cmd_delay_handler, "Reset write leveling Cmd delay", LITEDRAM_CMDS);
#endif

/**
 * Command "sdram_force_cmd_delay"
 *
 * Force write leveling Cmd delay
 *
 */
#if defined(CSR_SDRAM_BASE) && defined(CSR_DDRPHY_BASE)
static void sdram_force_cmd_delay_handler(int nb_params, char **params)
{
	char *c;
	int taps;
	if (nb_params < 1) {
		printf("sdram_force_cmd_delay <taps>");
		return;
	}
	taps = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect taps");
		return;
	}
	sdram_software_control_on();
	sdram_write_leveling_force_cmd_delay(taps, 1);
	sdram_software_control_off();
}
define_command(sdram_force_cmd_delay, sdram_force_cmd_delay_handler, "Force write leveling Cmd delay", LITEDRAM_CMDS);
#endif

#endif

#if defined(CSR_SDRAM_BASE)
/**
 * Command "sdram_init"
 *
 * Initialize SDRAM (Init + Calibration)
 *
 */
define_command(sdram_init, sdram_init, "Initialize SDRAM (Init + Calibration)", LITEDRAM_CMDS);

/**
 * Command "sdram_test"
 *
 * Test SDRAM
 *
 */
static void sdram_test_handler(int nb_params, char **params)
{
	memtest((unsigned int *)MAIN_RAM_BASE, MAIN_RAM_SIZE/32);
}
define_command(sdram_test, sdram_test_handler, "Test SDRAM", LITEDRAM_CMDS);

/**
 * Command "sdram_cal"
 *
 * Calibrate SDRAM
 *
 */
#if defined(CSR_DDRPHY_BASE)
static void sdram_cal_handler(int nb_params, char **params)
{
	sdram_software_control_on();
	sdram_leveling();
	sdram_software_control_off();
}
define_command(sdram_cal, sdram_cal_handler, "Calibrate SDRAM", LITEDRAM_CMDS);
#endif

#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE

/**
 * Command "sdram_rst_dat_delay"
 *
 * Reset write leveling Dat delay
 *
 */
#if defined(CSR_DDRPHY_BASE)
static void sdram_rst_dat_delay_handler(int nb_params, char **params)
{
	char *c;
	int module;
	if (nb_params < 1) {
		printf("sdram_rst_dat_delay <module>");
		return;
	}
	module = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect module");
		return;
	}
	sdram_software_control_on();
	sdram_write_leveling_rst_dat_delay(module, 1);
	sdram_software_control_off();
}
define_command(sdram_rst_dat_delay, sdram_rst_dat_delay_handler, "Reset write leveling Dat delay", LITEDRAM_CMDS);
#endif

/**
 * Command "sdram_force_dat_delay"
 *
 * Force write leveling Dat delay
 *
 */
#if defined(CSR_DDRPHY_BASE)
static void sdram_force_dat_delay_handler(int nb_params, char **params)
{
	char *c;
	int module;
	int taps;
	if (nb_params < 2) {
		printf("sdram_force_dat_delay <module> <taps>");
		return;
	}
	module = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect module");
		return;
	}
	taps = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect taps");
		return;
	}
	sdram_software_control_on();
	sdram_write_leveling_force_dat_delay(module, taps, 1);
	sdram_software_control_off();
}
define_command(sdram_force_dat_delay, sdram_force_dat_delay_handler, "Force write leveling Dat delay", LITEDRAM_CMDS);
#endif /* defined(CSR_SDRAM_BASE) && defined(CSR_DDRPHY_BASE) */

#endif /* SDRAM_PHY_WRITE_LEVELING_CAPABLE */

#if defined(SDRAM_PHY_BITSLIPS) && defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE)
/**
 * Command "sdram_rst_bitslip"
 *
 * Reset write leveling Bitslip
 *
 */
#if defined(CSR_DDRPHY_BASE)
static void sdram_rst_bitslip_handler(int nb_params, char **params)
{
	char *c;
	int module;
	if (nb_params < 1) {
		printf("sdram_rst_bitslip <module>");
		return;
	}
	module = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect module");
		return;
	}
	sdram_software_control_on();
	sdram_write_leveling_rst_bitslip(module, 1);
	sdram_software_control_off();
}
define_command(sdram_rst_bitslip, sdram_rst_bitslip_handler, "Reset write leveling Bitslip", LITEDRAM_CMDS);
#endif

/**
 * Command "sdram_force_bitslip"
 *
 * Force write leveling Bitslip
 *
 */
#if defined(CSR_DDRPHY_BASE)
static void sdram_force_bitslip_handler(int nb_params, char **params)
{
	char *c;
	int module;
	int bitslip;
	if (nb_params < 2) {
		printf("sdram_force_bitslip <module> <bitslip>");
		return;
	}
	module = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect module");
		return;
	}
	bitslip = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect bitslip");
		return;
	}
	sdram_software_control_on();
	sdram_write_leveling_force_bitslip(module, bitslip, 1);
	sdram_software_control_off();
}
define_command(sdram_force_bitslip, sdram_force_bitslip_handler, "Force write leveling Bitslip", LITEDRAM_CMDS);
#endif

#endif /* defined(SDRAM_PHY_BITSLIPS) && defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) */

/**
 * Command "sdram_mr_write"
 *
 * Write SDRAM Mode Register
 *
 */
static void sdram_mr_write_handler(int nb_params, char **params)
{
	char *c;
	uint8_t reg;
	uint16_t value;

	if (nb_params < 2) {
		printf("sdram_mr_write <reg> <value>");
		return;
	}
	reg = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect reg");
		return;
	}
	value = strtoul(params[1], &c, 0);
	if (*c != 0) {
		printf("Incorrect value");
		return;
	}
	sdram_software_control_on();
	printf("Writing 0x%04x to MR%d\n", value, reg);
	sdram_mode_register_write(reg, value);
	sdram_software_control_off();
}
define_command(sdram_mr_write, sdram_mr_write_handler, "Write SDRAM Mode Register", LITEDRAM_CMDS);

#endif /* CSR_SDRAM_BASE */

/**
 * Command "sdram_spd"
 *
 * Read contents of SPD EEPROM memory.
 * SPD address is a 3-bit address defined by the pins A0, A1, A2.
 *
 */
#ifdef CONFIG_HAS_I2C
static void sdram_spd_handler(int nb_params, char **params)
{
	char *c;
	unsigned char spdaddr;
	unsigned char buf[SDRAM_SPD_SIZE];
	int len = sizeof(buf);
	bool send_stop = true;

	if (nb_params < 1) {
		printf("sdram_spd <spdaddr> [<send_stop>]");
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

	if (!sdram_read_spd(spdaddr, 0, buf, (uint16_t)len, send_stop)) {
		printf("Error when reading SPD EEPROM");
		return;
	}

	dump_bytes((unsigned int *) buf, len, 0);

#ifdef SPD_BASE
	{
		int cmp_result;
		cmp_result = memcmp(buf, (void *) SPD_BASE, SPD_SIZE);
		if (cmp_result == 0) {
			printf("Memory contents matches the data used for gateware generation\n");
		} else {
			printf("\nWARNING: memory differs from the data used during gateware generation:\n");
			dump_bytes((void *) SPD_BASE, SPD_SIZE, 0);
		}
	}
#endif
}
define_command(sdram_spd, sdram_spd_handler, "Read SDRAM SPD EEPROM", LITEDRAM_CMDS);
#endif

#ifdef SDRAM_DEBUG
define_command(sdram_debug, sdram_debug, "Run SDRAM debug tests", LITEDRAM_CMDS);
#endif
