/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

#ifndef __USNATIVE_XEM8320_PROFILE_H
#define __USNATIVE_XEM8320_PROFILE_H

/* This opt-in identifies the existing XEM8320 native CSR/tap-index ABI.
 * It is not a board autodetector or a promise of portable native calibration. */
#if !defined(SDRAM_PHY_DDR4) || SDRAM_PHY_DATABITS != 16 || SDRAM_PHY_DFI_DATABITS != 32 || SDRAM_PHY_PHASES != 4 || SDRAM_PHY_XDR != 2
#error "USNative XEM8320 calibration requires x16 DDR4 with four 32-bit DFI phases"
#endif
#if SDRAM_PHY_DELAYS != 512 || SDRAM_PHY_BITSLIPS != 8 || SDRAM_PHY_CMD_LATENCY != 5
#error "USNative XEM8320 calibration requires the registered-TX native timing profile"
#endif
#if MAIN_RAM_BASE != 0x40000000 || MAIN_RAM_SIZE < 0x01200000
#error "USNative calibration needs scratch RAM at 0x41000000 through 0x411fffff"
#endif
#if defined(CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION) && MAIN_RAM_SIZE < 0x05000000
#error "Optional USNative DMA refinement needs scratch RAM through 0x44ffffff"
#endif
#if !defined(CSR_DDRPHY_RIU_BUSY_ADDR) || !defined(CSR_DDRPHY_RIU_VALID_ADDR) || !defined(CSR_DDRPHY_TAP_STATUS_VALID_ADDR)
#error "USNative calibration requires acknowledged RIU access and registered tap status"
#endif
#ifdef CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION
#if !defined(CONFIG_SDRAM_NATIVE_DMA_TEST)
#error "USNative DMA calibration requires the DMA benchmark configuration"
#endif
#if !defined(CSR_DMA_BENCH_START_ADDR) || !defined(CSR_DMA_BENCH_DQ_ERROR_MASK_ADDR) || !defined(CSR_DMA_BENCH_DATA_WIDTH_ADDR)
#error "USNative calibration requires a DMA engine with per-DQ error reporting"
#endif
#endif

#if CONFIG_CLOCK_FREQUENCY == 300000000 && SDRAM_PHY_CL == 17 && SDRAM_PHY_CWL == 12 && SDRAM_PHY_RDPHASE == 2 && SDRAM_PHY_WRPHASE == 3
#define USNATIVE_WR_ADDRESS sdram_dfii_pi3_address_write
#define USNATIVE_WR_BANK sdram_dfii_pi3_baddress_write
#define USNATIVE_WR_COMMAND command_p3
#define USNATIVE_RD_ADDRESS sdram_dfii_pi2_address_write
#define USNATIVE_RD_BANK sdram_dfii_pi2_baddress_write
#define USNATIVE_RD_COMMAND command_p2
#elif CONFIG_CLOCK_FREQUENCY == 333333333 && SDRAM_PHY_CL == 19 && SDRAM_PHY_CWL == 14 && SDRAM_PHY_RDPHASE == 0 && SDRAM_PHY_WRPHASE == 1
#define USNATIVE_WR_ADDRESS sdram_dfii_pi1_address_write
#define USNATIVE_WR_BANK sdram_dfii_pi1_baddress_write
#define USNATIVE_WR_COMMAND command_p1
#define USNATIVE_RD_ADDRESS sdram_dfii_pi0_address_write
#define USNATIVE_RD_BANK sdram_dfii_pi0_baddress_write
#define USNATIVE_RD_COMMAND command_p0
#elif defined(CONFIG_SDRAM_USNATIVE_OVERCLOCK) && (CONFIG_CLOCK_FREQUENCY == 366666666 || CONFIG_CLOCK_FREQUENCY == 366666667) && SDRAM_PHY_CL == 21 && SDRAM_PHY_CWL == 16 && SDRAM_PHY_RDPHASE == 2 && SDRAM_PHY_WRPHASE == 3
#define USNATIVE_WR_ADDRESS sdram_dfii_pi3_address_write
#define USNATIVE_WR_BANK sdram_dfii_pi3_baddress_write
#define USNATIVE_WR_COMMAND command_p3
#define USNATIVE_RD_ADDRESS sdram_dfii_pi2_address_write
#define USNATIVE_RD_BANK sdram_dfii_pi2_baddress_write
#define USNATIVE_RD_COMMAND command_p2
#elif defined(CONFIG_SDRAM_USNATIVE_OVERCLOCK) && CONFIG_CLOCK_FREQUENCY == 400000000 && SDRAM_PHY_CL == 24 && SDRAM_PHY_CWL == 16 && SDRAM_PHY_RDPHASE == 3 && SDRAM_PHY_WRPHASE == 3
#define USNATIVE_WR_ADDRESS sdram_dfii_pi3_address_write
#define USNATIVE_WR_BANK sdram_dfii_pi3_baddress_write
#define USNATIVE_WR_COMMAND command_p3
#define USNATIVE_RD_ADDRESS sdram_dfii_pi2_address_write
#define USNATIVE_RD_BANK sdram_dfii_pi2_baddress_write
#define USNATIVE_RD_COMMAND command_p2
#else
#error "Unsupported USNative XEM8320 profile; high rates require explicit overclock configuration"
#endif

/* The 3200 routed profile resets its read-phase CSR to 3, but its trained
 * operating phase is 2. Direct-DFII probes and controller traffic must agree.
 * Bootstrap seeds only establish a starting point: all normal window, deskew,
 * guard and final memory checks remain mandatory. */
#if CONFIG_CLOCK_FREQUENCY == 400000000
#define USNATIVE_RDPHASE 2
#define USNATIVE_BOOT_TX_DELAY 72
#define USNATIVE_BOOT_RX_DELAY 48
#else
#define USNATIVE_RDPHASE SDRAM_PHY_RDPHASE
#define USNATIVE_BOOT_TX_DELAY 88
#define USNATIVE_BOOT_RX_DELAY 32
#endif

#if CONFIG_CLOCK_FREQUENCY == 400000000
#define USNATIVE_GATE_DELAY 5
#elif CONFIG_CLOCK_FREQUENCY == 366666666 || CONFIG_CLOCK_FREQUENCY == 366666667
#define USNATIVE_GATE_DELAY 4
#else
#define USNATIVE_GATE_DELAY 3
#endif

/* Verbose scans and optional diagnostic snapshots are disabled by default. */
#ifdef CONFIG_SDRAM_USNATIVE_DEBUG
#define USNATIVE_DEBUG(...) printf(__VA_ARGS__)
#ifdef CSR_DDRPHY_SNAPSHOT_ADDR
#define USNATIVE_SNAPSHOT() ddrphy_snapshot_write(1)
#else
#define USNATIVE_SNAPSHOT() do {} while (0)
#endif
#else
#define USNATIVE_DEBUG(...) do {} while (0)
#define USNATIVE_SNAPSHOT() do {} while (0)
#endif

/* Independent software bound in case the DMA done response never arrives. */
#ifndef USNATIVE_DMA_POLL_LIMIT
#define USNATIVE_DMA_POLL_LIMIT 10000000u
#endif
#if USNATIVE_DMA_POLL_LIMIT < 1
#error "USNative DMA polling must be bounded by a positive count"
#endif
#endif
