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

#include <generated/soc.h>
#ifdef SDRAM_CSR_STRIDE
/* Several SDRAM controllers: the CSR accesses of this file are relative to a variable CSR base,
 * so controller k is leveled at controller 0's CSRs + k*SDRAM_CSR_STRIDE (the SoC keeps each
 * controller's sdram/ddrphy/sdram_generator/sdram_checker CSR groups at that stride). With
 * SDRAM_CONTROLLERS, sdram_init() also levels controllers 1..SDRAM_CONTROLLERS-1. */
#include <generated/mem.h>
static const unsigned long sdram_csr_base0 = CSR_BASE;
static unsigned long sdram_csr_base = CSR_BASE;
#undef CSR_BASE
#define CSR_BASE sdram_csr_base
#endif // SDRAM_CSR_STRIDE

#include <generated/csr.h>
#ifdef CSR_SDRAM_BASE
#include <generated/mem.h>

#include <stdio.h>
#include <stdlib.h>

#include <libbase/memtest.h>
#include <libbase/lfsr.h>

#include <generated/sdram_phy.h>
#include <generated/mem.h>
#include <system.h>

#include <liblitedram/sdram.h>
#include <liblitedram/sdram_dbg.h>
#include <liblitedram/accessors.h>

//#define SDRAM_TEST_DISABLE
//#define SDRAM_WRITE_LEVELING_CMD_DELAY_DEBUG
//#define SDRAM_WRITE_LATENCY_CALIBRATION_DEBUG
//#define SDRAM_LEVELING_SCAN_DISPLAY_HEX_DIV 10

/*
 * SDRAM startup overview:
 *
 * sdram_init() is the BIOS entry point used before external RAM is trusted. It
 * resets software-visible training state, gives the CPU direct access to the PHY
 * through DFII, runs the generated JEDEC initialization sequence, performs the
 * optional PHY training stages, and finally hands the DFI bus back to the memory
 * controller. When enabled, a small memtest/memspeed pass then validates the
 * result and updates the DDR controller init status CSRs when they are present.
 *
 * Training is done with direct DFII traffic to a scratch row/bank. The high-tap
 * fast paths below reduce the number of exploratory samples on PHYs where a full
 * tap sweep is expensive, but accepted candidates are still checked with the
 * stage-specific full validation before hardware control is restored.
 */

#ifdef SDRAM_WRITE_LATENCY_CALIBRATION_DEBUG
#define SDRAM_WLC_DEBUG 1
#else
#define SDRAM_WLC_DEBUG 0
#endif // SDRAM_WRITE_LATENCY_CALIBRATION_DEBUG

/*
 * High-tap PHYs (UltraScale/UltraScale+) make exhaustive software calibration
 * expensive: each extra check is multiplied by modules, bitslips and delay taps.
 * The fast paths below keep the old exhaustive algorithms as fallbacks, but use
 * sparse scans to identify likely candidates first and then validate candidates
 * with the same stronger checks used by the exhaustive paths.
 */
#ifndef SDRAM_WRITE_LEVELING_FINAL_FAST
#if SDRAM_PHY_DELAYS > 128
#define SDRAM_WRITE_LEVELING_FINAL_FAST 1
#else
#define SDRAM_WRITE_LEVELING_FINAL_FAST 0
#endif // SDRAM_PHY_DELAYS > 128
#endif

#ifndef SDRAM_WRITE_LEVELING_FINAL_FAST_LOOPS
#define SDRAM_WRITE_LEVELING_FINAL_FAST_LOOPS 16
#endif

#ifndef SDRAM_WRITE_LEVELING_FINAL_VALIDATE_LOOPS
#define SDRAM_WRITE_LEVELING_FINAL_VALIDATE_LOOPS 128
#endif

#ifndef SDRAM_WRITE_LEVELING_FINAL_VALIDATE_RANGE
#if SDRAM_PHY_DELAYS > 128
#define SDRAM_WRITE_LEVELING_FINAL_VALIDATE_RANGE (SDRAM_PHY_DELAYS/16)
#else
#define SDRAM_WRITE_LEVELING_FINAL_VALIDATE_RANGE SDRAM_PHY_DELAYS
#endif // SDRAM_PHY_DELAYS > 128
#endif

#ifndef SDRAM_WRITE_LATENCY_CALIBRATION_FAST
#if SDRAM_PHY_DELAYS > 128
#define SDRAM_WRITE_LATENCY_CALIBRATION_FAST 1
#else
#define SDRAM_WRITE_LATENCY_CALIBRATION_FAST 0
#endif // SDRAM_PHY_DELAYS > 128
#endif

#ifndef SDRAM_WRITE_LATENCY_CALIBRATION_FAST_MIN_WINDOW
#define SDRAM_WRITE_LATENCY_CALIBRATION_FAST_MIN_WINDOW 2
#endif

#ifndef SDRAM_WRITE_LATENCY_CALIBRATION_FAST_STEP
#if SDRAM_PHY_DELAYS > 128
#define SDRAM_WRITE_LATENCY_CALIBRATION_FAST_STEP (SDRAM_PHY_DELAYS/64)
#else
#define SDRAM_WRITE_LATENCY_CALIBRATION_FAST_STEP 1
#endif // SDRAM_PHY_DELAYS > 128
#endif // SDRAM_WRITE_LATENCY_CALIBRATION_FAST_STEP

#ifndef SDRAM_WRITE_LATENCY_CALIBRATION_FAST_VALIDATE_MIN_WINDOW
#define SDRAM_WRITE_LATENCY_CALIBRATION_FAST_VALIDATE_MIN_WINDOW \
	(SDRAM_WRITE_LATENCY_CALIBRATION_FAST_STEP*SDRAM_WRITE_LATENCY_CALIBRATION_FAST_MIN_WINDOW)
#endif

#ifndef SDRAM_READ_LEVELING_FAST
#if SDRAM_PHY_DELAYS > 128
#define SDRAM_READ_LEVELING_FAST 1
#else
#define SDRAM_READ_LEVELING_FAST 0
#endif // SDRAM_PHY_DELAYS > 128
#endif

#ifndef SDRAM_READ_LEVELING_FAST_MIN_WINDOW
#define SDRAM_READ_LEVELING_FAST_MIN_WINDOW 2
#endif

#ifndef SDRAM_READ_LEVELING_FAST_STEP
#if SDRAM_PHY_DELAYS > 128
#define SDRAM_READ_LEVELING_FAST_STEP (SDRAM_PHY_DELAYS/64)
#else
#define SDRAM_READ_LEVELING_FAST_STEP 1
#endif // SDRAM_PHY_DELAYS > 128
#endif // SDRAM_READ_LEVELING_FAST_STEP

#ifndef SDRAM_READ_LEVELING_FAST_VALIDATE_MIN_WINDOW
#define SDRAM_READ_LEVELING_FAST_VALIDATE_MIN_WINDOW \
	(SDRAM_READ_LEVELING_FAST_STEP*SDRAM_READ_LEVELING_FAST_MIN_WINDOW)
#endif

#ifdef SDRAM_DELAY_PER_DQ
#define DQ_COUNT SDRAM_PHY_DQ_DQS_RATIO
#else
#define DQ_COUNT 1
#endif

/* DDR4 MPR read leveling (see sdram_read_leveling_mpr). Not used with RDIMMs or clamshell
 * layouts: B-side inversion / address mirroring changes BA[1:0], which selects the MPR
 * location. Can be disabled by defining SDRAM_MPR_READ_LEVELING_DISABLE. */
#if defined(SDRAM_PHY_DDR4) && defined(SDRAM_PHY_READ_LEVELING_CAPABLE) && \
	!defined(SDRAM_PHY_DDR4_RDIMM) && !defined(SDRAM_PHY_CLAM_SHELL) && \
	((SDRAM_PHY_PHASES*SDRAM_PHY_XDR) == 8) && !defined(SDRAM_MPR_READ_LEVELING_DISABLE)
#define SDRAM_MPR_READ_LEVELING
#endif

/* DDR4 MR3 value written by the LiteDRAM init sequence (1x fine granularity refresh). */
#ifndef SDRAM_DDR4_MR3
#define SDRAM_DDR4_MR3 0x0000
#endif

#if SDRAM_PHY_DELAYS > 32
#define MODULO (SDRAM_PHY_DELAYS/32)
#else
#define MODULO (1)
#endif // SDRAM_PHY_DELAYS > 32

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
#else // not SDRAM_PHY_CL
	return -1;
#endif // SDRAM_PHY_CL
}

int sdram_get_cwl(void) {
#ifdef SDRAM_PHY_CWL
	return SDRAM_PHY_CWL;
#else
	return -1;
#endif // SDRAM_PHY_CWL
}

/*-----------------------------------------------------------------------*/
/* DFII                                                                  */
/*-----------------------------------------------------------------------*/

/*
 * DFII is the software bridge to the DFI PHY interface. It exposes one set of
 * address, bank, command, write-data and read-data CSRs per DFI phase. The PHY
 * can choose different phases for reads and writes, so helpers ending in pird or
 * piwr route commands/data to the configured read or write phase instead of
 * assuming phase 0.
 */

#ifdef CSR_DDRPHY_BASE
static unsigned char sdram_dfii_get_rdphase(void) {
#ifdef CSR_DDRPHY_RDPHASE_ADDR
	return ddrphy_rdphase_read();
#else
	return SDRAM_PHY_RDPHASE;
#endif // CSR_DDRPHY_RDPHASE_ADDR
}

static unsigned char sdram_dfii_get_wrphase(void) {
#ifdef CSR_DDRPHY_WRPHASE_ADDR
	return ddrphy_wrphase_read();
#else
	return SDRAM_PHY_WRPHASE;
#endif // CSR_DDRPHY_WRPHASE_ADDR
}

static void sdram_dfii_pix_address_write(unsigned char phase, unsigned int value) {
#if (SDRAM_PHY_PHASES > 8)
	#error "More than 8 DFI phases not supported"
#endif // (SDRAM_PHY_PHASES > 8)
	switch (phase) {
#if (SDRAM_PHY_PHASES > 4)
	case 7: sdram_dfii_pi7_address_write(value); break;
	case 6: sdram_dfii_pi6_address_write(value); break;
	case 5: sdram_dfii_pi5_address_write(value); break;
	case 4: sdram_dfii_pi4_address_write(value); break;
#endif // (SDRAM_PHY_PHASES > 4)
#if (SDRAM_PHY_PHASES > 2)
	case 3: sdram_dfii_pi3_address_write(value); break;
	case 2: sdram_dfii_pi2_address_write(value); break;
#endif // (SDRAM_PHY_PHASES > 2)
#if (SDRAM_PHY_PHASES > 1)
	case 1: sdram_dfii_pi1_address_write(value); break;
#endif // (SDRAM_PHY_PHASES > 1)
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
#endif // (SDRAM_PHY_PHASES > 8)
	switch (phase) {
#if (SDRAM_PHY_PHASES > 4)
	case 7: sdram_dfii_pi7_baddress_write(value); break;
	case 6: sdram_dfii_pi6_baddress_write(value); break;
	case 5: sdram_dfii_pi5_baddress_write(value); break;
	case 4: sdram_dfii_pi4_baddress_write(value); break;
#endif // (SDRAM_PHY_PHASES > 4)
#if (SDRAM_PHY_PHASES > 2)
	case 3: sdram_dfii_pi3_baddress_write(value); break;
	case 2: sdram_dfii_pi2_baddress_write(value); break;
#endif // (SDRAM_PHY_PHASES > 2)
#if (SDRAM_PHY_PHASES > 1)
	case 1: sdram_dfii_pi1_baddress_write(value); break;
#endif // (SDRAM_PHY_PHASES > 1)
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
#endif // (SDRAM_PHY_PHASES > 8)
	switch (phase) {
#if (SDRAM_PHY_PHASES > 4)
	case 7: command_p7(value); break;
	case 6: command_p6(value); break;
	case 5: command_p5(value); break;
	case 4: command_p4(value); break;
#endif // (SDRAM_PHY_PHASES > 4)
#if (SDRAM_PHY_PHASES > 2)
	case 3: command_p3(value); break;
	case 2: command_p2(value); break;
#endif // (SDRAM_PHY_PHASES > 2)
#if (SDRAM_PHY_PHASES > 1)
	case 1: command_p1(value); break;
#endif // (SDRAM_PHY_PHASES > 1)
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
#endif // CSR_DDRPHY_BASE

/*-----------------------------------------------------------------------*/
/* Software/Hardware Control                                             */
/*-----------------------------------------------------------------------*/

/*
 * During initialization and calibration, the BIOS drives SDRAM commands itself
 * through DFII with CKE/ODT/reset_n asserted. In hardware mode, DFII_CONTROL_SEL
 * gives the DFI bus back to the memory controller for normal system accesses.
 *
 * PHY voltage/temperature compensation is disabled while measuring taps so delay
 * lines do not move underneath the software scans, then re-enabled before normal
 * controller traffic starts.
 */

#define DFII_CONTROL_SOFTWARE (DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N)
#define DFII_CONTROL_HARDWARE (DFII_CONTROL_SEL)

void sdram_software_control_on(void) {
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
#endif // CSR_DDRPHY_EN_VTC_ADDR
}

void sdram_software_control_off(void) {
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
#endif // CSR_DDRPHY_EN_VTC_ADDR
}

/*-----------------------------------------------------------------------*/
/*  Mode Register                                                        */
/*-----------------------------------------------------------------------*/

/*
 * Mode-register writes are issued as MRS commands on DFII phase 0. Clamshell
 * layouts need separate top/bottom chip-select commands and mirrored address
 * bits, so sdram_mode_register_write() hides that board-level wiring detail from
 * the JEDEC init sequence and training code.
 */

__attribute__((unused)) static int swap_bit(int num, int a, int b) {
	if (((num >> a) & 1) != ((num >> b) & 1)) {
		num ^= (1 << a);
		num ^= (1 << b);
	}
	return num;
}

void sdram_mode_register_write(char reg, int value) {
#ifndef SDRAM_PHY_CLAM_SHELL
	sdram_dfii_pi0_address_write(value);
	sdram_dfii_pi0_baddress_write(reg);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
#else
	sdram_dfii_pi0_address_write(value);
	sdram_dfii_pi0_baddress_write(reg);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS_TOP);

	value = swap_bit(value, 3, 4);
	value = swap_bit(value, 5, 6);
	value = swap_bit(value, 7, 8);
	value = swap_bit(value, 11, 13);
	reg = swap_bit(reg, 0, 1);

	sdram_dfii_pi0_address_write(value);
	sdram_dfii_pi0_baddress_write(reg);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS_BOTTOM);
#endif
}

#ifdef CSR_DDRPHY_BASE

/*-----------------------------------------------------------------------*/
/* Leveling Centering (Common for Read/Write Leveling)                   */
/*-----------------------------------------------------------------------*/

/*
 * All software training traffic uses row 0, bank 0 as a scratch location while
 * the controller is stopped. The row is activated, one burst is written/read via
 * DFII, then the row is precharged so the next probe starts from a known DRAM
 * command state.
 */

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
#endif // SDRAM_LEVELING_SCAN_DISPLAY_HEX_DIV
}

#define READ_CHECK_TEST_PATTERN_MAX_ERRORS (8*SDRAM_PHY_PHASES*DFII_PIX_DATA_BYTES/SDRAM_PHY_MODULES)
#define MODULE_BITMASK ((1<<SDRAM_PHY_DQ_DQS_RATIO)-1)

#ifdef SDRAM_MPR_READ_LEVELING
/*
 * DDR4 Multi-Purpose Register (MPR) reads: with MR3[2] set, a READ returns the predefined
 * serial patterns of MPR page 0 (MPR0: 01010101, MPR1: 00110011, MPR2: 00001111, MSB first,
 * identical on all DQs) through the normal read path and latency, without any prior write.
 */
static int _sdram_mpr_mode = 0;
static const unsigned char _sdram_mpr_patterns[3] = {0x55, 0x33, 0x0f};

static void sdram_mpr_set(int enable) {
	/* MR3: A2 = MPR operation, A[1:0] = page 0, A[12:11] = serial readout. */
	sdram_mode_register_write(3, SDRAM_DDR4_MR3 | (enable ? (1 << 2) : 0));
	cdelay(200);
}

static unsigned int sdram_mpr_check_module(int module, int dq_line) {
	int p, mpr;
	unsigned int errors = 0;
	unsigned char tst[DFII_PIX_DATA_BYTES];
	int pebo = (module * SDRAM_PHY_DQ_DQS_RATIO)/8;
	int nebo = pebo + (DFII_PIX_DATA_BYTES / SDRAM_PHY_XDR);
	int ibo  = (module * SDRAM_PHY_DQ_DQS_RATIO)%8;
	int mask = MODULE_BITMASK;

#ifdef SDRAM_DELAY_PER_DQ
	mask = 1 << dq_line;
#endif // SDRAM_DELAY_PER_DQ

	for (mpr = 0; mpr < 3; mpr++) {
		/* Read MPR location (BA[1:0]), no activate needed. */
		sdram_dfii_pird_address_write(0);
		sdram_dfii_pird_baddress_write(mpr);
		command_prd(DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA);
		cdelay(15);

		/* Check expected pattern (2 bits per phase: positive edge then negative edge). */
		for (p = 0; p < SDRAM_PHY_PHASES; p++) {
			unsigned char pos = ((_sdram_mpr_patterns[mpr] >> (7 - 2*p - 0)) & 1) ? 0xff : 0x00;
			unsigned char neg = ((_sdram_mpr_patterns[mpr] >> (7 - 2*p - 1)) & 1) ? 0xff : 0x00;
			csr_rd_buf_uint8(sdram_dfii_pix_rddata_addr(p), tst, DFII_PIX_DATA_BYTES);
			errors += popcount(((pos ^ tst[pebo]) >> ibo) & mask);
			errors += popcount(((neg ^ tst[nebo]) >> ibo) & mask);
		}
	}
	return errors;
}
#endif // SDRAM_MPR_READ_LEVELING

/*
 * Core calibration probe used by read leveling, write latency calibration and
 * write DQ-DQS training. It generates deterministic LFSR data for every DFI
 * phase, writes one burst through the configured write phase, reads it back
 * through the configured read phase, and counts bit errors only on the module
 * (or single DQ line) currently being trained.
 */
static unsigned int sdram_write_read_check_test_pattern(int module, unsigned int seed, int dq_line) {
	int p, i, bit;
	unsigned int errors;
	unsigned int prv;
	unsigned char value;
	unsigned char tst[DFII_PIX_DATA_BYTES];
	unsigned char prs[SDRAM_PHY_PHASES][DFII_PIX_DATA_BYTES];

#ifdef SDRAM_MPR_READ_LEVELING
	/* In MPR mode, check the DRAM's predefined patterns instead (read-only). */
	if (_sdram_mpr_mode)
		return sdram_mpr_check_module(module, dq_line);
#endif // SDRAM_MPR_READ_LEVELING

	/* Generate pseudo-random sequence */
	prv = seed;
	for(p=0;p<SDRAM_PHY_PHASES;p++) {
		for(i=0;i<DFII_PIX_DATA_BYTES;i++) {
			value = 0;
			for (bit=0;bit<8;bit++) {
				prv = lfsr(32, prv);
				value |= (prv&1) << bit;
			}
			prs[p][i] = value;
		}
	}

	/* Activate */
	sdram_activate_test_row();

	/* Write pseudo-random sequence */
	for(p=0;p<SDRAM_PHY_PHASES;p++) {
		csr_wr_buf_uint8(sdram_dfii_pix_wrdata_addr(p), prs[p], DFII_PIX_DATA_BYTES);
	}
	sdram_dfii_piwr_address_write(0);
	sdram_dfii_piwr_baddress_write(0);
	command_pwr(DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS|DFII_COMMAND_WRDATA);
	cdelay(15);

#if defined(SDRAM_PHY_ECP5DDRPHY) || defined(SDRAM_PHY_GW2DDRPHY) || defined(SDRAM_PHY_GW5DDRPHY) || defined(SDRAM_PHY_NEXUSDDRPHY)
	ddrphy_burstdet_clr_write(1);
#endif // defined(SDRAM_PHY_ECP5DDRPHY) || defined(SDRAM_PHY_GW2DDRPHY) || defined(SDRAM_PHY_GW5DDRPHY) || defined(SDRAM_PHY_NEXUSDDRPHY)

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
		int pebo;   // module's positive_edge_byte_offset
		int nebo;   // module's negative_edge_byte_offset, could be undefined if SDR DRAM is used
		int ibo;    // module's in byte offset (x4 ICs)
		int mask;   // Check data lines

		mask = MODULE_BITMASK;

#ifdef SDRAM_DELAY_PER_DQ
		mask = 1 << dq_line;
#endif // SDRAM_DELAY_PER_DQ

		/* Values written into CSR are Little Endian */
		/* SDRAM_PHY_XDR is define 1 if SDR and 2 if DDR*/
		nebo = (module * SDRAM_PHY_DQ_DQS_RATIO)/8 + (DFII_PIX_DATA_BYTES / SDRAM_PHY_XDR);
		pebo = (module * SDRAM_PHY_DQ_DQS_RATIO)/8;
		/* When DFII_PIX_DATA_BYTES is 1 and SDRAM_PHY_XDR is 2, pebo and nebo are both -1s,
		* but only correct value is 0. This can happen when single x4 IC is used */
		if ((DFII_PIX_DATA_BYTES/SDRAM_PHY_XDR) == 0) {
			pebo = DFII_PIX_DATA_BYTES - 1;
			nebo = DFII_PIX_DATA_BYTES - 1;
		}

		ibo = (module * SDRAM_PHY_DQ_DQS_RATIO)%8; // Non zero only if x4 ICs are used

		errors += popcount(((prs[p][pebo] >> ibo) & mask) ^
		                   ((tst[pebo] >> ibo) & mask));
		if (SDRAM_PHY_DQ_DQS_RATIO == 16)
			errors += popcount(((prs[p][pebo-1] >> ibo) & mask) ^
			                   ((tst[pebo-1] >> ibo) & mask));


#if SDRAM_PHY_XDR == 2
		if (DFII_PIX_DATA_BYTES == 1) // Special case for x4 single IC
			ibo = 0x4;
		errors += popcount(((prs[p][nebo] >> ibo) & mask) ^
		                   ((tst[nebo] >> ibo) & mask));
		if (SDRAM_PHY_DQ_DQS_RATIO == 16)
			errors += popcount(((prs[p][nebo-1] >> ibo) & mask) ^
			                   ((tst[nebo-1] >> ibo) & mask));
#endif // SDRAM_PHY_XDR == 2
	}

#if defined(SDRAM_PHY_ECP5DDRPHY) || defined(SDRAM_PHY_GW2DDRPHY) || defined(SDRAM_PHY_GW5DDRPHY) || defined(SDRAM_PHY_NEXUSDDRPHY)
	if (((ddrphy_burstdet_seen_read() >> module) & 0x1) != 1)
		errors += 1;
#endif // defined(SDRAM_PHY_ECP5DDRPHY) || defined(SDRAM_PHY_GW2DDRPHY) || defined(SDRAM_PHY_GW5DDRPHY) || defined(SDRAM_PHY_NEXUSDDRPHY)

	return errors;
}

static int _seed_array[] = {42, 84, 36};
static int _seed_array_length = sizeof(_seed_array) / sizeof(_seed_array[0]);

/* Run the software write/read test pattern on one byte lane (or one DQ line
 * when SDRAM_DELAY_PER_DQ is enabled). Fast candidate scans can use a subset of
 * seeds; final validation and centering always use all seeds. */
static int run_test_pattern_seeds(int module, int dq_line, int seed_count) {
	int errors = 0;
	if (seed_count < 1)
		seed_count = 1;
	if (seed_count > _seed_array_length)
		seed_count = _seed_array_length;
	for (int i = 0; i < seed_count; i++) {
		errors += sdram_write_read_check_test_pattern(module, _seed_array[i], dq_line);
	}
	return errors;
}

static int run_test_pattern(int module, int dq_line) {
	return run_test_pattern_seeds(module, dq_line, _seed_array_length);
}

#ifdef SDRAM_MPR_READ_LEVELING
static int _sdram_leveling_center_delay = -1;
#endif // SDRAM_MPR_READ_LEVELING

/* Locate the largest passing delay window for the current bitslip and program
 * the delay to its center. Two consecutive passing taps are required before a
 * window is trusted, since single-edge taps can be unstable. */
static int sdram_leveling_center_module(
	int module, int show_short, int show_long, action_callback rst_delay,
	action_callback inc_delay, int dq_line) {

	int i;
	int show;
	int working, last_working;
	unsigned int errors;
	int delay, delay_mid, delay_range;
	int delay_min = -1, delay_max = -1, cur_delay_min = -1;

	if (show_long)
#ifdef SDRAM_DELAY_PER_DQ
		printf("m%d dq_line:%d: |", module, dq_line);
#else
		printf("m%d: |", module);
#endif // SDRAM_DELAY_PER_DQ

	/* Find smallest working delay */
	delay = 0;
	working = 0;
	sdram_leveling_action(module, dq_line, rst_delay);
	while(1) {
		errors = run_test_pattern(module, dq_line);
		last_working = working;
		working = errors == 0;
		show = show_long && (delay%MODULO == 0);
		if (show)
			print_scan_errors(errors);
		if(working && last_working && delay_min < 0) {
			delay_min = delay - 1; // delay on edges can be spotty
			break;
		}
		delay++;
		if(delay >= SDRAM_PHY_DELAYS)
			break;
		sdram_leveling_action(module, dq_line, inc_delay);
	}

	delay_max = delay_min;
	cur_delay_min = delay_min;
	/* Find largest working delay range */
	while(1) {
		errors = run_test_pattern(module, dq_line);
		working = errors == 0;
		show = show_long && (delay%MODULO == 0);
		if (show)
			print_scan_errors(errors);

		if (working) {
			int cur_delay_length = delay - cur_delay_min;
			int best_delay_length = delay_max - delay_min;
			if (cur_delay_length > best_delay_length) {
				delay_min = cur_delay_min;
				delay_max = delay;
			}
		} else {
			cur_delay_min = delay + 1;
		}
		delay++;
		if(delay >= SDRAM_PHY_DELAYS)
			break;
		sdram_leveling_action(module, dq_line, inc_delay);
	}
	if(delay_max < 0) {
		delay_max = delay;
	}

	if (show_long)
		printf("| ");

	delay_mid   = (delay_min+delay_max)/2 % SDRAM_PHY_DELAYS;
	delay_range = (delay_max-delay_min)/2;
#ifdef SDRAM_MPR_READ_LEVELING
	_sdram_leveling_center_delay = (delay_min >= 0) ? delay_mid : -1;
#endif // SDRAM_MPR_READ_LEVELING
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
			sdram_leveling_action(module, dq_line, rst_delay);
			cdelay(100);
			for(i = 0; i < delay_mid; i++) {
				sdram_leveling_action(module, dq_line, inc_delay);
				cdelay(100);
			}

			/* Check */
			errors = run_test_pattern(module, dq_line);
			if (errors == 0)
				break;
			retries--;
		}
	}
	return delay_min >= 0 && errors == 0;
}

/*-----------------------------------------------------------------------*/
/* Write Leveling                                                        */
/*-----------------------------------------------------------------------*/

#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE

int _sdram_tck_taps;

int _sdram_write_leveling_cmd_scan  = 1;
int _sdram_write_leveling_cmd_delay = 0;

int _sdram_write_leveling_cdly_range_start = -1;
int _sdram_write_leveling_cdly_range_end   = -1;

static void sdram_write_leveling_on(void) {
	// Flip write leveling bit in the Mode Register, as it is disabled by default
	sdram_mode_register_write(DDRX_MR_WRLVL_ADDRESS, DDRX_MR_WRLVL_RESET ^ (1 << DDRX_MR_WRLVL_BIT));

#ifdef SDRAM_PHY_DDR4_RDIMM
	sdram_dfii_pi0_address_write((DDRX_MR_WRLVL_RESET ^ (1 << DDRX_MR_WRLVL_BIT)) ^ 0x2BF8) ;
	sdram_dfii_pi0_baddress_write(DDRX_MR_WRLVL_ADDRESS ^ 0xF);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
#endif // SDRAM_PHY_DDR4_RDIMM

	ddrphy_wlevel_en_write(1);
}

static void sdram_write_leveling_off(void) {
	sdram_mode_register_write(DDRX_MR_WRLVL_ADDRESS, DDRX_MR_WRLVL_RESET);

#ifdef SDRAM_PHY_DDR4_RDIMM
	sdram_dfii_pi0_address_write(DDRX_MR_WRLVL_RESET ^ 0x2BF8);
	sdram_dfii_pi0_baddress_write(DDRX_MR_WRLVL_ADDRESS ^ 0xF);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
#endif // SDRAM_PHY_DDR4_RDIMM

	ddrphy_wlevel_en_write(0);
}

void sdram_write_leveling_rst_cmd_delay(int show) {
	_sdram_write_leveling_cmd_scan = 1;
	if (show)
		printf("Resetting Cmd delay\n");
}

void sdram_write_leveling_force_cmd_delay(int taps, int show) {
	int i;
	_sdram_write_leveling_cmd_scan  = 0;
	_sdram_write_leveling_cmd_delay = taps;
	if (show)
		printf("Forcing Cmd delay to %d taps\n", taps);
	sdram_rst_clock_delay();
	for (i=0; i<taps; i++) {
		sdram_inc_clock_delay();
	}
}

static int sdram_write_leveling_sample(int module, int loops) {
	int k;
	int zero_count = 0;
	int one_count = 0;
	unsigned char buf[DFII_PIX_DATA_BYTES];

	if (loops < 1)
		loops = 1;

	for (k=0; k<loops; k++) {
		ddrphy_wlevel_strobe_write(1);
		cdelay(100);
		csr_rd_buf_uint8(sdram_dfii_pix_rddata_addr(0), buf, DFII_PIX_DATA_BYTES);
#if SDRAM_PHY_DQ_DQS_RATIO == 4
		/* For x4 memories, we need to test individual nibbles, not bytes */

		/* Extract the byte containing the nibble from the tested module */
		int module_byte = buf[DFII_PIX_DATA_BYTES-1-(SDRAM_PHY_MODULES-1-(module/2))];
		/* Shift the byte by 4 bits right if the module number is odd */
		module_byte >>= 4 * (module % 2);
		/* Extract the nibble from the tested module */
		if ((module_byte & 0xf) != 0)
#else // SDRAM_PHY_DQ_DQS_RATIO != 4
		if (buf[DFII_PIX_DATA_BYTES-1-(SDRAM_PHY_MODULES-1-module)] != 0)
#endif // SDRAM_PHY_DQ_DQS_RATIO == 4
			one_count++;
		else
			zero_count++;
	}

	return one_count > zero_count;
}

/* Decode a write-leveling tap scan into the delay to program. Write leveling
 * looks for the start of the longest returned-1 window, which corresponds to
 * the DQS transition relative to CK/CMD. A window already active at tap 0 is
 * accepted only if it is wide enough to imply the transition happened before
 * the scan range rather than being noise at the edge. */
static int sdram_write_leveling_find_delay(
	unsigned char *taps_scan, int scan_start, int scan_stop, int *delay) {
	int j;
	int one_window_active;
	int one_window_start, one_window_best_start;
	int one_window_count, one_window_best_count;

	/* Find longest 1 window and set delay at the 0/1 transition */
	one_window_active = 0;
	one_window_start = scan_start;
	one_window_count = 0;
	one_window_best_start = scan_start;
	one_window_best_count = -1;
	*delay = -1;
	for(j=scan_start;j<scan_stop+1;j++) {
		if (one_window_active) {
			if ((j == scan_stop) || (taps_scan[j] == 0)) {
				one_window_active = 0;
				one_window_count = j - one_window_start;
				if (one_window_count > one_window_best_count) {
					one_window_best_start = one_window_start;
					one_window_best_count = one_window_count;
				}
			}
		} else {
			if (j != scan_stop && taps_scan[j]) {
				one_window_active = 1;
				one_window_start = j;
			}
		}
	}

	/* Succeed only if the start of a 1s window has been found: */
	if (
		/* Start of 1s window directly seen after 0. */
		((one_window_best_start) > scan_start && (one_window_best_count > 0)) ||
		/* Start of 1s window indirectly seen before 0. */
		((one_window_best_start == 0) && (one_window_best_count > _sdram_tck_taps/4))
	) {
		*delay = one_window_best_start;
		return 1;
	}

	return 0;
}

static void sdram_write_leveling_set_dat_delay(int module, int dq_line, int delay) {
	/* Reset delay */
	sdram_leveling_action(module, dq_line, write_rst_delay);
	cdelay(100);

	/* Configure write delay */
	for(int j=0; j<delay; j++) {
		sdram_leveling_action(module, dq_line, write_inc_delay);
		cdelay(100);
	}
}

/* Scan a contiguous range of write-delay taps. This is used by the fast final
 * validation pass to rescan only the neighborhood around a candidate transition
 * with the original high loop count. */
static int sdram_write_leveling_scan_range(
	int module, int dq_line, int loops, int scan_start, int scan_stop, int *delay) {
	int j;
	unsigned char taps_scan[SDRAM_PHY_DELAYS];

	/* Reset delay and move to range start. */
	sdram_leveling_action(module, dq_line, write_rst_delay);
	cdelay(100);
	for(j=0; j<scan_start; j++) {
		sdram_leveling_action(module, dq_line, write_inc_delay);
		cdelay(100);
	}

	for(j=scan_start;j<scan_stop;j++) {
		taps_scan[j] = sdram_write_leveling_sample(module, loops);
		if (j == scan_stop-1)
			break;
		sdram_leveling_action(module, dq_line, write_inc_delay);
		cdelay(100);
	}

	return sdram_write_leveling_find_delay(taps_scan, scan_start, scan_stop, delay);
}

/* Full write-leveling data scan over all write-delay taps. The loop count is
 * intentionally caller-controlled: command-delay search uses a small loop count,
 * the legacy final scan uses 128 loops, and the high-tap fast path combines a
 * cheaper full-range scan with local 128-loop validation. */
static int sdram_write_leveling_scan(int *delays, int loops, int show) {
	int i, j, dq_line;

	int err_ddrphy_wdly;

	unsigned char taps_scan[SDRAM_PHY_DELAYS];

	int ok;

	err_ddrphy_wdly = SDRAM_PHY_DELAYS - _sdram_tck_taps/4;

	sdram_write_leveling_on();
	cdelay(100);
	for(i=0;i<SDRAM_PHY_MODULES;i++) {
		for (dq_line = 0; dq_line < DQ_COUNT; dq_line++) {
			if (show)
#ifdef SDRAM_DELAY_PER_DQ
				printf("  m%d dq%d: |", i, dq_line);
#else
				printf("  m%d: |", i);
#endif // SDRAM_DELAY_PER_DQ

			/* Reset delay */
			sdram_leveling_action(i, dq_line, write_rst_delay);
			cdelay(100);

			/* Scan write delay taps */
			for(j=0;j<err_ddrphy_wdly;j++) {
				int show_iter = (j%MODULO == 0) && show;

				taps_scan[j] = sdram_write_leveling_sample(i, loops);
				if (show_iter)
					printf("%d", taps_scan[j]);
				sdram_leveling_action(i, dq_line, write_inc_delay);
				cdelay(100);
			}
			if (show)
				printf("|");

			/* Use forced delay if configured */
			if (_sdram_write_leveling_dat_delays[i] >= 0) {
				delays[i] = _sdram_write_leveling_dat_delays[i];
			} else {
				sdram_write_leveling_find_delay(taps_scan, 0, err_ddrphy_wdly, &delays[i]);
			}

			if (delays[i] >= 0)
				sdram_write_leveling_set_dat_delay(i, dq_line, delays[i]);

			if (show) {
				if (delays[i] == -1)
					printf(" delay: -\n");
				else
					printf(" delay: %02d\n", delays[i]);
			}
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

#if SDRAM_WRITE_LEVELING_FINAL_FAST
/* Validate the fast final write-leveling result. The first pass identifies a
 * transition cheaply; this pass rescans a bounded range around that transition
 * with the original 128-loop depth. If any lane cannot be validated, the caller
 * falls back to the legacy full 128-loop scan over all taps. */
static int sdram_write_leveling_validate_delays(int *delays) {
	int i, dq_line;
	int err_ddrphy_wdly;
	int ok = 1;

	err_ddrphy_wdly = SDRAM_PHY_DELAYS - _sdram_tck_taps/4;

	sdram_write_leveling_on();
	cdelay(100);
	for(i=0;i<SDRAM_PHY_MODULES;i++) {
		for (dq_line = 0; dq_line < DQ_COUNT; dq_line++) {
			int delay = delays[i];
			int validated_delay = -1;

			if (_sdram_write_leveling_dat_delays[i] >= 0) {
				validated_delay = _sdram_write_leveling_dat_delays[i];
			} else if (delay >= 0) {
				int scan_start;
				int scan_stop;

				scan_start = max(0, delay - SDRAM_WRITE_LEVELING_FINAL_VALIDATE_RANGE);
				scan_stop  = min(err_ddrphy_wdly,
					delay + SDRAM_WRITE_LEVELING_FINAL_VALIDATE_RANGE + 1);

				/* A window starting before tap zero is accepted only when it stays
				 * valid for a large fraction of tCK, so scan enough taps to prove it. */
				if (scan_start == 0)
					scan_stop = min(err_ddrphy_wdly,
						max(scan_stop, _sdram_tck_taps/4 +
							SDRAM_WRITE_LEVELING_FINAL_VALIDATE_RANGE + 1));

				if (scan_stop <= scan_start) {
					ok = 0;
				} else if (!sdram_write_leveling_scan_range(i, dq_line,
					SDRAM_WRITE_LEVELING_FINAL_VALIDATE_LOOPS,
					scan_start, scan_stop, &validated_delay)) {
					ok = 0;
				}
			} else {
				ok = 0;
			}

			if (validated_delay >= 0) {
				delays[i] = validated_delay;
				sdram_write_leveling_set_dat_delay(i, dq_line, delays[i]);
			}
		}
	}
	sdram_write_leveling_off();

	return ok;
}
#endif // SDRAM_WRITE_LEVELING_FINAL_FAST

/* Pick the CK/CMD delay used for write leveling. Rather than scanning every tap
 * at full resolution, this performs coarse-to-fine searches around the current
 * best point. Candidates are scored by how many modules can be leveled and how
 * close the resulting data delays are to the desired centered position. */
static void sdram_write_leveling_find_cmd_delay(
	unsigned int *best_error, unsigned int *best_count, int *best_cdly,
	int cdly_start, int cdly_stop, int cdly_step) {
	int cdly;
	int delays[SDRAM_PHY_MODULES];
#ifndef SDRAM_WRITE_LEVELING_CMD_DELAY_DEBUG
	int ok;
#endif // SDRAM_WRITE_LEVELING_CMD_DELAY_DEBUG

	/* Scan through the range */
	sdram_rst_clock_delay();
	for (cdly = cdly_start; cdly < cdly_stop; cdly += cdly_step) {
		/* Increment cdly to current value */
		while (sdram_clock_delay < cdly)
			sdram_inc_clock_delay();

		/* Write level using this delay */
#ifdef SDRAM_WRITE_LEVELING_CMD_DELAY_DEBUG
		printf("Cmd/Clk delay: %d\n", cdly);
		sdram_write_leveling_scan(delays, 8, 1);
#else
		ok = sdram_write_leveling_scan(delays, 8, 0);
#endif // SDRAM_WRITE_LEVELING_CMD_DELAY_DEBUG
		/* Use the mean of delays for error calulation */
		int delay_mean  = 0;
		int delay_count = 0;
		for (int i=0; i < SDRAM_PHY_MODULES; ++i) {
			if (delays[i] != -1) {
				delay_mean  += delays[i]*256 + _sdram_tck_taps*64;
				delay_count += 1;
			}
		}
		if (delay_count != 0)
			delay_mean /= delay_count;

		/* We want the higher number of valid modules and delay to be centered */
		int ideal_delay = SDRAM_PHY_DELAYS*128 - _sdram_tck_taps*32;
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
		printf("Delay mean: %d/256, ideal: %d/256\n", delay_mean, ideal_delay);
#else
		printf("%d", ok);
#endif // SDRAM_WRITE_LEVELING_CMD_DELAY_DEBUG
	}
}

int sdram_write_leveling(void) {
	int delays[SDRAM_PHY_MODULES];
	unsigned int best_error = ~0u;
	unsigned int best_count = 0;
	int best_cdly = -1;
	int cdly_range_start;
	int cdly_range_end;
	int cdly_range_step;

	_sdram_tck_taps = ddrphy_half_sys8x_taps_read()*4;
	printf("  tCK equivalent taps: %d\n", _sdram_tck_taps);

	/* First align CK/CMD against DQS. This makes the later per-module data
	 * delay windows wide and centered enough to be robust. */
	if (_sdram_write_leveling_cmd_scan) {
		/* Center write leveling by varying cdly. Searching through all possible
		 * values is slow, but we can use a simple optimization method of iteratively
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
		sdram_rst_clock_delay();
		for (int i = 0; i < best_cdly; ++i) {
			sdram_inc_clock_delay();
		}
	}

	printf("  Data scan:\n");

	/* Re-run write leveling the final time */
#if SDRAM_WRITE_LEVELING_FINAL_FAST
	/* On high-tap PHYs, do a cheap all-tap pass first and validate each chosen
	 * transition locally at the legacy 128-loop depth. Any uncertainty reruns
	 * the original full 128-loop scan. */
	if (!sdram_write_leveling_scan(delays, SDRAM_WRITE_LEVELING_FINAL_FAST_LOOPS, 1))
		return 0;
	if (!sdram_write_leveling_validate_delays(delays)) {
		printf("  Fast validation failed, re-running full scan.\n");
		if (!sdram_write_leveling_scan(delays, 128, 1))
			return 0;
	}
#else
	if (!sdram_write_leveling_scan(delays, 128, 1))
		return 0;
#endif

	return best_cdly >= 0;
}
#endif /*  SDRAM_PHY_WRITE_LEVELING_CAPABLE */

/*-----------------------------------------------------------------------*/
/* Read Leveling                                                         */
/*-----------------------------------------------------------------------*/

#if defined(SDRAM_PHY_WRITE_DQ_DQS_TRAINING_CAPABLE) || defined(SDRAM_PHY_WRITE_LATENCY_CALIBRATION_CAPABLE) || defined(SDRAM_PHY_READ_LEVELING_CAPABLE)

/* Exhaustive read-window score for one bitslip. The score heavily rewards any
 * zero-error tap and still records relative quality when all taps fail, allowing
 * the legacy fallback to pick the least-bad bitslip instead of failing early. */
static unsigned int sdram_read_leveling_scan_module(int module, int bitslip, int show, int dq_line) {
	const unsigned int max_errors = _seed_array_length*READ_CHECK_TEST_PATTERN_MAX_ERRORS;
	int i;
	unsigned int score;
	unsigned int errors;

	/* Check test pattern for each delay value */
	score = 0;
	if (show)
		printf("  m%d, b%02d: |", module, bitslip);
	sdram_leveling_action(module, dq_line, read_rst_dq_delay);
	for(i=0;i<SDRAM_PHY_DELAYS;i++) {
		int working;
		int _show = (i%MODULO == 0) & show;
		errors = run_test_pattern(module, dq_line);
		working = errors == 0;
		/* When any scan is working then the final score will always be higher then if no scan was working */
		score += (working * max_errors*SDRAM_PHY_DELAYS) + (max_errors - errors);
		if (_show) {
			print_scan_errors(errors);
		}
		sdram_leveling_action(module, dq_line, read_inc_dq_delay);
	}
	if (show)
		printf("| ");

	return score;
}

/* Window detector used by the fast read-related paths. It can scan sparsely
 * with fewer seeds for candidate discovery, or scan every tap with all seeds
 * for validation. The optional outputs report the longest passing run. */
static int sdram_read_leveling_scan_window(
	int module, int dq_line, int seed_count, int step, int min_window,
	int *best_start, int *best_length, int bitslip, int show) {
	int good_delays = 0;
	int good_start = 0;
	int best_good_start = -1;
	int best_good_length = 0;

	if (step < 1)
		step = 1;
	if (min_window < 1)
		min_window = 1;

	if (show)
		printf("  m%d, b%02d: |", module, bitslip);

	sdram_leveling_action(module, dq_line, read_rst_dq_delay);
	for(int i=0;i<SDRAM_PHY_DELAYS;i++) {
		if ((i % step) == 0) {
			int errors = run_test_pattern_seeds(module, dq_line, seed_count);
			int _show = (i%MODULO == 0) & show;
			if (errors == 0) {
				if (good_delays == 0)
					good_start = i;
				good_delays++;
				if (good_delays > best_good_length) {
					best_good_start = good_start;
					best_good_length = good_delays;
				}
			} else {
				good_delays = 0;
			}
			if (_show)
				print_scan_errors(errors);
		}
		if (i == SDRAM_PHY_DELAYS-1)
			break;
		sdram_leveling_action(module, dq_line, read_inc_dq_delay);
	}

	if (show)
		printf("| ");

	if (best_start != NULL)
		*best_start = best_good_start;
	if (best_length != NULL)
		*best_length = best_good_length;

	return best_good_length >= min_window;
}

static int sdram_read_leveling_scan_has_window(
	int module, int dq_line, int seed_count, int step, int min_window) {
	return sdram_read_leveling_scan_window(
		module, dq_line, seed_count, step, min_window, NULL, NULL, -1, 0);
}

#endif // defined(SDRAM_PHY_WRITE_DQ_DQS_TRAINING_CAPABLE) || defined(SDRAM_PHY_WRITE_LATENCY_CALIBRATION_CAPABLE) || defined(SDRAM_PHY_READ_LEVELING_CAPABLE)

#ifdef SDRAM_PHY_READ_LEVELING_CAPABLE

#if SDRAM_READ_LEVELING_FAST
static void sdram_read_leveling_set_bitslip(int module, int dq_line, int bitslip) {
	sdram_leveling_action(module, dq_line, read_rst_dq_bitslip);
	for(int i=0; i<bitslip; i++)
		sdram_leveling_action(module, dq_line, read_inc_dq_bitslip);
}

/* Fast read-leveling bitslip selection. Sparse scans are allowed to produce a
 * contiguous group of adjacent candidates, since real valid windows can straddle
 * a bitslip boundary. The fast path accepts only one candidate group and then
 * chooses a unique widest all-seed validation window inside that group; separated
 * groups or ties fall back to the exhaustive scorer. */
static int sdram_read_leveling_fast_bitslip(int module, int dq_line) {
	int candidates[SDRAM_PHY_BITSLIPS];
	int groups = 0;
	int in_group = 0;
	int best_bitslip = -1;
	int best_window_length = 0;
	int best_window_count = 0;

	sdram_leveling_action(module, dq_line, read_rst_dq_bitslip);
	for(int bitslip=0; bitslip<SDRAM_PHY_BITSLIPS; bitslip++) {
		candidates[bitslip] = sdram_read_leveling_scan_has_window(
			module, dq_line, 1,
			SDRAM_READ_LEVELING_FAST_STEP,
			SDRAM_READ_LEVELING_FAST_MIN_WINDOW);

		if (bitslip == SDRAM_PHY_BITSLIPS-1)
			break;
		sdram_leveling_action(module, dq_line, read_inc_dq_bitslip);
	}

	for(int bitslip=0; bitslip<SDRAM_PHY_BITSLIPS; bitslip++) {
		if (candidates[bitslip] && !in_group) {
			groups++;
			in_group = 1;
		} else if (!candidates[bitslip]) {
			in_group = 0;
		}
	}

	if (groups != 1)
		return -1;

	for(int bitslip=0; bitslip<SDRAM_PHY_BITSLIPS; bitslip++) {
		int window_length;

		if (!candidates[bitslip])
			continue;

		sdram_read_leveling_set_bitslip(module, dq_line, bitslip);
		if (!sdram_read_leveling_scan_window(
			module, dq_line, _seed_array_length, 1,
			SDRAM_READ_LEVELING_FAST_VALIDATE_MIN_WINDOW,
			NULL, &window_length, bitslip, 1)) {
			printf("\n");
			continue;
		}
		printf("\n");

		if (window_length > best_window_length) {
			best_bitslip = bitslip;
			best_window_length = window_length;
			best_window_count = 1;
		} else if (window_length == best_window_length) {
			best_window_count++;
		}
	}

	if (best_window_count != 1)
		return -1;

	return best_bitslip;
}
#endif // SDRAM_READ_LEVELING_FAST

#ifdef SDRAM_MPR_READ_LEVELING
static int _sdram_mpr_valid = 0;
static int _sdram_mpr_bitslip[SDRAM_PHY_MODULES][DQ_COUNT];
static int _sdram_mpr_delay[SDRAM_PHY_MODULES][DQ_COUNT];

static void sdram_read_leveling_mpr_update(int module, int dq_line, int bitslip, int ok) {
	/* MPR pass: save read setting. */
	if (_sdram_mpr_mode) {
		_sdram_mpr_bitslip[module][dq_line] = ok ? bitslip : -1;
		_sdram_mpr_delay[module][dq_line]   = ok ? _sdram_leveling_center_delay : -1;
		return;
	}

	/* No read window on written data while the MPR pass found one: the write side of this
	 * module is not working, keep the read setting from the MPR pass. */
	if (!ok && _sdram_mpr_valid && (_sdram_mpr_bitslip[module][dq_line] >= 0)) {
		sdram_leveling_action(module, dq_line, read_rst_dq_bitslip);
		for(int i=0; i<_sdram_mpr_bitslip[module][dq_line]; i++)
			sdram_leveling_action(module, dq_line, read_inc_dq_bitslip);
		sdram_leveling_action(module, dq_line, read_rst_dq_delay);
		for(int i=0; i<_sdram_mpr_delay[module][dq_line]; i++)
			sdram_leveling_action(module, dq_line, read_inc_dq_delay);
		printf(" (kept MPR b%02d delay %02d)",
			_sdram_mpr_bitslip[module][dq_line],
			_sdram_mpr_delay[module][dq_line]);
	}
}
#endif // SDRAM_MPR_READ_LEVELING

void sdram_read_leveling(void) {
	int ok;
	int module;
	int bitslip;
	int dq_line;
	unsigned int score;
	unsigned int best_score;
	int best_bitslip;

	for(module=0; module<SDRAM_PHY_MODULES; module++) {
		for (dq_line = 0; dq_line < DQ_COUNT; dq_line++) {
			/* Find a bitslip with a usable read-delay window. Fast mode tries
			 * sparse candidate selection first; fallback prints and scores all
			 * bitslips exactly as the original algorithm did. */
			best_score = 0;
			best_bitslip = -1;
#if SDRAM_READ_LEVELING_FAST
			best_bitslip = sdram_read_leveling_fast_bitslip(module, dq_line);
#endif // SDRAM_READ_LEVELING_FAST
			if (best_bitslip < 0) {
				best_bitslip = 0;
				sdram_leveling_action(module, dq_line, read_rst_dq_bitslip);
				for(bitslip=0; bitslip<SDRAM_PHY_BITSLIPS; bitslip++) {
					/* Compute score */
					score = sdram_read_leveling_scan_module(module, bitslip, 1, dq_line);
#if !SDRAM_READ_LEVELING_FAST
					sdram_leveling_center_module(module, 1, 0,
						read_rst_dq_delay, read_inc_dq_delay, dq_line);
#endif // !SDRAM_READ_LEVELING_FAST
					printf("\n");
					if (score > best_score) {
						best_bitslip = bitslip;
						best_score = score;
					}
					/* Exit */
					if (bitslip == SDRAM_PHY_BITSLIPS-1)
						break;
					/* Increment bitslip */
					sdram_leveling_action(module, dq_line, read_inc_dq_bitslip);
				}
			}

			/* Select best read window */
#ifdef SDRAM_DELAY_PER_DQ
			printf("  best: m%d, b%02d, dq_line%d ", module, best_bitslip, dq_line);
#else
			printf("  best: m%d, b%02d ", module, best_bitslip);
#endif // SDRAM_DELAY_PER_DQ
#if SDRAM_READ_LEVELING_FAST
			sdram_read_leveling_set_bitslip(module, dq_line, best_bitslip);
#else
			sdram_leveling_action(module, dq_line, read_rst_dq_bitslip);
			for (bitslip=0; bitslip<best_bitslip; bitslip++)
				sdram_leveling_action(module, dq_line, read_inc_dq_bitslip);
#endif // SDRAM_READ_LEVELING_FAST

			/* Re-do leveling on best read window*/
			ok = sdram_leveling_center_module(module, 1, 0,
				read_rst_dq_delay, read_inc_dq_delay, dq_line);
#ifdef SDRAM_MPR_READ_LEVELING
			sdram_read_leveling_mpr_update(module, dq_line, best_bitslip, ok);
#else
			(void)ok;
#endif // SDRAM_MPR_READ_LEVELING
			printf("\n");
		}
	}
}

#ifdef SDRAM_MPR_READ_LEVELING
/*
 * Read leveling on the DDR4 MPR patterns: sets the read side (bitslip/delay) independently of
 * the write side, before write latency calibration and write DQ-DQS training which read back
 * what they write and can't distinguish a read error from a write error. The read settings
 * are saved and kept by the final read leveling for modules where it finds no window.
 */
static void sdram_read_leveling_mpr(void) {
	int module;
	int dq_line;

	for(module=0; module<SDRAM_PHY_MODULES; module++)
		for (dq_line = 0; dq_line < DQ_COUNT; dq_line++)
			_sdram_mpr_bitslip[module][dq_line] = -1;

	sdram_mpr_set(1);
	_sdram_mpr_mode = 1;
	sdram_read_leveling();
	_sdram_mpr_mode = 0;
	sdram_mpr_set(0);
	_sdram_mpr_valid = 1;
}
#endif // SDRAM_MPR_READ_LEVELING

#endif // SDRAM_PHY_READ_LEVELING_CAPABLE

#endif /* CSR_DDRPHY_BASE */

/*-----------------------------------------------------------------------*/
/* Write latency calibration                                             */
/*-----------------------------------------------------------------------*/

#ifdef SDRAM_PHY_WRITE_LATENCY_CALIBRATION_CAPABLE

static void sdram_write_latency_set_bitslip(int module, int dq_line, int bitslip) {
	sdram_leveling_action(module, dq_line, write_rst_dq_bitslip);
	for (int i=0; i<bitslip; i++)
		sdram_leveling_action(module, dq_line, write_inc_dq_bitslip);
}

static unsigned int sdram_write_latency_score_bitslip(
	int module, int dq_line, int bitslip, int debug) {
	unsigned int score = 0;

	if (debug)
		printf("m%d wb%02d:\n", module, bitslip);

	sdram_write_latency_set_bitslip(module, dq_line, bitslip);
	sdram_leveling_action(module, dq_line, read_rst_dq_bitslip);

	for(int i=0; i<SDRAM_PHY_BITSLIPS; i++) {
		unsigned int subscore;

		subscore = sdram_read_leveling_scan_module(module, i, debug, dq_line);
		if (debug)
			printf("\n");
		score = subscore > score ? subscore : score;

		if (i == SDRAM_PHY_BITSLIPS-1)
			break;
		sdram_leveling_action(module, dq_line, read_inc_dq_bitslip);
	}

	return score;
}

#if SDRAM_WRITE_LATENCY_CALIBRATION_FAST
/* Sparse one-seed scan used only to identify an unambiguous write bitslip. The
 * selected bitslip is accepted only after a full all-seed validation window is
 * found, otherwise the exhaustive scorer is used. */
static int sdram_write_latency_fast_bitslip(int module, int dq_line) {
	int candidates = 0;
	int candidate_bitslip = -1;

	for(int bitslip=0; bitslip<SDRAM_PHY_BITSLIPS; bitslip+=2) { /* +2 for tCK steps */
		int has_window = 0;

		sdram_write_latency_set_bitslip(module, dq_line, bitslip);
		sdram_leveling_action(module, dq_line, read_rst_dq_bitslip);

		for(int i=0; i<SDRAM_PHY_BITSLIPS; i++) {
			if (sdram_read_leveling_scan_has_window(
				module, dq_line, 1,
				SDRAM_WRITE_LATENCY_CALIBRATION_FAST_STEP,
				SDRAM_WRITE_LATENCY_CALIBRATION_FAST_MIN_WINDOW)) {
				has_window = 1;
				break;
			}
			if (i == SDRAM_PHY_BITSLIPS-1)
				break;
			sdram_leveling_action(module, dq_line, read_inc_dq_bitslip);
		}

		if (has_window) {
			candidates++;
			candidate_bitslip = bitslip;
		}
	}

	return (candidates == 1) ? candidate_bitslip : -1;
}

static int sdram_write_latency_bitslip_has_window(int module, int dq_line, int bitslip) {
	sdram_write_latency_set_bitslip(module, dq_line, bitslip);
	sdram_leveling_action(module, dq_line, read_rst_dq_bitslip);

	for(int i=0; i<SDRAM_PHY_BITSLIPS; i++) {
		if (sdram_read_leveling_scan_has_window(
			module, dq_line, _seed_array_length, 1,
			SDRAM_WRITE_LATENCY_CALIBRATION_FAST_VALIDATE_MIN_WINDOW))
			return 1;
		if (i == SDRAM_PHY_BITSLIPS-1)
			break;
		sdram_leveling_action(module, dq_line, read_inc_dq_bitslip);
	}

	return 0;
}
#endif // SDRAM_WRITE_LATENCY_CALIBRATION_FAST

static void sdram_write_latency_calibration(void) {
	int module;
	int bitslip;
	int dq_line;
	unsigned int score;
	unsigned int best_score;
	int best_bitslip;

	for(module = 0; module < SDRAM_PHY_MODULES; module++) {
		for (dq_line = 0; dq_line < DQ_COUNT; dq_line++) {
			best_score   = 0;
			best_bitslip = -1;

#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE
			/* If write leveling already provided a forced/known bitslip, use it
			 * directly. Otherwise calibrate write latency by checking which write
			 * bitslip allows a readable window after read bitslip/delay sweeps. */
			if (_sdram_write_leveling_bitslips[module] >= 0) {
				best_bitslip = _sdram_write_leveling_bitslips[module];
			} else
#endif // SDRAM_PHY_WRITE_LEVELING_CAPABLE
			{
#if SDRAM_WRITE_LATENCY_CALIBRATION_FAST
				if (!SDRAM_WLC_DEBUG) {
					bitslip = sdram_write_latency_fast_bitslip(module, dq_line);
					if (bitslip >= 0) {
						if (sdram_write_latency_bitslip_has_window(module, dq_line, bitslip)) {
							best_bitslip = bitslip;
						}
					}
				}
#endif // SDRAM_WRITE_LATENCY_CALIBRATION_FAST

				if (best_bitslip < 0) {
					/* Scan possible write windows */
					for(bitslip=0; bitslip<SDRAM_PHY_BITSLIPS; bitslip+=2) { /* +2 for tCK steps */
						score = sdram_write_latency_score_bitslip(
							module, dq_line, bitslip, SDRAM_WLC_DEBUG);
						if (score > best_score) {
							best_bitslip = bitslip;
							best_score = score;
						}
					}
				}
			}

			bitslip = best_bitslip;
			if (bitslip == -1)
				printf("m%d:- ", module);
			else
#ifdef SDRAM_DELAY_PER_DQ
				printf("m%d dq%d:%d ", module, dq_line, bitslip);
#else
				printf("m%d:%d ", module, bitslip);
#endif // SDRAM_DELAY_PER_DQ

			if (SDRAM_WLC_DEBUG)
				printf("\n");

			/* Reset bitslip */
			sdram_write_latency_set_bitslip(module, dq_line, bitslip);
#ifdef SDRAM_DELAY_PER_DQ
		printf("\n");
#endif
		}
	}
#ifndef SDRAM_DELAY_PER_DQ
	printf("\n");
#endif

}

#endif // SDRAM_PHY_WRITE_LATENCY_CALIBRATION_CAPABLE

/*-----------------------------------------------------------------------*/
/* Write DQ-DQS training                                                 */
/*-----------------------------------------------------------------------*/

#ifdef SDRAM_PHY_WRITE_DQ_DQS_TRAINING_CAPABLE

/* Write DQ-DQS training needs reads to be usable while it moves write delays, so
 * first choose and center the best read bitslip for the current lane. */
static int sdram_read_leveling_best_bitslip(int module, int dq_line) {
	unsigned int score;
	int bitslip;
	int best_bitslip = 0;
	unsigned int best_score = 0;

	sdram_leveling_action(module, dq_line, read_rst_dq_bitslip);
	for(bitslip=0; bitslip<SDRAM_PHY_BITSLIPS; bitslip++) {
		score = sdram_read_leveling_scan_module(module, bitslip, 0, dq_line);
#if !SDRAM_READ_LEVELING_FAST
		sdram_leveling_center_module(module, 0, 0,
			read_rst_dq_delay, read_inc_dq_delay, dq_line);
#endif // !SDRAM_READ_LEVELING_FAST
		if (score > best_score) {
			best_bitslip = bitslip;
			best_score = score;
		}
		if (bitslip == SDRAM_PHY_BITSLIPS-1)
			break;
		sdram_leveling_action(module, dq_line, read_inc_dq_bitslip);
	}

	/* Select best read window and re-center it */
	sdram_leveling_action(module, dq_line, read_rst_dq_bitslip);
	for (bitslip=0; bitslip<best_bitslip; bitslip++)
		sdram_leveling_action(module, dq_line, read_inc_dq_bitslip);
	return sdram_leveling_center_module(module, 0, 0,
		read_rst_dq_delay, read_inc_dq_delay, dq_line);
}

static void sdram_write_dq_dqs_training(void) {
	int module;
	int dq_line;

	for(module=0; module<SDRAM_PHY_MODULES; module++) {
		for (dq_line = 0; dq_line < DQ_COUNT; dq_line++) {
			/* Find usable reads. If writes are initially outside their valid
			 * window, move write data before trying read leveling again. */
			if (!sdram_read_leveling_best_bitslip(module, dq_line)) {
				int write_step = SDRAM_PHY_DELAYS >= 32 ? SDRAM_PHY_DELAYS/32 : 1;
				sdram_leveling_action(module, dq_line, write_rst_dq_delay);
				for (int delay = 0; delay < SDRAM_PHY_DELAYS; delay++) {
					if ((delay % write_step) == 0 &&
						sdram_read_leveling_best_bitslip(module, dq_line))
						break;
					if (delay < SDRAM_PHY_DELAYS - 1)
						sdram_leveling_action(module, dq_line, write_inc_dq_delay);
				}
			}
			/* Center DQ-DQS window */
			sdram_leveling_center_module(module, 1, 1,
				write_rst_dq_delay, write_inc_dq_delay, dq_line);
		}
	}
}

#endif /* SDRAM_PHY_WRITE_DQ_DQS_TRAINING_CAPABLE */

/*-----------------------------------------------------------------------*/
/* CK Phase Leveling                                                     */
/*-----------------------------------------------------------------------*/

#ifdef SDRAM_PHY_CKPHASE_STEPS

/*
 * DDR3 leveling for PHYs without write leveling that move CK against DQ/DQS instead (LiteDRAM's
 * S7DDRPHY with_ck_phase_shift, e.g. Series-7 HR banks): CK and the commands run on an MMCM fine
 * phase shift (ckphase CSRs), DQ/DQS/read capture stay on static clocks.
 *
 *   for each CK phase over one tCK (fine MMCM steps):
 *       JEDEC init (DLL reset), then for each write latency (bitslip 0/2/4/6, all lanes):
 *           read scan of every DQ bit at once: read bitslips x IDELAY taps, a DFI write/read
 *           check per point (fresh random data each time)
 *       each lane takes the write latency where all its bits have the widest read window;
 *       each bit its own read bitslip and the centre of its window (per-bit framing, dq_dly_sel);
 *       a DFI check of the result, then a LiteDRAM BIST write/read under traffic;
 *   the CK phase goes to the middle of the longest (circular) run of phases where every lane
 *   and the BIST pass, and the PHY is calibrated there once more, every bit's read tap is
 *   re-centred in its eye under BIST traffic (below), and the result is BIST-checked.
 *
 * A single-burst DFI check is not enough to pick the phase: a lane can pass it and fail under
 * traffic near its tDQSS crossing, hence the BIST at every step (when the SoC has the LiteDRAM
 * BIST: add_sdram(..., with_bist=True)).
 *
 * Nor is it enough to centre a bit: its read window from the DFI scan (a few isolated bursts) is
 * wider than its eye under back-to-back reads with every lane toggling, and the window's centre
 * can sit at the edge of that eye - a passing DFI check, rare read errors under traffic. So, at
 * the chosen phase, every bit's tap is moved by -range..+range from its centre and a BIST region
 * is read at each offset; each bit then goes to the middle of its longest run of clean offsets.
 * The DFI ECC's per-DQ corrected-error counters (LiteDRAM core/ecc.py, with_bit_stats) tell
 * which bits fail at an offset; without them a passing read clears every bit and a failing one
 * is retried one bit at a time. SDRAM_CKPHASE_EYE_RANGE 0 leaves this step out.
 */

#ifdef SDRAM_PHY_ECC
// DFI ECC (LiteDRAM core/ecc.py): the PHY's raw width, ECC lanes included - leveled like the
// data lanes (the DFI injector sits below the ECC, on the raw beats).
#define CKPHASE_LANES    SDRAM_PHY_ECC_MODULES    // x8 byte lanes.
#define CKPHASE_BITS     SDRAM_PHY_ECC_DATABITS   // DQ bits (8 per lane).
#else
#define CKPHASE_LANES    SDRAM_PHY_MODULES        // x8 byte lanes.
#define CKPHASE_BITS     SDRAM_PHY_DATABITS       // DQ bits (8 per lane).
#endif
#define CKPHASE_MASK_WORDS ((CKPHASE_BITS + 31)/32) // Failing-bit mask words.
#define CKPHASE_STEPS    SDRAM_PHY_CKPHASE_STEPS  // Fine CK phase steps per tCK.
#define CKPHASE_WLS      4                        // Write latencies tried: bitslip 0/2/4/6.
#define CKPHASE_BURSTS   2                        // DFI bursts per check.
#define CKPHASE_ALL_LANES ((1u << CKPHASE_LANES) - 1)

#ifndef SDRAM_CKPHASE_SCAN_STRIDE
#define SDRAM_CKPHASE_SCAN_STRIDE      2             // CK phase scan stride (fine steps).
#endif
#ifndef SDRAM_CKPHASE_MIN_WINDOW
#define SDRAM_CKPHASE_MIN_WINDOW       4             // Narrowest passing read window (taps).
#endif
#ifndef SDRAM_CKPHASE_BIST_STEP_BYTES
#define SDRAM_CKPHASE_BIST_STEP_BYTES  (16u << 20)   // Traffic test per scan step.
#endif
#ifndef SDRAM_CKPHASE_BIST_FINAL_BYTES
#define SDRAM_CKPHASE_BIST_FINAL_BYTES (256u << 20)  // Traffic test at the chosen phase.
#endif
#ifndef SDRAM_CKPHASE_EYE_RANGE
#define SDRAM_CKPHASE_EYE_RANGE        4             // Read eye under traffic: tap offsets tried.
#endif
#ifndef SDRAM_CKPHASE_EYE_BYTES
#define SDRAM_CKPHASE_EYE_BYTES        (8u << 20)    // Traffic test per tap offset.
#endif

#if ((CKPHASE_BITS != 64) && (CKPHASE_BITS != 72)) || \
    (DFII_PIX_DATA_SIZE != (2*CKPHASE_BITS + 31)/32) || (CKPHASE_STEPS > 256)
#error "CK phase leveling: 64-bit channels (72 with ECC lanes), two beats per DFII phase"
#endif

struct ckphase_bit {
	uint8_t bitslip; // Read bitslip (increments after reset).
	uint8_t tap;     // IDELAY tap.
	uint8_t window;  // Read window (taps).
};

// Per-bit summary of one write latency's scan: the widest window over the read bitslips.
struct ckphase_best {
	uint8_t len, start, bitslip;
};

// The leveling's state (~3.5 KB, .bss). Not zeroed: everything is written before it is read.
static struct {
	int      ckphase;                                        // Chosen CK phase (fine steps).
	int      run;                                            // Common passing run (fine steps).
	uint8_t  wl[CKPHASE_LANES];                              // Write bitslip per lane.
	struct ckphase_bit bit[CKPHASE_BITS];
	uint16_t lane_pass[CKPHASE_STEPS];                       // Per step: lanes that passed.
	uint8_t  bist_ok[CKPHASE_STEPS];
	uint32_t scan[SDRAM_PHY_BITSLIPS][CKPHASE_BITS];         // Passing taps per (bitslip, bit).
	struct ckphase_best wl_best[CKPHASE_WLS][CKPHASE_BITS];  // Per write latency, per bit.
} ckphase;

/* PHY controls of the selected lanes/bits (dly_sel/dq_dly_sel): reset, then n steps. */

static void ckphase_select(uint32_t lanes, uint32_t bits) {
	ddrphy_dly_sel_write(lanes);
	ddrphy_dq_dly_sel_write(bits);
}

static void ckphase_set_wl(uint32_t lanes, int n) {
	ckphase_select(lanes, 0);
	ddrphy_wdly_dq_bitslip_rst_write(1);
	for (int i = 0; i < n; i++)
		ddrphy_wdly_dq_bitslip_write(1);
	ckphase_select(0, 0);
}

static void ckphase_set_rb(uint32_t lanes, uint32_t bits, int n) {
	ckphase_select(lanes, bits);
	ddrphy_rdly_dq_bitslip_rst_write(1);
	for (int i = 0; i < n; i++)
		ddrphy_rdly_dq_bitslip_write(1);
	ckphase_select(0, 0);
}

static void ckphase_set_tap(uint32_t lanes, uint32_t bits, int n) {
	ckphase_select(lanes, bits);
	ddrphy_rdly_dq_rst_write(1);
	for (int i = 0; i < n; i++)
		ddrphy_rdly_dq_inc_write(1);
	ckphase_select(0, 0);
}

/* CK phase (MMCM fine phase shift, signed steps from its reset phase). */

static int ckphase_value(void) {
	return (int16_t)(ddrphy_ckphase_status_read() & 0xffff);
}

static int ckphase_status(int offset) {
	return (ddrphy_ckphase_status_read() >> offset) & 1;
}

static int ckphase_set(int target) {
	int v;
	while ((v = ckphase_value()) != target) {
		int i;
		if (target > v)
			ddrphy_ckphase_inc_write(1);
		else
			ddrphy_ckphase_dec_write(1);
		for (i = 0; i < 100000; i++)
			if (!ckphase_status(CSR_DDRPHY_CKPHASE_STATUS_BUSY_OFFSET))
				break;
		if (i == 100000)
			return 0;
	}
	return 1;
}

/* DFI check: one write/read round trip of CKPHASE_BURSTS bursts (row 0, bank 0), returning the
 * failing DQ bits (a CKPHASE_MASK_WORDS mask, bit b = DQ b). A DFII phase carries two beats of
 * CKPHASE_BITS bits, {odd, even}, in DFII_PIX_DATA_SIZE CSR words, most significant first. */

static uint32_t ckphase_rand_state = 0x2545F491;

static uint32_t ckphase_rand(void) {
	// xorshift32: fresh data at every check, so stale data never reads back as a pass.
	uint32_t x = ckphase_rand_state;
	x ^= x << 13;
	x ^= x >> 17;
	x ^= x << 5;
	return ckphase_rand_state = x;
}

static int ckphase_err(const uint32_t *errors, int b) {
	return (errors[b/32] >> (b%32)) & 1;
}

static void ckphase_dfi_check(uint32_t *errors) {
	uint32_t data[CKPHASE_BURSTS][SDRAM_PHY_PHASES][DFII_PIX_DATA_SIZE];
	for (int i = 0; i < CKPHASE_MASK_WORDS; i++)
		errors[i] = 0;
	int wrphase = sdram_dfii_get_wrphase();
	int rdphase = sdram_dfii_get_rdphase();

	sdram_activate_test_row();

	// Write.
	for (int b = 0; b < CKPHASE_BURSTS; b++) {
		for (int p = 0; p < SDRAM_PHY_PHASES; p++)
			for (int w = 0; w < DFII_PIX_DATA_SIZE; w++) {
				data[b][p][w] = ckphase_rand();
				csr_write_simple(data[b][p][w], sdram_dfii_pix_wrdata_addr(p) + 4*w);
			}
		sdram_dfii_pix_address_write(wrphase, 8*b);
		sdram_dfii_pix_baddress_write(wrphase, 0);
		command_px(wrphase, DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS|DFII_COMMAND_WRDATA);
		cdelay(15);
	}

	// Read back.
	for (int b = 0; b < CKPHASE_BURSTS; b++) {
		sdram_dfii_pix_address_write(rdphase, 8*b);
		sdram_dfii_pix_baddress_write(rdphase, 0);
		command_px(rdphase, DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA);
		cdelay(15);
		for (int p = 0; p < SDRAM_PHY_PHASES; p++)
			for (int w = 0; w < DFII_PIX_DATA_SIZE; w++) {
				uint32_t addr = sdram_dfii_pix_rddata_addr(p) + 4*w;
				uint32_t diff = csr_read_simple(addr) ^ data[b][p][w];
				// Word w holds phase bits [(N-1-w)*32, (N-w)*32): beat x/CKPHASE_BITS,
				// DQ x%CKPHASE_BITS (the top word's bits past 2*CKPHASE_BITS do not exist).
				for (int j = 0; diff && j < 32; j++, diff >>= 1) {
					int x = (DFII_PIX_DATA_SIZE - 1 - w)*32 + j;
					if ((diff & 1) && x < 2*CKPHASE_BITS)
						errors[(x % CKPHASE_BITS)/32] |= 1u << ((x % CKPHASE_BITS) % 32);
				}
			}
	}

	sdram_precharge_test_row();
}

/* BIST: a LiteDRAM generator/checker run under traffic (controller-local addresses). */

#ifdef CSR_SDRAM_GENERATOR_BASE
// The BIST runs under the controller (DFII_CONTROL_SEL), the leveling's own commands under
// software control: begin/end switch between the two.
static void ckphase_bist_begin(void) {
	sdram_dfii_control_write(DFII_CONTROL_SEL);
}

static void ckphase_bist_end(void) {
	sdram_dfii_control_write(DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
}

// Random data over [0, length); 1 when written.
static int ckphase_bist_write(uint32_t length) {
	int i;
	sdram_generator_reset_write(1);
	sdram_generator_random_write(1);
	sdram_generator_base_write(0);
	sdram_generator_end_write(length);
	sdram_generator_length_write(length);
	sdram_generator_start_write(1);
	for (i = 0; (sdram_generator_done_read() == 0) && (i < 10000000); i++);
	return i < 10000000;
}

// [0, length) against the generator's data: the error count (0xffffffff: timeout).
static uint32_t ckphase_bist_read(uint32_t length) {
	int i;
	sdram_checker_reset_write(1);
	sdram_checker_random_write(1);
	sdram_checker_base_write(0);
	sdram_checker_end_write(length);
	sdram_checker_length_write(length);
	sdram_checker_start_write(1);
	for (i = 0; (sdram_checker_done_read() == 0) && (i < 10000000); i++);
	return i < 10000000 ? sdram_checker_errors_read() : 0xffffffff;
}

static uint32_t ckphase_bist(uint32_t length) {
	uint32_t errors = 0xffffffff;
	ckphase_bist_begin();
	if (ckphase_bist_write(length))
		errors = ckphase_bist_read(length);
	ckphase_bist_end();
	return errors;
}
#else
// No LiteDRAM BIST in the SoC: the DFI checks alone pick the phase.
static uint32_t ckphase_bist(uint32_t length) {
	(void)length;
	return 0;
}
#endif // CSR_SDRAM_GENERATOR_BASE

/* Leveling at the current CK phase; returns the lanes that pass the DFI check. */

// Longest run of ones in a tap mask.
static int ckphase_window(uint32_t mask, int *start) {
	int best = 0, run = 0;
	*start = 0;
	for (int t = 0; t < SDRAM_PHY_DELAYS; t++) {
		if (mask & (1u << t)) {
			if (++run > best) {
				best   = run;
				*start = t - run + 1;
			}
		} else
			run = 0;
	}
	return best;
}

static void ckphase_read_scan(void) {
	for (int rb = 0; rb < SDRAM_PHY_BITSLIPS; rb++) {
		ckphase_set_rb(CKPHASE_ALL_LANES, 0, rb);
		ckphase_set_tap(CKPHASE_ALL_LANES, 0, 0);
		for (int b = 0; b < CKPHASE_BITS; b++)
			ckphase.scan[rb][b] = 0;
		for (int t = 0; t < SDRAM_PHY_DELAYS; t++) {
			uint32_t err[CKPHASE_MASK_WORDS];
			ckphase_dfi_check(err);
			for (int b = 0; b < CKPHASE_BITS; b++)
				if (!ckphase_err(err, b))
					ckphase.scan[rb][b] |= 1u << t;
			if (t != SDRAM_PHY_DELAYS - 1) {
				ckphase_select(CKPHASE_ALL_LANES, 0);
				ddrphy_rdly_dq_inc_write(1);
				ckphase_select(0, 0);
			}
		}
	}
}

static uint32_t ckphase_calibrate_point(void) {
	uint32_t lanes = 0;

	// Read scan at every write latency.
	for (int w = 0; w < CKPHASE_WLS; w++) {
		ckphase_set_wl(CKPHASE_ALL_LANES, 2*w);
		ckphase_read_scan();
		for (int b = 0; b < CKPHASE_BITS; b++) {
			struct ckphase_best *best = &ckphase.wl_best[w][b];
			best->len = 0;
			for (int rb = 0; rb < SDRAM_PHY_BITSLIPS; rb++) {
				int start, len = ckphase_window(ckphase.scan[rb][b], &start);
				if (len > best->len) {
					best->len     = len;
					best->start   = start;
					best->bitslip = rb;
				}
			}
		}
	}

	// Per lane: the write latency whose narrowest bit window is the widest.
	for (int l = 0; l < CKPHASE_LANES; l++) {
		int best_w = -1, best_min = 0;
		for (int w = 0; w < CKPHASE_WLS; w++) {
			int min = SDRAM_PHY_DELAYS;
			for (int i = 0; i < 8; i++)
				if (ckphase.wl_best[w][8*l + i].len < min)
					min = ckphase.wl_best[w][8*l + i].len;
			if (min > best_min) {
				best_min = min;
				best_w   = w;
			}
		}
		if (best_w < 0)
			best_w = 0;
		ckphase.wl[l] = 2*best_w;
		ckphase_set_wl(1u << l, 2*best_w);
		for (int i = 0; i < 8; i++) {
			struct ckphase_best *best = &ckphase.wl_best[best_w][8*l + i];
			struct ckphase_bit *bit   = &ckphase.bit[8*l + i];
			bit->bitslip = best->bitslip;
			bit->tap     = best->start + best->len/2;
			bit->window  = best->len;
			ckphase_set_rb(1u << l, 1u << i, bit->bitslip);
			ckphase_set_tap(1u << l, 1u << i, bit->tap);
		}
		if (best_min >= SDRAM_CKPHASE_MIN_WINDOW)
			lanes |= 1u << l;
	}

	// Check the result (a few rounds of fresh data).
	for (int n = 0; n < 4; n++) {
		uint32_t err[CKPHASE_MASK_WORDS];
		ckphase_dfi_check(err);
		for (int l = 0; l < CKPHASE_LANES; l++)
			for (int i = 0; i < 8; i++)
				if (ckphase_err(err, 8*l + i))
					lanes &= ~(1u << l);
	}
	return lanes;
}

/* Read eye under traffic (see the top): each bit's tap re-centred between the offsets where a
 * BIST read of SDRAM_CKPHASE_EYE_BYTES has no error on it. Returns the bits moved, -1 when the
 * BIST did not run. */

#if defined(CSR_SDRAM_GENERATOR_BASE) && (SDRAM_CKPHASE_EYE_RANGE > 0)

#define CKPHASE_EYE_RANGE SDRAM_CKPHASE_EYE_RANGE
#if CKPHASE_EYE_RANGE > 15
#error "SDRAM_CKPHASE_EYE_RANGE: at most 15 (a 32-bit mask of offsets)"
#endif

// Is offset o of a bit's mask clean? Offsets past the IDELAY's range are not tested: not clean.
static int ckphase_eye_clean(uint32_t mask, int o) {
	return (mask >> (o + CKPHASE_EYE_RANGE)) & 1;
}

// The longest run of clean offsets; on a tie, the one holding the DFI scan's centre (offset 0).
// Returns its length and its middle (toward 0 on a half) in *centre.
static int ckphase_eye_run(uint32_t mask, int *centre) {
	int best = 0, best_lo = 0, best_hi = -1;
	for (int o = -CKPHASE_EYE_RANGE; o <= CKPHASE_EYE_RANGE; o++) {
		if (!ckphase_eye_clean(mask, o))
			continue;
		int lo = o;
		while (o < CKPHASE_EYE_RANGE && ckphase_eye_clean(mask, o + 1))
			o++;
		int len = o - lo + 1;
		if (len > best || (len == best && lo <= 0 && o >= 0)) {
			best    = len;
			best_lo = lo;
			best_hi = o;
		}
	}
	*centre = best ? (best_lo + best_hi)/2 : 0;
	return best;
}

// Bit b's tap at offset o from its centre; 0 when that tap does not exist.
static int ckphase_eye_tap(int b, int o, int *tap) {
	*tap = ckphase.bit[b].tap + o;
	return *tap >= 0 && *tap < SDRAM_PHY_DELAYS;
}

static void ckphase_eye_set(int b, int tap) {
	ckphase_set_tap(1u << (b/8), 1u << (b%8), tap);
}

static int ckphase_eye_refine(void) {
	uint32_t clean[CKPHASE_BITS];  // Bit (o + range): no read error on DQ b at tap offset o.
	int moved = 0;

	ckphase_bist_begin();
	if (!ckphase_bist_write(SDRAM_CKPHASE_EYE_BYTES)) {
		ckphase_bist_end();
		return -1;
	}
#ifdef CSR_SDRAM_ECC_BITSEL_ADDR
	// The per-DQ counters attribute the errors (the decoder's syndrome: correction on).
	sdram_ecc_enable_write(1);
#endif
	for (int b = 0; b < CKPHASE_BITS; b++)
		clean[b] = 0;
	for (int o = -CKPHASE_EYE_RANGE; o <= CKPHASE_EYE_RANGE; o++) {
		uint32_t mark = 1u << (o + CKPHASE_EYE_RANGE);
		uint32_t tested[CKPHASE_MASK_WORDS] = {0};  // Bits with a tap at this offset.
		int tap;
		for (int b = 0; b < CKPHASE_BITS; b++)
			if (ckphase_eye_tap(b, o, &tap)) {
				ckphase_eye_set(b, tap);
				tested[b/32] |= 1u << (b%32);
			} else
				ckphase_eye_set(b, ckphase.bit[b].tap);
#ifdef CSR_SDRAM_ECC_BITSEL_ADDR
		sdram_ecc_clear_write(1);
		ckphase_bist_read(SDRAM_CKPHASE_EYE_BYTES);
		for (int b = 0; b < CKPHASE_BITS; b++) {
			sdram_ecc_bitsel_write(b);
			(void)sdram_ecc_bitcnt_read();  // The counter mux is registered: read it twice.
			if (sdram_ecc_bitcnt_read() == 0)
				clean[b] |= mark;
		}
#else
		if (ckphase_bist_read(SDRAM_CKPHASE_EYE_BYTES) == 0) {
			for (int b = 0; b < CKPHASE_BITS; b++)
				clean[b] |= mark;
		} else {
			// Which bits: every bit back at its centre, then one at a time at the offset.
			for (int b = 0; b < CKPHASE_BITS; b++)
				ckphase_eye_set(b, ckphase.bit[b].tap);
			for (int b = 0; b < CKPHASE_BITS; b++) {
				if (!ckphase_eye_tap(b, o, &tap))
					continue;
				ckphase_eye_set(b, tap);
				if (ckphase_bist_read(SDRAM_CKPHASE_EYE_BYTES) == 0)
					clean[b] |= mark;
				ckphase_eye_set(b, ckphase.bit[b].tap);
			}
		}
#endif
		for (int b = 0; b < CKPHASE_BITS; b++)
			if (!ckphase_err(tested, b))  // Not tested (past the IDELAY's range): not clean.
				clean[b] &= ~mark;
	}
#ifdef CSR_SDRAM_ECC_BITSEL_ADDR
	sdram_ecc_clear_write(1);
	sdram_ecc_enable_write(0);
#endif
	ckphase_bist_end();

	// Re-centre, and show each bit's clean offsets (#) and its move.
	printf("  read eye under traffic (%lu KB per offset, %+d..%+d from the scan's centre):\n",
		(unsigned long)(SDRAM_CKPHASE_EYE_BYTES >> 10), -CKPHASE_EYE_RANGE, CKPHASE_EYE_RANGE);
	for (int l = 0; l < CKPHASE_LANES; l++) {
		printf("  m%d:", l);
		for (int i = 0; i < 8; i++) {
			int b = 8*l + i, centre;
			struct ckphase_bit *bit = &ckphase.bit[b];
			ckphase_eye_run(clean[b], &centre);  // No clean offset: the scan's centre stays.
			if (centre) {
				bit->tap += centre;
				moved++;
			}
			ckphase_eye_set(b, bit->tap);
			printf(" ");
			for (int o = -CKPHASE_EYE_RANGE; o <= CKPHASE_EYE_RANGE; o++)
				printf("%c", ckphase_eye_clean(clean[b], o) ? '#' : '.');
			printf("%+d", centre);
		}
		printf("\n");
	}
	printf("  %d of %d bits moved\n", moved, CKPHASE_BITS);
	return moved;
}

#endif // CSR_SDRAM_GENERATOR_BASE && SDRAM_CKPHASE_EYE_RANGE

static void ckphase_init_dram(void) {
	// Close the test row (precharge all), then JEDEC init: DLL reset at the new CK phase.
	sdram_dfii_control_write(DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
	sdram_dfii_pi0_address_write(0x400);
	sdram_dfii_pi0_baddress_write(0);
	command_p0(DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
	cdelay(15);
	init_sequence();
	sdram_dfii_control_write(DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
}

static void ckphase_print_point(int ck, uint32_t lanes, uint32_t bist) {
	printf("  ck %+4d:", ck);
	for (int l = 0; l < CKPHASE_LANES; l++) {
		int min = SDRAM_PHY_DELAYS;
		for (int i = 0; i < 8; i++)
			if (ckphase.bit[8*l + i].window < min)
				min = ckphase.bit[8*l + i].window;
		printf(" %c%d/%02d", (lanes >> l) & 1 ? ' ' : '!', ckphase.wl[l], min);
	}
	if (bist == 0xfffffffe)
		printf("  bist -\n");
	else
		printf("  bist %lu\n", (unsigned long)bist);
}

// Index of a CK phase in the scan arrays ([-steps/2, steps/2) -> [0, steps)).
static int ckphase_index(int ck) {
	return (ck + CKPHASE_STEPS/2 + CKPHASE_STEPS) % CKPHASE_STEPS;
}

/* CK phase leveling of the PHY at the current CSR base; returns 1 on success. */
static int sdram_ckphase_calibrate(void) {
	const int half = CKPHASE_STEPS/2;
	int best_len = 0, best_start = 0;
	uint32_t lanes, bist_errors;
	int ok;

	printf("  ddrphy CSRs at %08lx, CK phase over one tCK: %d steps of %d\n",
		(unsigned long)CSR_DDRPHY_BASE, CKPHASE_STEPS/SDRAM_CKPHASE_SCAN_STRIDE,
		SDRAM_CKPHASE_SCAN_STRIDE);

	// PHY reset, MMCM lock.
	sdram_dfii_control_write(DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
	ddrphy_rst_write(1);
	cdelay(1000);
	ddrphy_rst_write(0);
	cdelay(1000);
	for (int i = 0; !ckphase_status(CSR_DDRPHY_CKPHASE_STATUS_LOCKED_OFFSET); i++) {
		if (i > 1000000) {
			printf("  PHY MMCM not locked\n");
			return 0;
		}
	}

	// Scan.
	for (int i = 0; i < CKPHASE_STEPS; i++)
		ckphase.lane_pass[i] = ckphase.bist_ok[i] = 0;
	for (int ck = -half; ck < half; ck += SDRAM_CKPHASE_SCAN_STRIDE) {
		uint32_t bist = 0xfffffffe;
		if (!ckphase_set(ck)) {
			printf("  CK phase step timeout\n");
			return 0;
		}
		ckphase_init_dram();
		lanes = ckphase_calibrate_point();
		if (lanes == CKPHASE_ALL_LANES)
			bist = ckphase_bist(SDRAM_CKPHASE_BIST_STEP_BYTES);
		ckphase_print_point(ck, lanes, bist);
		for (int j = 0; j < SDRAM_CKPHASE_SCAN_STRIDE; j++) {
			ckphase.lane_pass[ckphase_index(ck + j)] = lanes;
			ckphase.bist_ok[ckphase_index(ck + j)]   = (bist == 0);
		}
	}

	// Longest circular run of phases where every lane and the BIST pass.
	for (int start = 0; start < CKPHASE_STEPS; start++) {
		int len = 0;
		while (len < CKPHASE_STEPS) {
			int i = (start + len) % CKPHASE_STEPS;
			if (ckphase.lane_pass[i] != CKPHASE_ALL_LANES || !ckphase.bist_ok[i])
				break;
			len++;
		}
		if (len > best_len) {
			best_len   = len;
			best_start = start;
		}
	}
	ckphase.run = best_len;
	if (best_len == 0) {
		printf("  no CK phase where every lane passes\n");
		return 0;
	}
	ckphase.ckphase = (best_start + best_len/2) % CKPHASE_STEPS - half;

	// Level at the centre of the run.
	ckphase_set(ckphase.ckphase);
	ckphase_init_dram();
	lanes = ckphase_calibrate_point();
#if defined(CSR_SDRAM_GENERATOR_BASE) && (SDRAM_CKPHASE_EYE_RANGE > 0)
	if (lanes == CKPHASE_ALL_LANES)
		ckphase_eye_refine();
#endif
	bist_errors = (lanes == CKPHASE_ALL_LANES) ?
		ckphase_bist(SDRAM_CKPHASE_BIST_FINAL_BYTES) : 0xffffffff;
	ok = (lanes == CKPHASE_ALL_LANES) && (bist_errors == 0);
	ckphase_print_point(ckphase.ckphase, lanes, bist_errors);
	printf("  CK phase %+d (run %d steps), write bitslips", ckphase.ckphase, ckphase.run);
	for (int l = 0; l < CKPHASE_LANES; l++)
		printf(" %d", ckphase.wl[l]);
	printf(", read bitslip/tap/window per bit:\n");
	for (int l = 0; l < CKPHASE_LANES; l++) {
		printf("  m%d:", l);
		for (int i = 0; i < 8; i++)
			printf(" %d/%02d/%02d", ckphase.bit[8*l + i].bitslip, ckphase.bit[8*l + i].tap,
				ckphase.bit[8*l + i].window);
		printf("\n");
	}
	printf("  %s (BIST %lu KB, %lu errors)\n", ok ? "OK" : "FAILED",
		(unsigned long)(SDRAM_CKPHASE_BIST_FINAL_BYTES >> 10), (unsigned long)bist_errors);
	return ok;
}

/* CK phase leveling of controller `controller` (0: main_ram's, also run by sdram_leveling()).
 * Controller k > 0 is leveled at controller 0's CSRs + k*SDRAM_CSR_STRIDE and handed back to
 * its controller on success. */
int sdram_ckphase_leveling(int controller) {
	int ok;
	if (controller != 0) {
#ifdef SDRAM_CSR_STRIDE
		sdram_csr_base = sdram_csr_base0 + (unsigned long)controller*SDRAM_CSR_STRIDE;
#else
		printf("Controller %d: no SDRAM_CSR_STRIDE\n", controller);
		return 0;
#endif // SDRAM_CSR_STRIDE
	}
	printf("CK phase leveling (controller %d):\n", controller);
#ifdef CSR_SDRAM_ECC_ENABLE_ADDR
	// The BIST traffic tests judge the raw beats: no correction while leveling (the eye
	// refinement turns it on for its own reads, for the per-DQ counters).
	sdram_ecc_enable_write(0);
#endif
	ok = sdram_ckphase_calibrate();
#ifdef CSR_SDRAM_ECC_ENABLE_ADDR
	sdram_ecc_enable_write(1);
	sdram_ecc_clear_write(1);
#endif
#ifdef SDRAM_CSR_STRIDE
	if (controller != 0) {
		if (ok)
			sdram_software_control_off();
		sdram_csr_base = sdram_csr_base0;
	}
#endif // SDRAM_CSR_STRIDE
	return ok;
}

#endif // SDRAM_PHY_CKPHASE_STEPS

/*-----------------------------------------------------------------------*/
/* Leveling                                                              */
/*-----------------------------------------------------------------------*/

/*
 * Full PHY calibration sequence:
 *
 * - Reset delay/bitslip controls to a known point.
 * - Write leveling aligns CK/CMD and write DQS/DQ timing where supported.
 * - Write latency calibration selects the write bitslip that makes written data
 *   land in the readable burst position.
 * - Optional write DQ-DQS training centers write data delays using the already
 *   usable read path as the measurement reference.
 * - Read leveling then selects read bitslip and centers read delay windows.
 * - PHYs moving CK against DQ/DQS (SDRAM_PHY_CKPHASE_STEPS) run CK phase leveling
 *   instead: CK phase scan, write latency and per-bit read leveling at each step.
 *
 * Each stage leaves its programmed PHY state in place for the next stage.
 */
int sdram_leveling(void) {
	int module;
	int dq_line;
	sdram_software_control_on();

	/* Start from a known PHY state. Individual calibration stages can then move
	 * only the delays/bitslips they own, and forced values still start from the
	 * same reset point as discovered values. */
	for(module=0; module<SDRAM_PHY_MODULES; module++) {
		for (dq_line = 0; dq_line < DQ_COUNT; dq_line++) {
#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE
			sdram_leveling_action(module, dq_line, write_rst_delay);
#ifdef SDRAM_PHY_BITSLIPS
			sdram_leveling_action(module, dq_line, write_rst_dq_bitslip);
#endif // SDRAM_PHY_BITSLIPS
#endif // SDRAM_PHY_WRITE_LEVELING_CAPABLE

#ifdef SDRAM_PHY_READ_LEVELING_CAPABLE
			sdram_leveling_action(module, dq_line, read_rst_dq_delay);
#ifdef SDRAM_PHY_BITSLIPS
			sdram_leveling_action(module, dq_line, read_rst_dq_bitslip);
#endif // SDRAM_PHY_BITSLIPS
#endif // SDRAM_PHY_READ_LEVELING_CAPABLE
		}
	}

#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE
	printf("Write leveling:\n");
	sdram_write_leveling();
#endif // SDRAM_PHY_WRITE_LEVELING_CAPABLE

#ifdef SDRAM_MPR_READ_LEVELING
	printf("Read leveling (MPR):\n");
	sdram_read_leveling_mpr();
#endif // SDRAM_MPR_READ_LEVELING

#ifdef SDRAM_PHY_WRITE_LATENCY_CALIBRATION_CAPABLE
	printf("Write latency calibration:\n");
	sdram_write_latency_calibration();
#endif // SDRAM_PHY_WRITE_LATENCY_CALIBRATION_CAPABLE

#ifdef SDRAM_PHY_WRITE_DQ_DQS_TRAINING_CAPABLE
	printf("Write DQ-DQS training:\n");
	sdram_write_dq_dqs_training();
#endif // SDRAM_PHY_WRITE_DQ_DQS_TRAINING_CAPABLE

#if defined(SDRAM_PHY_CKPHASE_STEPS)
	/* Includes the write latency calibration and a per-bit read leveling. */
	sdram_ckphase_leveling(0);
#elif defined(SDRAM_PHY_READ_LEVELING_CAPABLE)
	printf("Read leveling:\n");
	sdram_read_leveling();
#endif // SDRAM_PHY_CKPHASE_STEPS / SDRAM_PHY_READ_LEVELING_CAPABLE

	sdram_software_control_off();

	return 1;
}

/*-----------------------------------------------------------------------*/
/* Initialization                                                        */
/*-----------------------------------------------------------------------*/

/*
 * Bring SDRAM from reset to normal controller-owned operation. The generated
 * init_sequence() contains the memory-type-specific JEDEC commands and waits
 * (power-up, reset/CKE, mode registers, ZQ calibration, refresh setup, ...).
 * This file surrounds that fixed sequence with PHY reset/training and LiteX
 * controller status reporting.
 */
int sdram_init(void) {
	printf("Initializing SDRAM @0x%08lx...\n", MAIN_RAM_BASE);

#ifdef CSR_DDRCTRL_BASE
	ddrctrl_init_done_write(0);
	ddrctrl_init_error_write(0);
#endif // CSR_DDRCTRL_BASE

#ifdef CONFIG_SDRAM_CUSTOM_INIT
	/* Some memories require board-level power or a device-specific training
	 * flow that cannot be represented by the generated generic sequence. */
	if (!sdram_custom_init()) {
		sdram_software_control_off();
#ifdef CSR_DDRCTRL_BASE
		ddrctrl_init_error_write(1);
		ddrctrl_init_done_write(1);
#endif // CSR_DDRCTRL_BASE
		return 0;
	}
#else
	/* Clear user/BIOS overrides so every boot starts from discovered values
	 * unless a build-time forced value is explicitly present. */
#ifdef SDRAM_PHY_WRITE_LEVELING_CAPABLE
	int i;
	sdram_write_leveling_rst_cmd_delay(0);
	for (i=0; i<16; i++) sdram_write_leveling_rst_dat_delay(i, 0);
#ifdef SDRAM_PHY_BITSLIPS
	for (i=0; i<16; i++) sdram_write_leveling_rst_bitslip(i, 0);
#endif // SDRAM_PHY_BITSLIPS
#endif // SDRAM_PHY_WRITE_LEVELING_CAPABLE
	/* Reset Read/Write phases */
#ifdef CSR_DDRPHY_RDPHASE_ADDR
	ddrphy_rdphase_write(SDRAM_PHY_RDPHASE);
#endif // CSR_DDRPHY_RDPHASE_ADDR
#ifdef CSR_DDRPHY_WRPHASE_ADDR
	ddrphy_wrphase_write(SDRAM_PHY_WRPHASE);
#endif // CSR_DDRPHY_WRPHASE_ADDR
	/* Set Cmd delay if enforced at build time */
#ifdef SDRAM_PHY_CMD_DELAY
	_sdram_write_leveling_cmd_scan  = 0;
	_sdram_write_leveling_cmd_delay = SDRAM_PHY_CMD_DELAY;
#endif // SDRAM_PHY_CMD_DELAY
	/* Stop normal controller ownership and put the PHY into a clean state before
	 * the JEDEC sequence touches the DRAM. */
	sdram_software_control_on();
#if CSR_DDRPHY_RST_ADDR
	ddrphy_rst_write(1);
	cdelay(1000);
	ddrphy_rst_write(0);
	cdelay(1000);
#endif // CSR_DDRPHY_RST_ADDR

	/* Generated from the configured memory module/timings. After this returns,
	 * the DRAM can respond to software DFII read/write probes. */
	init_sequence();
#if defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) || defined(SDRAM_PHY_READ_LEVELING_CAPABLE)
	sdram_leveling();
#endif // defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) || defined(SDRAM_PHY_READ_LEVELING_CAPABLE)
#endif // CONFIG_SDRAM_CUSTOM_INIT

	/* Release the DFI bus to the hardware controller; subsequent accesses use
	 * normal LiteX memory paths instead of direct DFII command CSRs. */
	sdram_software_control_off();
#ifndef SDRAM_TEST_DISABLE
	/* Final software smoke test before marking DDRCTRL init_done. */
	if(!memtest((unsigned int *) MAIN_RAM_BASE_VA, MEMTEST_DATA_SIZE)) {
#ifdef CSR_DDRCTRL_BASE
		ddrctrl_init_error_write(1);
		ddrctrl_init_done_write(1);
#endif // CSR_DDRCTRL_BASE
		return 0;
	}
	memspeed((unsigned int *) MAIN_RAM_BASE_VA, MEMTEST_DATA_SIZE, false, 0);
#endif // SDRAM_TEST_DISABLE
#if defined(SDRAM_PHY_CKPHASE_STEPS) && defined(SDRAM_CONTROLLERS)
	/* Other controllers of the SoC (SDRAM_CSR_STRIDE): leveled once main_ram is up, so they
	 * are ready for user logic after boot (their result does not change main_ram's init). */
	for (int controller = 1; controller < SDRAM_CONTROLLERS; controller++)
		sdram_ckphase_leveling(controller);
#endif // defined(SDRAM_PHY_CKPHASE_STEPS) && defined(SDRAM_CONTROLLERS)
#ifdef CSR_DDRCTRL_BASE
	ddrctrl_init_done_write(1);
#endif // CSR_DDRCTRL_BASE

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
#endif // SDRAM_DEBUG_READBACK_MEM_SIZE
#define SDRAM_DEBUG_READBACK_VERBOSE 1

#define SDRAM_DEBUG_READBACK_COUNT 3
#define SDRAM_DEBUG_READBACK_MEMTEST_SIZE MEMTEST_DATA_SIZE

#define _SINGLE_READBACK (SDRAM_DEBUG_READBACK_MEM_SIZE/SDRAM_DEBUG_READBACK_COUNT)
#define _READBACK_ERRORS_SIZE (_SINGLE_READBACK - sizeof(struct readback))
#define SDRAM_DEBUG_READBACK_LEN (_READBACK_ERRORS_SIZE / sizeof(struct memory_error))
#endif // SDRAM_DEBUG_READBACK_MEM_ADDR

static int sdram_debug_error_stats_on_error(
	unsigned int addr, unsigned int rdata, unsigned int refdata, void *arg) {
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
	memtest_data((unsigned int *) MAIN_RAM_BASE_VA, SDRAM_DEBUG_STATS_MEMTEST_SIZE, 1, NULL);

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
		memtest_data((unsigned int *) MAIN_RAM_BASE_VA, SDRAM_DEBUG_STATS_MEMTEST_SIZE, 1, &config);
	}

	printf("\n");
	error_stats_print(&stats);
}

#ifdef SDRAM_DEBUG_READBACK_MEM_ADDR
static int sdram_debug_readback_on_error(
	unsigned int addr, unsigned int rdata, unsigned int refdata, void *arg) {
	struct readback *readback = (struct readback *) arg;
	struct memory_error error = {
		.addr = addr,
		.data = rdata,
		.ref = refdata,
	};
	// run only as long as we have space for new entries
	return readback_add(readback, SDRAM_DEBUG_READBACK_LEN, error) != 1;
}

static void sdram_debug_readback(void) {
	printf("Using storage @0x%08x with size 0x%08x for %d readbacks.\n",
		SDRAM_DEBUG_READBACK_MEM_ADDR, SDRAM_DEBUG_READBACK_MEM_SIZE, SDRAM_DEBUG_READBACK_COUNT);

	printf("Running initial memtest to fill memory ...\n");
	memtest_data((unsigned int *) MAIN_RAM_BASE_VA, SDRAM_DEBUG_READBACK_MEMTEST_SIZE, 1, NULL);

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
		memtest_data((unsigned int *) MAIN_RAM_BASE_VA, SDRAM_DEBUG_READBACK_MEMTEST_SIZE, 1, &config);
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
#endif // SDRAM_DEBUG_READBACK_MEM_ADDR

void sdram_debug(void) {
#if defined(SDRAM_DEBUG_STATS_NUM_RUNS) && SDRAM_DEBUG_STATS_NUM_RUNS > 0
	printf("\nError stats:\n");
	sdram_debug_error_stats();
#endif // defined(SDRAM_DEBUG_STATS_NUM_RUNS) && SDRAM_DEBUG_STATS_NUM_RUNS > 0

#ifdef SDRAM_DEBUG_READBACK_MEM_ADDR
	printf("\nReadback:\n");
	sdram_debug_readback();
#endif // SDRAM_DEBUG_READBACK_MEM_ADDR
}
#endif // SDRAM_DEBUG

#endif // CSR_SDRAM_BASE
