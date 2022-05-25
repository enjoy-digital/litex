// This file is Copyright (c) 2013-2020 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
// This file is Copyright (c) 2018 Chris Ballance <chris.ballance@physics.ox.ac.uk>
// This file is Copyright (c) 2018 Dolu1990 <charles.papon.90@gmail.com>
// This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
// This file is Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
// This file is Copyright (c) 2018 Sergiusz Bazanski <q3k@q3k.org>
// This file is Copyright (c) 2018 Tim 'mithro' Ansell <me@mith.ro>
// This file is Copyright (c) 2021 Antmicro <www.antmicro.com>
// License: BSD

#include <generated/csr.h>
#include <generated/mem.h>

#include <stdio.h>
#include <stdlib.h>

#include <libbase/memtest.h>
#include <libbase/lfsr.h>

#ifdef CSR_SDRAM_BASE
#include <generated/sdram_phy.h>
#endif
#include <generated/mem.h>
#include <system.h>

#include <liblitedram/sdram.h>
#include <liblitedram/sdram_dbg.h>

//#define SDRAM_TEST_DISABLE
//#define SDRAM_WRITE_LEVELING_CMD_DELAY_DEBUG
//#define SDRAM_WRITE_LATENCY_CALIBRATION_DEBUG
//#define SDRAM_LEVELING_SCAN_DISPLAY_HEX_DIV 10

#ifdef CSR_SDRAM_BASE

/*-----------------------------------------------------------------------*/
/* Helpers                                                               */
/*-----------------------------------------------------------------------*/

#define max(x, y) (((x) > (y)) ? (x) : (y))
#define min(x, y) (((x) < (y)) ? (x) : (y))

__attribute__((unused)) void cdelay(int i)
{
#ifndef CONFIG_BIOS_NO_DELAYS
	while(i > 0) {
		__asm__ volatile(CONFIG_CPU_NOP);
		i--;
	}
#endif
}

/*-----------------------------------------------------------------------*/
/* Constants                                                             */
/*-----------------------------------------------------------------------*/

#define DFII_PIX_DATA_BYTES SDRAM_PHY_DFI_DATABITS/8

int sdram_get_databits(void) {
	return SDRAM_PHY_DATABITS;
}

int sdram_get_freq(void) {
	return SDRAM_PHY_XDR*SDRAM_PHY_PHASES*CONFIG_CLOCK_FREQUENCY;
}

int sdram_get_cl(void) {
#ifdef SDRAM_PHY_CL
	return SDRAM_PHY_CL;
#else
	return -1;
#endif
}

int sdram_get_cwl(void) {
#ifdef SDRAM_PHY_CWL
	return SDRAM_PHY_CWL;
#else
	return -1;
#endif
}

/*-----------------------------------------------------------------------*/
/* DFII                                                                  */
/*-----------------------------------------------------------------------*/

#ifdef CSR_DDRPHY_BASE

static unsigned char sdram_dfii_get_rdphase(void) {
#ifdef CSR_DDRPHY_RDPHASE_ADDR
	return ddrphy_rdphase_read();
#else
	return SDRAM_PHY_RDPHASE;
#endif
}

static unsigned char sdram_dfii_get_wrphase(void) {
#ifdef CSR_DDRPHY_WRPHASE_ADDR
	return ddrphy_wrphase_read();
#else
	return SDRAM_PHY_WRPHASE;
#endif
}

static void sdram_dfii_pix_address_write(unsigned char phase, unsigned int value) {
#if (SDRAM_PHY_PHASES > 8)
	#error "More than 8 DFI phases not supported"
#endif
	switch (phase) {
#if (SDRAM_PHY_PHASES > 4)
	case 7: sdram_dfii_pi7_address_write(value); break;
	case 6: sdram_dfii_pi6_address_write(value); break;
	case 5: sdram_dfii_pi5_address_write(value); break;
	case 4: sdram_dfii_pi4_address_write(value); break;
#endif
#if (SDRAM_PHY_PHASES > 2)
	case 3: sdram_dfii_pi3_address_write(value); break;
	case 2: sdram_dfii_pi2_address_write(value); break;
#endif
#if (SDRAM_PHY_PHASES > 1)
	case 1: sdram_dfii_pi1_address_write(value); break;
#endif
	default: sdram_dfii_pi0_address_write(value);
	}
}

static void sdram_dfii_pird_address_write(unsigned int value) {
	unsigned char rdphase = sdram_dfii_get_rdphase();
	sdram_dfii_pix_address_write(rdphase, value);
}

static void sdram_dfii_piwr_address_write(unsigned int value) {
	unsigned char wrphase = sdram_dfii_get_wrphase();
	sdram_dfii_pix_address_write(wrphase, value);
}

static void sdram_dfii_pix_baddress_write(unsigned char phase, unsigned int value) {
#if (SDRAM_PHY_PHASES > 8)
	#error "More than 8 DFI phases not supported"
#endif
	switch (phase) {
#if (SDRAM_PHY_PHASES > 4)
	case 7: sdram_dfii_pi7_baddress_write(value); break;
	case 6: sdram_dfii_pi6_baddress_write(value); break;
	case 5: sdram_dfii_pi5_baddress_write(value); break;
	case 4: sdram_dfii_pi4_baddress_write(value); break;
#endif
#if (SDRAM_PHY_PHASES > 2)
	case 3: sdram_dfii_pi3_baddress_write(value); break;
	case 2: sdram_dfii_pi2_baddress_write(value); break;
#endif
#if (SDRAM_PHY_PHASES > 1)
	case 1: sdram_dfii_pi1_baddress_write(value); break;
#endif
	default: sdram_dfii_pi0_baddress_write(value);
	}
}

static void sdram_dfii_pird_baddress_write(unsigned int value) {
	unsigned char rdphase = sdram_dfii_get_rdphase();
	sdram_dfii_pix_baddress_write(rdphase, value);
}

static void sdram_dfii_piwr_baddress_write(unsigned int value) {
	unsigned char wrphase = sdram_dfii_get_wrphase();
	sdram_dfii_pix_baddress_write(wrphase, value);
}

static void command_px(unsigned char phase, unsigned int value) {
#if (SDRAM_PHY_PHASES > 8)
	#error "More than 8 DFI phases not supported"
#endif
	switch (phase) {
#if (SDRAM_PHY_PHASES > 4)
	case 7: command_p7(value); break;
	case 6: command_p6(value); break;
	case 5: command_p5(value); break;
	case 4: command_p4(value); break;
#endif
#if (SDRAM_PHY_PHASES > 2)
	case 3: command_p3(value); break;
	case 2: command_p2(value); break;
#endif
#if (SDRAM_PHY_PHASES > 1)
	case 1: command_p1(value); break;
#endif
	default: command_p0(value);
	}
}

static void command_prd(unsigned int value) {
	unsigned char rdphase = sdram_dfii_get_rdphase();
	command_px(rdphase, value);
}

static void command_pwr(unsigned int value) {
	unsigned char wrphase = sdram_dfii_get_wrphase();
	command_px(wrphase, value);
}

#endif

/*-----------------------------------------------------------------------*/
/* Software/Hardware Control                                             */
/*-----------------------------------------------------------------------*/

#define DFII_CONTROL_SOFTWARE (DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N)
#define DFII_CONTROL_HARDWARE (DFII_CONTROL_SEL)

void sdram_software_control_on(void)
{
	unsigned int previous;
	previous = sdram_dfii_control_read();
	/* Switch DFII to software control */
	if (previous != DFII_CONTROL_SOFTWARE) {
		sdram_dfii_control_write(DFII_CONTROL_SOFTWARE);
		printf("Switching SDRAM to software control.\n");
	}

#if CSR_DDRPHY_EN_VTC_ADDR
	/* Disable Voltage/Temperature compensation */
	ddrphy_en_vtc_write(0);
#endif
}

void sdram_software_control_off(void)
{
	unsigned int previous;
	previous = sdram_dfii_control_read();
	/* Switch DFII to hardware control */
	if (previous != DFII_CONTROL_HARDWARE) {
		sdram_dfii_control_write(DFII_CONTROL_HARDWARE);
		printf("Switching SDRAM to hardware control.\n");
	}
#if CSR_DDRPHY_EN_VTC_ADDR
	/* Enable Voltage/Temperature compensation */
	ddrphy_en_vtc_write(1);
#endif
}

/*-----------------------------------------------------------------------*/
/*  Mode Register                                                        */
/*-----------------------------------------------------------------------*/

void sdram_mode_register_write(char reg, int value) {
	sdram_dfii_pi0_address_write(value);
	sdram_dfii_pi0_baddress_write(reg);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
}

#ifdef CSR_DDRPHY_BASE

/*-----------------------------------------------------------------------*/
/* Leveling Centering (Common for Read/Write Leveling)                   */
/*-----------------------------------------------------------------------*/

typedef void (*delay_callback)(int module);

static void sdram_activate_test_row(void) {
	sdram_dfii_pi0_address_write(0);
	sdram_dfii_pi0_baddress_write(0);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CS);
	cdelay(15);
}

static void sdram_precharge_test_row(void) {
	sdram_dfii_pi0_address_write(0);
	sdram_dfii_pi0_baddress_write(0);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
	cdelay(15);
}

// Count number of bits in a 32-bit word, faster version than a while loop
// see: https://www.johndcook.com/blog/2020/02/21/popcount/
static unsigned int popcount(unsigned int x) {
	x -= ((x >> 1) & 0x55555555);
	x = (x & 0x33333333) + ((x >> 2) & 0x33333333);
	x = (x + (x >> 4)) & 0x0F0F0F0F;
	x += (x >> 8);
	x += (x >> 16);
	return x & 0x0000003F;
}

static void print_scan_errors(unsigned int errors) {
#ifdef SDRAM_LEVELING_SCAN_DISPLAY_HEX_DIV
	// Display '.' for no errors, errors/div in hex if it is a single char, else show 'X'
	errors = errors / SDRAM_LEVELING_SCAN_DISPLAY_HEX_DIV;
	if (errors == 0)
		printf(".");
	else if (errors > 0xf)
		printf("X");
	else
		printf("%x", errors);
#else
		printf("%d", errors == 0);
#endif
}

#define READ_CHECK_TEST_PATTERN_MAX_ERRORS (8*SDRAM_PHY_PHASES*DFII_PIX_DATA_BYTES/SDRAM_PHY_MODULES)

static unsigned int sdram_write_read_check_test_pattern(int module, unsigned int seed) {
	int p, i;
	unsigned int errors;
	unsigned int prv;
	unsigned char tst[DFII_PIX_DATA_BYTES];
	unsigned char prs[SDRAM_PHY_PHASES][DFII_PIX_DATA_BYTES];

	/* Generate pseudo-random sequence */
	prv = seed;
	for(p=0;p<SDRAM_PHY_PHASES;p++) {
		for(i=0;i<DFII_PIX_DATA_BYTES;i++) {
			prv = lfsr(32, prv);
			prs[p][i] = prv;
		}
	}

	/* Activate */
	sdram_activate_test_row();

	/* Write pseudo-random sequence */
	for(p=0;p<SDRAM_PHY_PHASES;p++)
		csr_wr_buf_uint8(sdram_dfii_pix_wrdata_addr(p), prs[p], DFII_PIX_DATA_BYTES);
	sdram_dfii_piwr_address_write(0);
	sdram_dfii_piwr_baddress_write(0);
	command_pwr(DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS|DFII_COMMAND_WRDATA);
	cdelay(15);

#ifdef SDRAM_PHY_ECP5DDRPHY
	ddrphy_burstdet_clr_write(1);
#endif

	/* Read/Check pseudo-random sequence */
	sdram_dfii_pird_address_write(0);
	sdram_dfii_pird_baddress_write(0);
	command_prd(DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA);
	cdelay(15);

	/* Precharge */
	sdram_precharge_test_row();

	errors = 0;
	for(p=0;p<SDRAM_PHY_PHASES;p++) {
		/* Read back test pattern */
		csr_rd_buf_uint8(sdram_dfii_pix_rddata_addr(p), tst, DFII_PIX_DATA_BYTES);
		/* Verify bytes matching current 'module' */
		for (int i = 0; i < DFII_PIX_DATA_BYTES; ++i) {
			int j = p * DFII_PIX_DATA_BYTES + i;
#if SDRAM_PHY_DQ_DQS_RATIO == 4
			if (j % (SDRAM_PHY_MODULES/2) == ((SDRAM_PHY_MODULES-1)/2)-(module/2)) {
				if(module % 2) {
					errors += popcount((prs[p][i] & 0xf0) ^ (tst[i] & 0xf0));
				} else {
					errors += popcount((prs[p][i] & 0x0f) ^ (tst[i] & 0x0f));
				}
			}
#else
			if (j % SDRAM_PHY_MODULES == SDRAM_PHY_MODULES-1-module) {
				errors += popcount(prs[p][i] ^ tst[i]);
			}
#endif
		}
	}

#ifdef SDRAM_PHY_ECP5DDRPHY
	if (((ddrphy_burstdet_seen_read() >> module) & 0x1) != 1)
		errors += 1;
#endif

	return errors;
}

static void sdram_leveling_center_module(
	int module, int show_short, int show_long, delay_callback rst_delay, delay_callback inc_delay)
{
	int i;
	int show;
	int working;
	unsigned int errors;
	int delay, delay_mid, delay_range;
	int delay_min = -1, delay_max = -1;

	if (show_long)
		printf("m%d: |", module);

	/* Find smallest working delay */
	delay = 0;
	rst_delay(module);
	while(1) {
		errors  = sdram_write_read_check_test_pattern(module, 42);
		errors += sdram_write_read_check_test_pattern(module, 84);
		working = errors == 0;
		show = show_long;
#if SDRAM_PHY_DELAYS > 32
		show = show && (delay%16 == 0);
#endif
		if (show)
			print_scan_errors(errors);
		if(working && delay_min < 0) {
			delay_min = delay;
			break;
		}
		delay++;
		if(delay >= SDRAM_PHY_DELAYS)
			break;
		inc_delay(module);
	}

	/* Get a bit further into the working zone */
#if SDRAM_PHY_DELAYS > 32
	#define	SDRAM_PHY_DELAY_JUMP 16
#elif SDRAM_PHY_DELAYS > 8
	#define SDRAM_PHY_DELAY_JUMP 4
#else
	#define SDRAM_PHY_DELAY_JUMP 1
#endif
	for(i=0;i<SDRAM_PHY_DELAY_JUMP;i++) {
		delay += 1;
		inc_delay(module);
	}

	/* Find largest working delay */
	while(1) {
		errors  = sdram_write_read_check_test_pattern(module, 42);
		errors += sdram_write_read_check_test_pattern(module, 84);
		working = errors == 0;
		show = show_long;
#if SDRAM_PHY_DELAYS > 32
		show = show && (delay%16 == 0);
#endif
		if (show)
			print_scan_errors(errors);
		if(!working && delay_max < 0) {
			delay_max = delay;
		}
		delay++;
		if(delay >= SDRAM_PHY_DELAYS)
			break;
		inc_delay(module);
	}
	if(delay_max < 0) {
		delay_max = delay;
	}

	if (show_long)
		printf("| ");

	delay_mid   = (delay_min+delay_max)/2 % SDRAM_PHY_DELAYS;
	delay_range = (delay_max-delay_min)/2;
	if (show_short) {
		if (delay_min < 0)
			printf("delays: -");
		else
			printf("delays: %02d+-%02d", delay_mid, delay_range);
	}

	if (show_long)
		printf("\n");

	/* Set delay to the middle and check */
	if (delay_min >= 0) {
		int retries = 8; /* Do N configs/checks and give up if failing */
		while (retries > 0) {
			/* Set delay. */
			rst_delay(module);
			cdelay(100);
			for(i = 0; i < delay_mid; i++) {
				inc_delay(module);
				cdelay(100);
			}

			/* Check */
			errors  = sdram_write_read_check_test_pattern(module, 42);
			errors += sdram_write_read_check_test_pattern(module, 84);
			if (errors == 0)
				break;
			retries--;
		}
	}
}

/*-----------------------------------------------------------------------*/
/* Write Leveling                                                        */
/*-----------------------------------------------------------------------*/

int _sdram_tck_taps;
int _sdram_write_leveling_bitslips[16];

#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE

int _sdram_write_leveling_cmd_scan  = 1;
int _sdram_write_leveling_cmd_delay = 0;
int _sdram_write_leveling_dat_delays[16];

int _sdram_write_leveling_cdly_range_start = -1;
int _sdram_write_leveling_cdly_range_end   = -1;

static void sdram_write_leveling_on(void)
{
	// Flip write leveling bit in the Mode Register, as it is disabled by default
	sdram_dfii_pi0_address_write(DDRX_MR_WRLVL_RESET ^ (1 << DDRX_MR_WRLVL_BIT));
	sdram_dfii_pi0_baddress_write(DDRX_MR_WRLVL_ADDRESS);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);

#ifdef SDRAM_PHY_DDR4_RDIMM
	sdram_dfii_pi0_address_write((DDRX_MR_WRLVL_RESET ^ (1 << DDRX_MR_WRLVL_BIT)) ^ 0x2BF8) ;
	sdram_dfii_pi0_baddress_write(DDRX_MR_WRLVL_ADDRESS ^ 0xF);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
#endif

	ddrphy_wlevel_en_write(1);
}

static void sdram_write_leveling_off(void)
{
	sdram_dfii_pi0_address_write(DDRX_MR_WRLVL_RESET);
	sdram_dfii_pi0_baddress_write(DDRX_MR_WRLVL_ADDRESS);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);

#ifdef SDRAM_PHY_DDR4_RDIMM
	sdram_dfii_pi0_address_write(DDRX_MR_WRLVL_RESET ^ 0x2BF8);
	sdram_dfii_pi0_baddress_write(DDRX_MR_WRLVL_ADDRESS ^ 0xF);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
#endif

	ddrphy_wlevel_en_write(0);
}

void sdram_write_leveling_rst_cmd_delay(int show) {
	_sdram_write_leveling_cmd_scan = 1;
	if (show)
		printf("Reseting Cmd delay\n");
}

void sdram_write_leveling_force_cmd_delay(int taps, int show) {
	int i;
	_sdram_write_leveling_cmd_scan  = 0;
	_sdram_write_leveling_cmd_delay = taps;
	if (show)
		printf("Forcing Cmd delay to %d taps\n", taps);
	ddrphy_cdly_rst_write(1);
	cdelay(100);
	for (i=0; i<taps; i++) {
		ddrphy_cdly_inc_write(1);
		cdelay(100);
	}
}

void sdram_write_leveling_rst_dat_delay(int module, int show) {
	_sdram_write_leveling_dat_delays[module] = -1;
	if (show)
		printf("Reseting Dat delay of module %d\n", module);
}

void sdram_write_leveling_force_dat_delay(int module, int taps, int show) {
	_sdram_write_leveling_dat_delays[module] = taps;
	if (show)
		printf("Forcing Dat delay of module %d to %d taps\n", module, taps);
}

void sdram_write_leveling_rst_bitslip(int module, int show) {
	_sdram_write_leveling_bitslips[module] = -1;
	if (show)
		printf("Reseting Bitslip of module %d\n", module);
}

void sdram_write_leveling_force_bitslip(int module, int bitslip, int show) {
	_sdram_write_leveling_bitslips[module] = bitslip;
	if (show)
		printf("Forcing Bitslip of module %d to %d\n", module, bitslip);
}

static void sdram_write_leveling_rst_delay(int module) {
	/* Select module */
	ddrphy_dly_sel_write(1 << module);

	/* Reset DQ delay */
	ddrphy_wdly_dq_rst_write(1);

#if defined(SDRAM_PHY_USDDRPHY) || defined(SDRAM_PHY_USPDDRPHY)
	/* Reset DQS delay */
	while (ddrphy_wdly_dqs_inc_count_read() != 0) {
		ddrphy_wdly_dqs_inc_write(1);
		cdelay(100);
	}
#else
	/* Reset DQ/DQS delay */
	ddrphy_wdly_dq_rst_write(1);
	ddrphy_wdly_dqs_rst_write(1);
	cdelay(100);
#endif

	/* Un-select module */
	ddrphy_dly_sel_write(0);
}

static void sdram_write_leveling_inc_delay(int module) {
	/* Select module */
	ddrphy_dly_sel_write(1 << module);

	/* Increment DQ/DQS delay */
	ddrphy_wdly_dq_inc_write(1);
	ddrphy_wdly_dqs_inc_write(1);

	/* Un-select module */
	ddrphy_dly_sel_write(0);
}

static int sdram_write_leveling_scan(int *delays, int loops, int show)
{
	int i, j, k;

	int err_ddrphy_wdly;

	unsigned char taps_scan[SDRAM_PHY_DELAYS];

	int one_window_active;
	int one_window_start, one_window_best_start;
	int one_window_count, one_window_best_count;

	unsigned char buf[DFII_PIX_DATA_BYTES];

	int ok;

	err_ddrphy_wdly = SDRAM_PHY_DELAYS - _sdram_tck_taps/4;

	sdram_write_leveling_on();
	cdelay(100);
	for(i=0;i<SDRAM_PHY_MODULES;i++) {
		if (show)
			printf("  m%d: |", i);

		/* Reset delay */
		sdram_write_leveling_rst_delay(i);
		cdelay(100);

		/* Scan write delay taps */
		for(j=0;j<err_ddrphy_wdly;j++) {
			int zero_count = 0;
			int one_count = 0;
			int show_iter = show;
#if SDRAM_PHY_DELAYS > 32
			show_iter = (j%16 == 0) && show;
#endif
			for (k=0; k<loops; k++) {
				ddrphy_wlevel_strobe_write(1);
				cdelay(100);
				csr_rd_buf_uint8(sdram_dfii_pix_rddata_addr(0), buf, DFII_PIX_DATA_BYTES);
#if SDRAM_PHY_DQ_DQS_RATIO == 4
				if (buf[SDRAM_PHY_MODULES-1-(i/2)] != 0)
#else
				if (buf[SDRAM_PHY_MODULES-1-i] != 0)
#endif
					one_count++;
				else
					zero_count++;
			}
			if (one_count > zero_count)
				taps_scan[j] = 1;
			else
				taps_scan[j] = 0;
			if (show_iter)
				printf("%d", taps_scan[j]);
			sdram_write_leveling_inc_delay(i);
			cdelay(100);
		}
		if (show)
			printf("|");

		/* Find longer 1 window and set delay at the 0/1 transition */
		one_window_active = 0;
		one_window_start = 0;
		one_window_count = 0;
		one_window_best_start = 0;
		one_window_best_count = -1;
		delays[i] = -1;
		for(j=0;j<err_ddrphy_wdly;j++) {
			if (one_window_active) {
				if ((taps_scan[j] == 0) | (j == err_ddrphy_wdly - 1)) {
					one_window_active = 0;
					one_window_count = j - one_window_start;
					if (one_window_count > one_window_best_count) {
						one_window_best_start = one_window_start;
						one_window_best_count = one_window_count;
					}
				}
			} else {
				if (taps_scan[j]) {
					one_window_active = 1;
					one_window_start = j;
				}
			}
		}

		/* Reset delay */
		sdram_write_leveling_rst_delay(i);
		cdelay(100);

		/* Use forced delay if configured */
		if (_sdram_write_leveling_dat_delays[i] >= 0) {
			delays[i] = _sdram_write_leveling_dat_delays[i];

			/* Configure write delay */
			for(j=0; j<delays[i]; j++)  {
				sdram_write_leveling_inc_delay(i);
				cdelay(100);
			}
		/* Succeed only if the start of a 1s window has been found: */
		} else if (
			/* Start of 1s window directly seen after 0. */
			((one_window_best_start) > 0 && (one_window_best_count > 0)) ||
			/* Start of 1s window indirectly seen before 0. */
			((one_window_best_start == 0) && (one_window_best_count > _sdram_tck_taps/4))
			){
#if SDRAM_PHY_DELAYS > 32
			/* Ensure write delay is just before transition */
			one_window_start -= min(one_window_start, 16);
#endif
			delays[i] = one_window_best_start;

			/* Configure write delay */
			for(j=0; j<delays[i]; j++) {
				sdram_write_leveling_inc_delay(i);
				cdelay(100);
			}
		}
		if (show) {
			if (delays[i] == -1)
				printf(" delay: -\n");
			else
				printf(" delay: %02d\n", delays[i]);
		}
	}

	sdram_write_leveling_off();

	ok = 1;
	for(i=SDRAM_PHY_MODULES-1;i>=0;i--) {
		if(delays[i] < 0)
			ok = 0;
	}

	return ok;
}

static void sdram_write_leveling_find_cmd_delay(unsigned int *best_error, unsigned int *best_count, int *best_cdly,
		int cdly_start, int cdly_stop, int cdly_step)
{
	int cdly;
	int cdly_actual = 0;
	int delays[SDRAM_PHY_MODULES];
#ifndef SDRAM_WRITE_LEVELING_CMD_DELAY_DEBUG
	int ok;
#endif

	/* Scan through the range */
	ddrphy_cdly_rst_write(1);
	cdelay(100);
	for (cdly = cdly_start; cdly < cdly_stop; cdly += cdly_step) {
		/* Increment cdly to current value */
		while (cdly_actual < cdly) {
			ddrphy_cdly_inc_write(1);
			cdelay(100);
			cdly_actual++;
		}

		/* Write level using this delay */
#ifdef SDRAM_WRITE_LEVELING_CMD_DELAY_DEBUG
		printf("Cmd/Clk delay: %d\n", cdly);
		sdram_write_leveling_scan(delays, 8, 1);
#else
		ok = sdram_write_leveling_scan(delays, 8, 0);
#endif
		/* Use the mean of delays for error calulation */
		int delay_mean  = 0;
		int delay_count = 0;
		for (int i=0; i < SDRAM_PHY_MODULES; ++i) {
			if (delays[i] != -1) {
				delay_mean  += delays[i] + _sdram_tck_taps/4;
				delay_count += 1;
			}
		}
		if (delay_count != 0)
			delay_mean /= delay_count;

		/* We want the higher number of valid modules and delay to be centered */
		int ideal_delay = (SDRAM_PHY_DELAYS - _sdram_tck_taps/4)/2;
		int error = ideal_delay - delay_mean;
		if (error < 0)
			error *= -1;

		if (delay_count >= *best_count) {
			if (error < *best_error) {
				*best_cdly  = cdly;
				*best_error = error;
				*best_count = delay_count;
			}
		}
#ifdef SDRAM_WRITE_LEVELING_CMD_DELAY_DEBUG
		printf("Delay mean: %d, ideal: %d\n", delay_mean, ideal_delay);
#else
		printf("%d", ok);
#endif
	}
}

int sdram_write_leveling(void)
{
	int delays[SDRAM_PHY_MODULES];
	unsigned int best_error = ~0u;
	unsigned int best_count = 0;
	int best_cdly = -1;
	int cdly_range_start;
	int cdly_range_end;
	int cdly_range_step;

	_sdram_tck_taps = ddrphy_half_sys8x_taps_read()*4;
	printf("  tCK equivalent taps: %d\n", _sdram_tck_taps);

	if (_sdram_write_leveling_cmd_scan) {
		/* Center write leveling by varying cdly. Searching through all possible
		 * values is slow, but we can use a simple optimization method of iterativly
		 * scanning smaller ranges with decreasing step */
		if (_sdram_write_leveling_cdly_range_start != -1)
			cdly_range_start = _sdram_write_leveling_cdly_range_start;
		else
			cdly_range_start = 0;
		if (_sdram_write_leveling_cdly_range_end != -1)
			cdly_range_end = _sdram_write_leveling_cdly_range_end;
		else
			cdly_range_end = _sdram_tck_taps/2; /* Limit Clk/Cmd scan to 1/2 tCK */

		printf("  Cmd/Clk scan (%d-%d)\n", cdly_range_start, cdly_range_end);
		if (SDRAM_PHY_DELAYS > 32)
			cdly_range_step = SDRAM_PHY_DELAYS/8;
		else
			cdly_range_step = 1;
		while (cdly_range_step > 0) {
			printf("  |");
			sdram_write_leveling_find_cmd_delay(&best_error, &best_count, &best_cdly,
					cdly_range_start, cdly_range_end, cdly_range_step);

			/* Small optimization - stop if we have zero error */
			if (best_error == 0)
				break;

			/* Use best result as the middle of next range */
			cdly_range_start = best_cdly - cdly_range_step;
			cdly_range_end = best_cdly + cdly_range_step + 1;
			if (cdly_range_start < 0)
				cdly_range_start = 0;
			if (cdly_range_end > 512)
				cdly_range_end = 512;

			cdly_range_step /= 4;
		}
		printf("| best: %d\n", best_cdly);
	} else {
		best_cdly = _sdram_write_leveling_cmd_delay;
	}
	printf("  Setting Cmd/Clk delay to %d taps.\n", best_cdly);
	/* Set working or forced delay */
	if (best_cdly >= 0) {
		ddrphy_cdly_rst_write(1);
		cdelay(100);
		for (int i = 0; i < best_cdly; ++i) {
			ddrphy_cdly_inc_write(1);
			cdelay(100);
		}
	}

	printf("  Data scan:\n");

	/* Re-run write leveling the final time */
	if (!sdram_write_leveling_scan(delays, 128, 1))
		return 0;

	return best_cdly >= 0;
}

#endif /*  SDRAM_PHY_WRITE_LEVELING_CAPABLE */

/*-----------------------------------------------------------------------*/
/* Read Leveling                                                         */
/*-----------------------------------------------------------------------*/

static void sdram_read_leveling_rst_delay(int module) {
	/* Select module */
	ddrphy_dly_sel_write(1 << module);

	/* Reset delay */
	ddrphy_rdly_dq_rst_write(1);

	/* Un-select module */
	ddrphy_dly_sel_write(0);

#ifdef SDRAM_PHY_ECP5DDRPHY
	/* Sync all DQSBUFM's, By toggling all dly_sel (DQSBUFM.PAUSE) lines. */
	ddrphy_dly_sel_write(0xff);
	ddrphy_dly_sel_write(0);
#endif
}

static void sdram_read_leveling_inc_delay(int module) {
	/* Select module */
	ddrphy_dly_sel_write(1 << module);

	/* Increment delay */
	ddrphy_rdly_dq_inc_write(1);

	/* Un-select module */
	ddrphy_dly_sel_write(0);

#ifdef SDRAM_PHY_ECP5DDRPHY
	/* Sync all DQSBUFM's, By toggling all dly_sel (DQSBUFM.PAUSE) lines. */
	ddrphy_dly_sel_write(0xff);
	ddrphy_dly_sel_write(0);
#endif
}

static void sdram_read_leveling_rst_bitslip(char m)
{
	/* Select module */
	ddrphy_dly_sel_write(1 << m);

	/* Reset delay */
	ddrphy_rdly_dq_bitslip_rst_write(1);

	/* Un-select module */
	ddrphy_dly_sel_write(0);
}


static void sdram_read_leveling_inc_bitslip(char m)
{
	/* Select module */
	ddrphy_dly_sel_write(1 << m);

	/* Increment delay */
	ddrphy_rdly_dq_bitslip_write(1);

	/* Un-select module */
	ddrphy_dly_sel_write(0);
}

static unsigned int sdram_read_leveling_scan_module(int module, int bitslip, int show)
{
	const unsigned int max_errors = 2*READ_CHECK_TEST_PATTERN_MAX_ERRORS;
	int i;
	unsigned int score;
	unsigned int errors;

	/* Check test pattern for each delay value */
	score = 0;
	if (show)
		printf("  m%d, b%02d: |", module, bitslip);
	sdram_read_leveling_rst_delay(module);
	for(i=0;i<SDRAM_PHY_DELAYS;i++) {
		int working;
		int _show = show;
#if SDRAM_PHY_DELAYS > 32
		_show = (i%16 == 0) & show;
#endif
		errors  = sdram_write_read_check_test_pattern(module, 42);
		errors += sdram_write_read_check_test_pattern(module, 84);
		working = errors == 0;
		/* When any scan is working then the final score will always be higher then if no scan was working */
		score += (working * max_errors*SDRAM_PHY_DELAYS) + (max_errors - errors);
		if (_show) {
			print_scan_errors(errors);
		}
		sdram_read_leveling_inc_delay(module);
	}
	if (show)
		printf("| ");

	return score;
}

#endif /* CSR_DDRPHY_BASE */

#endif /* CSR_SDRAM_BASE */

#ifdef CSR_SDRAM_BASE

#if defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) || defined(SDRAM_PHY_READ_LEVELING_CAPABLE)

void sdram_read_leveling(void)
{
	int module;
	int bitslip;
	unsigned int score;
	unsigned int best_score;
	int best_bitslip;

	for(module=0; module<SDRAM_PHY_MODULES; module++) {
		/* Scan possible read windows */
		best_score = 0;
		best_bitslip = 0;
		sdram_read_leveling_rst_bitslip(module);
		for(bitslip=0; bitslip<SDRAM_PHY_BITSLIPS; bitslip++) {
			/* Compute score */
			score = sdram_read_leveling_scan_module(module, bitslip, 1);
			sdram_leveling_center_module(module, 1, 0,
				sdram_read_leveling_rst_delay, sdram_read_leveling_inc_delay);
			printf("\n");
			if (score > best_score) {
				best_bitslip = bitslip;
				best_score = score;
			}
			/* Exit */
			if (bitslip == SDRAM_PHY_BITSLIPS-1)
				break;
			/* Increment bitslip */
			sdram_read_leveling_inc_bitslip(module);
		}

		/* Select best read window */
		printf("  best: m%d, b%02d ", module, best_bitslip);
		sdram_read_leveling_rst_bitslip(module);
		for (bitslip=0; bitslip<best_bitslip; bitslip++)
			sdram_read_leveling_inc_bitslip(module);

		/* Re-do leveling on best read window*/
		sdram_leveling_center_module(module, 1, 0,
			sdram_read_leveling_rst_delay, sdram_read_leveling_inc_delay);
		printf("\n");
	}
}

/*-----------------------------------------------------------------------*/
/* Write latency calibration                                             */
/*-----------------------------------------------------------------------*/

#ifdef SDRAM_PHY_WRITE_LATENCY_CALIBRATION_CAPABLE

static void sdram_write_latency_calibration(void) {
	int i;
	int module;
	int bitslip;
	unsigned int score;
	unsigned int subscore;
	unsigned int best_score;
	int best_bitslip;

	for(module=0; module<SDRAM_PHY_MODULES; module++) {
		/* Scan possible write windows */
		best_score   = 0;
		best_bitslip = -1;
		for(bitslip=0; bitslip<SDRAM_PHY_BITSLIPS; bitslip+=2) { /* +2 for tCK steps */
#ifdef SDRAM_WRITE_LATENCY_CALIBRATION_DEBUG
			printf("m%d wb%02d:\n", module, bitslip);
#endif
			score = 0;
			/* Select module */
			ddrphy_dly_sel_write(1 << module);
			/* Reset bitslip */
			ddrphy_wdly_dq_bitslip_rst_write(1);
			for (i=0; i<bitslip; i++) {
				ddrphy_wdly_dq_bitslip_write(1);
			}
			/* Un-select module */
			ddrphy_dly_sel_write(0);
			score = 0;
			sdram_read_leveling_rst_bitslip(module);
			for(i=0; i<SDRAM_PHY_BITSLIPS; i++) {
				/* Compute score */
#ifdef SDRAM_WRITE_LATENCY_CALIBRATION_DEBUG
				subscore = sdram_read_leveling_scan_module(module, i, 1);
				printf("\n");
#else
				subscore = sdram_read_leveling_scan_module(module, i, 0);
#endif
				score = subscore > score ? subscore : score;
				/* Increment bitslip */
				sdram_read_leveling_inc_bitslip(module);
			}
			if (score > best_score) {
				best_bitslip = bitslip;
				best_score = score;
			}
		}

		#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE
		if (_sdram_write_leveling_bitslips[module] < 0)
			bitslip = best_bitslip;
		else
			bitslip = _sdram_write_leveling_bitslips[module];
		#else
			bitslip = best_bitslip;
		#endif
		if (bitslip == -1)
			printf("m%d:- ", module);
		else
			printf("m%d:%d ", module, bitslip);
#ifdef SDRAM_WRITE_LATENCY_CALIBRATION_DEBUG
		printf("\n");
#endif

		/* Select best write window */
		ddrphy_dly_sel_write(1 << module);

		/* Reset bitslip */
		ddrphy_wdly_dq_bitslip_rst_write(1);
		for (i=0; i<bitslip; i++) {
			ddrphy_wdly_dq_bitslip_write(1);
		}
		/* Un-select module */
		ddrphy_dly_sel_write(0);
	}
	printf("\n");
}

#endif

/*-----------------------------------------------------------------------*/
/* Write DQ-DQS training                                                 */
/*-----------------------------------------------------------------------*/

#ifdef SDRAM_PHY_WRITE_DQ_DQS_TRAINING_CAPABLE

static void sdram_write_dq_dqs_training_rst_delay(int module) {
	/* Select module */
	ddrphy_dly_sel_write(1 << module);

#if defined(SDRAM_PHY_USDDRPHY) || defined(SDRAM_PHY_USPDDRPHY)
	/* Reset DQ delay */
	int dq_count = ddrphy_wdly_dqs_inc_count_read();
	while (dq_count != SDRAM_PHY_DELAYS) {
		ddrphy_wdly_dq_inc_write(1);
		cdelay(100);
		dq_count++;
	}
#else
	/* Reset DQ delay */
	ddrphy_wdly_dq_rst_write(1);
	cdelay(100);
#endif

	/* Un-select module */
	ddrphy_dly_sel_write(0);
}

static void sdram_write_dq_dqs_training_inc_delay(int module) {
	/* Select module */
	ddrphy_dly_sel_write(1 << module);
	/* Increment delay */
	ddrphy_wdly_dq_inc_write(1);
	cdelay(100);
	/* Un-select module */
	ddrphy_dly_sel_write(0);
}

static void sdram_read_leveling_best_bitslip(int module)
{
	unsigned int score;
	int bitslip;
	int best_bitslip = 0;
	unsigned int best_score = 0;

	sdram_read_leveling_rst_bitslip(module);
	for(bitslip=0; bitslip<SDRAM_PHY_BITSLIPS; bitslip++) {
		score = sdram_read_leveling_scan_module(module, bitslip, 0);
		sdram_leveling_center_module(module, 0, 0,
			sdram_read_leveling_rst_delay, sdram_read_leveling_inc_delay);
		if (score > best_score) {
			best_bitslip = bitslip;
			best_score = score;
		}
		if (bitslip == SDRAM_PHY_BITSLIPS-1)
			break;
		sdram_read_leveling_inc_bitslip(module);
	}

	/* Select best read window and re-center it */
	sdram_read_leveling_rst_bitslip(module);
	for (bitslip=0; bitslip<best_bitslip; bitslip++)
		sdram_read_leveling_inc_bitslip(module);
	sdram_leveling_center_module(module, 0, 0,
		sdram_read_leveling_rst_delay, sdram_read_leveling_inc_delay);
}

static void sdram_write_dq_dqs_training(void)
{
	int module;

	for(module=0; module<SDRAM_PHY_MODULES; module++) {
		/* Find best bitslip */
		sdram_read_leveling_best_bitslip(module);
		/* Center DQ-DQS window */
		sdram_leveling_center_module(module, 1, 1,
			sdram_write_dq_dqs_training_rst_delay, sdram_write_dq_dqs_training_inc_delay);
	}
}

#endif /* SDRAM_PHY_WRITE_DQ_DQS_TRAINING_CAPABLE */

/*-----------------------------------------------------------------------*/
/* Leveling                                                              */
/*-----------------------------------------------------------------------*/

int sdram_leveling(void)
{
	int module;
	sdram_software_control_on();

	for(module=0; module<SDRAM_PHY_MODULES; module++) {
#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE
		sdram_write_leveling_rst_delay(module);
#endif
		sdram_read_leveling_rst_delay(module);
		sdram_read_leveling_rst_bitslip(module);
	}

#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE
	printf("Write leveling:\n");
	sdram_write_leveling();
#endif

#ifdef SDRAM_PHY_WRITE_LATENCY_CALIBRATION_CAPABLE
	printf("Write latency calibration:\n");
	sdram_write_latency_calibration();
#endif

#ifdef SDRAM_PHY_WRITE_DQ_DQS_TRAINING_CAPABLE
	printf("Write DQ-DQS training:\n");
	sdram_write_dq_dqs_training();
#endif

#ifdef SDRAM_PHY_READ_LEVELING_CAPABLE
	printf("Read leveling:\n");
	sdram_read_leveling();
#endif

	sdram_software_control_off();

	return 1;
}
#endif

/*-----------------------------------------------------------------------*/
/* Initialization                                                        */
/*-----------------------------------------------------------------------*/

int sdram_init(void)
{
	/* Reset Cmd/Dat delays */
#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE
	int i;
	sdram_write_leveling_rst_cmd_delay(0);
	for (i=0; i<16; i++) sdram_write_leveling_rst_dat_delay(i, 0);
	for (i=0; i<16; i++) sdram_write_leveling_rst_bitslip(i, 0);
#endif
	/* Reset Read/Write phases */
#ifdef CSR_DDRPHY_RDPHASE_ADDR
	ddrphy_rdphase_write(SDRAM_PHY_RDPHASE);
#endif
#ifdef CSR_DDRPHY_WRPHASE_ADDR
	ddrphy_wrphase_write(SDRAM_PHY_WRPHASE);
#endif
	/* Set Cmd delay if enforced at build time */
#ifdef SDRAM_PHY_CMD_DELAY
	_sdram_write_leveling_cmd_scan  = 0;
	_sdram_write_leveling_cmd_delay = SDRAM_PHY_CMD_DELAY;
#endif
	printf("Initializing SDRAM @0x%08lx...\n", MAIN_RAM_BASE);
	sdram_software_control_on();
#if CSR_DDRPHY_RST_ADDR
	ddrphy_rst_write(1);
	cdelay(1000);
	ddrphy_rst_write(0);
	cdelay(1000);
#endif

#ifdef CSR_DDRCTRL_BASE
	ddrctrl_init_done_write(0);
	ddrctrl_init_error_write(0);
#endif
	init_sequence();
#if defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) || defined(SDRAM_PHY_READ_LEVELING_CAPABLE)
	sdram_leveling();
#endif
	sdram_software_control_off();
#ifndef SDRAM_TEST_DISABLE
	if(!memtest((unsigned int *) MAIN_RAM_BASE, MEMTEST_DATA_SIZE)) {
#ifdef CSR_DDRCTRL_BASE
		ddrctrl_init_error_write(1);
		ddrctrl_init_done_write(1);
#endif
		return 0;
	}
	memspeed((unsigned int *) MAIN_RAM_BASE, MEMTEST_DATA_SIZE, false, 0);
#endif
#ifdef CSR_DDRCTRL_BASE
	ddrctrl_init_done_write(1);
#endif

	return 1;
}

/*-----------------------------------------------------------------------*/
/* Debugging                                                             */
/*-----------------------------------------------------------------------*/

#ifdef SDRAM_DEBUG

#define SDRAM_DEBUG_STATS_NUM_RUNS 10
#define SDRAM_DEBUG_STATS_MEMTEST_SIZE MEMTEST_DATA_SIZE

#ifdef SDRAM_DEBUG_READBACK_MEM_ADDR
#ifndef SDRAM_DEBUG_READBACK_MEM_SIZE
#error "Provide readback memory size via SDRAM_DEBUG_READBACK_MEM_SIZE"
#endif
#define SDRAM_DEBUG_READBACK_VERBOSE 1

#define SDRAM_DEBUG_READBACK_COUNT 3
#define SDRAM_DEBUG_READBACK_MEMTEST_SIZE MEMTEST_DATA_SIZE

#define _SINGLE_READBACK (SDRAM_DEBUG_READBACK_MEM_SIZE/SDRAM_DEBUG_READBACK_COUNT)
#define _READBACK_ERRORS_SIZE (_SINGLE_READBACK - sizeof(struct readback))
#define SDRAM_DEBUG_READBACK_LEN (_READBACK_ERRORS_SIZE / sizeof(struct memory_error))
#endif

static int sdram_debug_error_stats_on_error(
	unsigned int addr, unsigned int rdata, unsigned int refdata, void *arg)
{
	struct error_stats *stats = (struct error_stats *) arg;
	struct memory_error error = {
		.addr = addr,
		.data = rdata,
		.ref = refdata,
	};
	error_stats_update(stats, error);
	return 0;
}

static void sdram_debug_error_stats(void) {
	printf("Running initial memtest to fill memory ...\n");
	memtest_data((unsigned int *) MAIN_RAM_BASE, SDRAM_DEBUG_STATS_MEMTEST_SIZE, 1, NULL);

	struct error_stats stats;
	error_stats_init(&stats);

	struct memtest_config config = {
		.show_progress = 0,
		.read_only = 1,
		.on_error = sdram_debug_error_stats_on_error,
		.arg = &stats,
	};

	printf("Running read-only memtests ... \n");
	for (int i = 0; i < SDRAM_DEBUG_STATS_NUM_RUNS; ++i) {
		printf("Running read-only memtest %3d/%3d ... \r", i + 1, SDRAM_DEBUG_STATS_NUM_RUNS);
		memtest_data((unsigned int *) MAIN_RAM_BASE, SDRAM_DEBUG_STATS_MEMTEST_SIZE, 1, &config);
	}

	printf("\n");
	error_stats_print(&stats);
}

#ifdef SDRAM_DEBUG_READBACK_MEM_ADDR
static int sdram_debug_readback_on_error(
	unsigned int addr, unsigned int rdata, unsigned int refdata, void *arg)
{
	struct readback *readback = (struct readback *) arg;
	struct memory_error error = {
		.addr = addr,
		.data = rdata,
		.ref = refdata,
	};
	// run only as long as we have space for new entries
	return readback_add(readback, SDRAM_DEBUG_READBACK_LEN, error) != 1;
}

static void sdram_debug_readback(void)
{
	printf("Using storage @0x%08x with size 0x%08x for %d readbacks.\n",
		SDRAM_DEBUG_READBACK_MEM_ADDR, SDRAM_DEBUG_READBACK_MEM_SIZE, SDRAM_DEBUG_READBACK_COUNT);

	printf("Running initial memtest to fill memory ...\n");
	memtest_data((unsigned int *) MAIN_RAM_BASE, SDRAM_DEBUG_READBACK_MEMTEST_SIZE, 1, NULL);

	for (int i = 0; i < SDRAM_DEBUG_READBACK_COUNT; ++i) {
		struct readback *readback = (struct readback *)
			(SDRAM_DEBUG_READBACK_MEM_ADDR + i * READBACK_SIZE(SDRAM_DEBUG_READBACK_LEN));
		readback_init(readback);

		struct memtest_config config = {
			.show_progress = 0,
			.read_only = 1,
			.on_error = sdram_debug_readback_on_error,
			.arg = readback,
		};

		printf("Running readback %3d/%3d ... \r", i + 1, SDRAM_DEBUG_READBACK_COUNT);
		memtest_data((unsigned int *) MAIN_RAM_BASE, SDRAM_DEBUG_READBACK_MEMTEST_SIZE, 1, &config);
	}
	printf("\n");


	// Iterate over all combinations
	for (int i = 0; i < SDRAM_DEBUG_READBACK_COUNT; ++i) {
		struct readback *first = (struct readback *)
			(SDRAM_DEBUG_READBACK_MEM_ADDR + i * READBACK_SIZE(SDRAM_DEBUG_READBACK_LEN));

		for (int j = i + 1; j < SDRAM_DEBUG_READBACK_COUNT; ++j) {
			int nums[] = {i, j};
			struct readback *readbacks[] = {
				(struct readback *) (SDRAM_DEBUG_READBACK_MEM_ADDR + i * READBACK_SIZE(SDRAM_DEBUG_READBACK_LEN)),
				(struct readback *) (SDRAM_DEBUG_READBACK_MEM_ADDR + j * READBACK_SIZE(SDRAM_DEBUG_READBACK_LEN)),
			};

			// Compare i vs j and j vs i
			for (int k = 0; k < 2; ++k) {
				printf("Comparing readbacks %d vs %d:\n", nums[k], nums[1 - k]);
				int missing = readback_compare(readbacks[k], readbacks[1 - k], SDRAM_DEBUG_READBACK_VERBOSE);
				if (missing == 0)
					printf("  OK\n");
				else
					printf("  N missing = %d\n", missing);
			}
		}
	}
}
#endif

void sdram_debug(void)
{
#if defined(SDRAM_DEBUG_STATS_NUM_RUNS) && SDRAM_DEBUG_STATS_NUM_RUNS > 0
	printf("\nError stats:\n");
	sdram_debug_error_stats();
#endif

#ifdef SDRAM_DEBUG_READBACK_MEM_ADDR
	printf("\nReadback:\n");
	sdram_debug_readback();
#endif
}
#endif

#endif
