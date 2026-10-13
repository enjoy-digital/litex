// This file is part of LiteX.
//
// Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
// SPDX-License-Identifier: BSD-2-Clause

/*
 * DDR3 calibration for LiteDRAM's S7DDRPHY with CK phase shift (with_ck_phase_shift: Series-7 HR
 * banks, write leveling by CK phase).
 *
 * The PHY has no write leveling (no ODELAYE2 on HR banks): CK moves against DQ/DQS instead.
 *
 *   for each CK phase over one tCK (fine MMCM steps):
 *       JEDEC init (DLL reset), then for each write latency (bitslip 0/2/4/6, all lanes):
 *           read scan of every DQ bit at once: read bitslips x IDELAY taps, a DFI write/read
 *           check per point (fresh random data each time)
 *       each lane takes the write latency where all its bits have the widest read window;
 *       each bit its own read bitslip and the centre of its window (per-bit framing);
 *       a DFI check of the result, then a LiteDRAM BIST write/read under traffic;
 *   the CK phase goes to the middle of the longest (circular) run of phases where every lane
 *   and the BIST pass, and the channel is calibrated there once more and BIST-checked.
 *
 * A single-burst DFI check is not enough to pick the phase: a lane can pass it and fail under
 * traffic near its tDQSS crossing, hence the BIST at every step (when the SoC has the LiteDRAM
 * BIST: add_sdram(..., with_bist=True)).
 *
 * Several controllers: every CSR access below is relative to a variable CSR base, so controller
 * k is calibrated at controller 0's CSRs + k*SDRAM_S7HR_CSR_STRIDE (the SoC keeps each
 * controller's sdram/ddrphy/sdram_generator/sdram_checker CSR groups at that stride).
 */

#include <generated/soc.h>
#include <generated/mem.h>              // CSR_BASE, the literal.

__attribute__((unused)) static const unsigned long s7hr_csr_base0 = CSR_BASE;
#undef CSR_BASE
__attribute__((unused)) static unsigned long s7hr_csr_base;
#define CSR_BASE s7hr_csr_base

#include <stdio.h>
#include <stdint.h>

#include <generated/csr.h>

#ifdef CSR_SDRAM_BASE
#include <generated/sdram_phy.h>
#endif

#include <system.h>

#include <liblitedram/sdram.h>
#include <liblitedram/sdram_s7hr.h>

#ifdef SDRAM_S7HR_CALIBRATION

/* Parameters */
/*------------*/

#define S7HR_LANES     SDRAM_PHY_MODULES           // x8 byte lanes.
#define S7HR_BITS      SDRAM_PHY_DATABITS          // DQ bits (8 per lane).
#define S7HR_TAPS      SDRAM_PHY_DELAYS            // IDELAY taps.
#define S7HR_BITSLIPS  SDRAM_PHY_BITSLIPS          // Read bitslips (one bit each).
#define S7HR_STEPS     SDRAM_PHY_CKPHASE_STEPS   // Fine CK phase steps per tCK.
#define S7HR_WLS       4                           // Write latencies tried: bitslip 0/2/4/6.
#define S7HR_BURSTS    2                           // DFI bursts per check.

#ifndef S7HR_SCAN_STRIDE
#define S7HR_SCAN_STRIDE 2                         // CK phase scan stride (fine steps).
#endif
#ifndef S7HR_MIN_WINDOW
#define S7HR_MIN_WINDOW  4                         // Narrowest read window a bit may pass with (taps).
#endif
#ifndef S7HR_BIST_STEP_BYTES
#define S7HR_BIST_STEP_BYTES  (16u << 20)          // Traffic test per scan step.
#endif
#ifndef S7HR_BIST_FINAL_BYTES
#define S7HR_BIST_FINAL_BYTES (256u << 20)         // Traffic test at the chosen phase.
#endif
#define S7HR_BIST_BASE        0x0000000u           // Controller-local byte address.

#define S7HR_ALL_LANES ((1u << S7HR_LANES) - 1)

#if (S7HR_BITS != 64) || (DFII_PIX_DATA_SIZE != 4) || (S7HR_STEPS > 256)
#error "S7HR calibration: a 64-bit channel (two 64-bit beats per DFII phase, 4 CSR words)"
#endif

/* Results */
/*---------*/

struct s7hr_bit {
    uint8_t bitslip; // Read bitslip (increments after reset).
    uint8_t tap;     // IDELAY tap.
    uint8_t window;  // Read window (taps).
};

struct s7hr_result {
    int     ok;
    int     ckphase;                  // Chosen CK phase (fine steps from the MMCM's reset phase).
    int     run;                      // Common passing run (fine steps).
    uint8_t wl[S7HR_LANES];           // Write bitslip per lane.
    struct s7hr_bit bit[S7HR_BITS];
    uint8_t lane_pass[S7HR_STEPS];    // Per scan step: lanes that passed (bit 7 of each byte... lanes).
    uint8_t bist_ok[S7HR_STEPS];
    uint32_t bist_errors;             // Final BIST.
};

// Per-bit summary of one write latency's scan: the widest window over the read bitslips.
struct s7hr_best {
    uint8_t len, start, bitslip;
};

// The calibration's state (~3.5 KB, .bss). Not zeroed: everything is written before it is read.
struct s7hr_state {
    struct s7hr_result result;
    uint32_t scan[S7HR_BITSLIPS][S7HR_BITS];      // Passing taps per (read bitslip, bit).
    struct s7hr_best wl_best[S7HR_WLS][S7HR_BITS]; // Per write latency, per bit.
};

static struct s7hr_state s7hr_state;
#define S7HR_STATE (&s7hr_state)
#define s7hr         (S7HR_STATE->result)
#define s7hr_scan    (S7HR_STATE->scan)
#define s7hr_wl_best (S7HR_STATE->wl_best)

/* PHY Helpers */
/*-------------*/

static void s7hr_select(uint32_t lanes, uint32_t bits)
{
    ddrphy_dly_sel_write(lanes);
    ddrphy_dq_dly_sel_write(bits);
}

static void s7hr_deselect(void)
{
    ddrphy_dly_sel_write(0);
    ddrphy_dq_dly_sel_write(0);
}

// Write bitslip of the selected lanes: reset, then n steps.
static void s7hr_set_wl(uint32_t lanes, int n)
{
    s7hr_select(lanes, 0);
    ddrphy_wdly_dq_bitslip_rst_write(1);
    for (int i = 0; i < n; i++)
        ddrphy_wdly_dq_bitslip_write(1);
    s7hr_deselect();
}

// Read bitslip of the selected bits: reset, then n steps.
static void s7hr_set_rb(uint32_t lanes, uint32_t bits, int n)
{
    s7hr_select(lanes, bits);
    ddrphy_rdly_dq_bitslip_rst_write(1);
    for (int i = 0; i < n; i++)
        ddrphy_rdly_dq_bitslip_write(1);
    s7hr_deselect();
}

// IDELAY tap of the selected bits: reset, then n taps.
static void s7hr_set_tap(uint32_t lanes, uint32_t bits, int n)
{
    s7hr_select(lanes, bits);
    ddrphy_rdly_dq_rst_write(1);
    for (int i = 0; i < n; i++)
        ddrphy_rdly_dq_inc_write(1);
    s7hr_deselect();
}

/* CK Phase */
/*----------*/

static int s7hr_ck_value(void)
{
    return (int16_t)(ddrphy_ckphase_status_read() & 0xffff);
}

static int s7hr_ck_busy(void)
{
    return (ddrphy_ckphase_status_read() >> CSR_DDRPHY_CKPHASE_STATUS_BUSY_OFFSET) & 1;
}

static int s7hr_ck_locked(void)
{
    return (ddrphy_ckphase_status_read() >> CSR_DDRPHY_CKPHASE_STATUS_LOCKED_OFFSET) & 1;
}

static int s7hr_ck_step(int dir)
{
    if (dir > 0)
        ddrphy_ckphase_inc_write(1);
    else
        ddrphy_ckphase_dec_write(1);
    for (int i = 0; i < 100000; i++)
        if (!s7hr_ck_busy())
            return 1;
    return 0;
}

static int s7hr_ck_set(int target)
{
    int v;
    while ((v = s7hr_ck_value()) != target)
        if (!s7hr_ck_step(target > v ? 1 : -1))
            return 0;
    return 1;
}

/* DFI Check */
/*-----------*/

// The DFII registers of phase p (generated/csr.h's accessors are per phase).
static void s7hr_phase_address(int p, uint32_t address, uint32_t bank)
{
    switch (p) {
    case 0: sdram_dfii_pi0_address_write(address); sdram_dfii_pi0_baddress_write(bank); break;
    case 1: sdram_dfii_pi1_address_write(address); sdram_dfii_pi1_baddress_write(bank); break;
    case 2: sdram_dfii_pi2_address_write(address); sdram_dfii_pi2_baddress_write(bank); break;
    default: sdram_dfii_pi3_address_write(address); sdram_dfii_pi3_baddress_write(bank); break;
    }
}

static void s7hr_phase_command(int p, uint32_t cmd)
{
    switch (p) {
    case 0: command_p0(cmd); break;
    case 1: command_p1(cmd); break;
    case 2: command_p2(cmd); break;
    default: command_p3(cmd); break;
    }
}

static void s7hr_precharge_all(void)
{
    s7hr_phase_address(0, 0x400, 0);
    s7hr_phase_command(0, DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
    cdelay(15);
}

static uint32_t s7hr_rand_state = 0x2545F491;

static uint32_t s7hr_rand(void)
{
    // xorshift32: fresh data at every check, so stale data never reads back as a pass.
    uint32_t x = s7hr_rand_state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return s7hr_rand_state = x;
}

// One write/read round trip of S7HR_BURSTS bursts (row 0, bank 0); returns the failing DQ bits.
// A DFII phase carries two beats: CSR words, most significant first, {odd beat [63:32],
// odd [31:0], even [63:32], even [31:0]} (the CSRs are big-endian ordered).
static uint64_t s7hr_dfi_check(void)
{
    uint32_t data[S7HR_BURSTS][SDRAM_PHY_PHASES][DFII_PIX_DATA_SIZE];
    uint64_t errors = 0;
    int wrphase = ddrphy_wrphase_read();
    int rdphase = ddrphy_rdphase_read();

    // Activate.
    s7hr_phase_address(0, 0, 0);
    s7hr_phase_command(0, DFII_COMMAND_RAS|DFII_COMMAND_CS);
    cdelay(15);

    // Write.
    for (int b = 0; b < S7HR_BURSTS; b++) {
        for (int p = 0; p < SDRAM_PHY_PHASES; p++)
            for (int w = 0; w < DFII_PIX_DATA_SIZE; w++) {
                data[b][p][w] = s7hr_rand();
                csr_write_simple(data[b][p][w], sdram_dfii_pix_wrdata_addr(p) + 4*w);
            }
        s7hr_phase_address(wrphase, 8*b, 0);
        s7hr_phase_command(wrphase, DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS|DFII_COMMAND_WRDATA);
        cdelay(15);
    }

    // Read back.
    for (int b = 0; b < S7HR_BURSTS; b++) {
        s7hr_phase_address(rdphase, 8*b, 0);
        s7hr_phase_command(rdphase, DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA);
        cdelay(15);
        for (int p = 0; p < SDRAM_PHY_PHASES; p++)
            for (int w = 0; w < DFII_PIX_DATA_SIZE; w++) {
                uint32_t diff = csr_read_simple(sdram_dfii_pix_rddata_addr(p) + 4*w) ^ data[b][p][w];
                errors |= (w & 1) ? (uint64_t)diff : (uint64_t)diff << 32;
            }
    }

    // Precharge.
    s7hr_precharge_all();
    return errors;
}

/* BIST */
/*------*/

#ifdef CSR_SDRAM_GENERATOR_BASE
static uint32_t s7hr_bist(uint32_t base, uint32_t length)
{
    sdram_generator_reset_write(1);
    sdram_generator_random_write(1); // Random data.
    sdram_generator_base_write(base);
    sdram_generator_end_write(base + length);
    sdram_generator_length_write(length);
    sdram_generator_start_write(1);
    for (int i = 0; sdram_generator_done_read() == 0; i++)
        if (i > 10000000)
            return 0xffffffff;

    sdram_checker_reset_write(1);
    sdram_checker_random_write(1);
    sdram_checker_base_write(base);
    sdram_checker_end_write(base + length);
    sdram_checker_length_write(length);
    sdram_checker_start_write(1);
    for (int i = 0; sdram_checker_done_read() == 0; i++)
        if (i > 10000000)
            return 0xffffffff;
    return sdram_checker_errors_read();
}

static uint32_t s7hr_bist_hw(uint32_t length)
{
    uint32_t errors;
    sdram_dfii_control_write(DFII_CONTROL_SEL);
    errors = s7hr_bist(S7HR_BIST_BASE, length);
    sdram_dfii_control_write(DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
    return errors;
}
#else
// No LiteDRAM BIST in the SoC: the DFI checks alone pick the phase.
static uint32_t s7hr_bist_hw(uint32_t length)
{
    (void)length;
    return 0;
}
#endif

/* Calibration at one CK phase */
/*-----------------------------*/

// Longest run of ones in a tap mask.
static int s7hr_window(uint32_t mask, int *start)
{
    int best = 0, run = 0;
    *start = 0;
    for (int t = 0; t < S7HR_TAPS; t++) {
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

static void s7hr_read_scan(void)
{
    for (int rb = 0; rb < S7HR_BITSLIPS; rb++) {
        s7hr_set_rb(S7HR_ALL_LANES, 0, rb);
        s7hr_set_tap(S7HR_ALL_LANES, 0, 0);
        for (int b = 0; b < S7HR_BITS; b++)
            s7hr_scan[rb][b] = 0;
        for (int t = 0; t < S7HR_TAPS; t++) {
            uint64_t err = s7hr_dfi_check();
            for (int b = 0; b < S7HR_BITS; b++)
                if (!((err >> b) & 1))
                    s7hr_scan[rb][b] |= 1u << t;
            if (t != S7HR_TAPS - 1) {
                s7hr_select(S7HR_ALL_LANES, 0);
                ddrphy_rdly_dq_inc_write(1);
                s7hr_deselect();
            }
        }
    }
}

// Calibrate at the current CK phase; returns the lanes that pass the DFI check.
static uint32_t s7hr_calibrate_point(void)
{
    uint32_t lanes = 0;

    // Read scan at every write latency.
    for (int w = 0; w < S7HR_WLS; w++) {
        s7hr_set_wl(S7HR_ALL_LANES, 2*w);
        s7hr_read_scan();
        for (int b = 0; b < S7HR_BITS; b++) {
            struct s7hr_best *best = &s7hr_wl_best[w][b];
            best->len = 0;
            for (int rb = 0; rb < S7HR_BITSLIPS; rb++) {
                int start, len = s7hr_window(s7hr_scan[rb][b], &start);
                if (len > best->len) {
                    best->len     = len;
                    best->start   = start;
                    best->bitslip = rb;
                }
            }
        }
    }

    // Per lane: the write latency whose narrowest bit window is the widest.
    for (int l = 0; l < S7HR_LANES; l++) {
        int best_w = -1, best_min = 0;
        for (int w = 0; w < S7HR_WLS; w++) {
            int min = S7HR_TAPS;
            for (int i = 0; i < 8; i++)
                if (s7hr_wl_best[w][8*l + i].len < min)
                    min = s7hr_wl_best[w][8*l + i].len;
            if (min > best_min) {
                best_min = min;
                best_w   = w;
            }
        }
        if (best_w < 0)
            best_w = 0;
        s7hr.wl[l] = 2*best_w;
        s7hr_set_wl(1u << l, 2*best_w);
        for (int i = 0; i < 8; i++) {
            struct s7hr_best *best = &s7hr_wl_best[best_w][8*l + i];
            struct s7hr_bit *bit   = &s7hr.bit[8*l + i];
            bit->bitslip = best->bitslip;
            bit->tap     = best->start + best->len/2;
            bit->window  = best->len;
            s7hr_set_rb(1u << l, 1u << i, bit->bitslip);
            s7hr_set_tap(1u << l, 1u << i, bit->tap);
        }
        if (best_min >= S7HR_MIN_WINDOW)
            lanes |= 1u << l;
    }

    // Check the result (a few rounds of fresh data).
    for (int n = 0; n < 4; n++) {
        uint64_t err = s7hr_dfi_check();
        for (int l = 0; l < S7HR_LANES; l++)
            if ((err >> (8*l)) & 0xff)
                lanes &= ~(1u << l);
    }
    return lanes;
}

static void s7hr_init_dram(void)
{
    sdram_dfii_control_write(DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
    s7hr_precharge_all();
    init_sequence();
    sdram_dfii_control_write(DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
}

/* Calibration */
/*-------------*/

static void s7hr_print_point(int ck, uint32_t lanes, uint32_t bist)
{
    printf("  ck %+4d:", ck);
    for (int l = 0; l < S7HR_LANES; l++) {
        int min = S7HR_TAPS;
        for (int i = 0; i < 8; i++)
            if (s7hr.bit[8*l + i].window < min)
                min = s7hr.bit[8*l + i].window;
        printf(" %c%d/%02d", (lanes >> l) & 1 ? ' ' : '!', s7hr.wl[l], min);
    }
    if (bist == 0xfffffffe)
        printf("  bist -\n");
    else
        printf("  bist %lu\n", (unsigned long)bist);
}

// Index of a CK phase in the scan arrays ([-steps/2, steps/2) -> [0, steps)).
static int s7hr_index(int ck)
{
    return (ck + S7HR_STEPS/2 + S7HR_STEPS) % S7HR_STEPS;
}

static int s7hr_calibrate(void)
{
    const int half = S7HR_STEPS/2;
    int best_len = 0, best_start = 0;

    printf("S7HR DDR3 calibration (CSRs at %08lx): CK phase over one tCK, %d steps of %d\n",
        (unsigned long)CSR_DDRPHY_BASE, S7HR_STEPS/S7HR_SCAN_STRIDE, S7HR_SCAN_STRIDE);

    // PHY reset, MMCM lock.
    sdram_dfii_control_write(DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
    ddrphy_rst_write(1);
    cdelay(1000);
    ddrphy_rst_write(0);
    cdelay(1000);
    for (int i = 0; !s7hr_ck_locked(); i++) {
        if (i > 1000000) {
            printf("S7HR: PHY MMCM not locked\n");
            return 0;
        }
    }

    // Scan.
    for (int i = 0; i < S7HR_STEPS; i++)
        s7hr.lane_pass[i] = s7hr.bist_ok[i] = 0;
    for (int ck = -half; ck < half; ck += S7HR_SCAN_STRIDE) {
        if (!s7hr_ck_set(ck)) {
            printf("S7HR: CK phase step timeout\n");
            return 0;
        }
        s7hr_init_dram();
        uint32_t lanes = s7hr_calibrate_point();
        uint32_t bist  = 0xfffffffe;
        if (lanes == S7HR_ALL_LANES)
            bist = s7hr_bist_hw(S7HR_BIST_STEP_BYTES);
        s7hr_print_point(ck, lanes, bist);
        for (int j = 0; j < S7HR_SCAN_STRIDE; j++) {
            s7hr.lane_pass[s7hr_index(ck + j)] = lanes;
            s7hr.bist_ok[s7hr_index(ck + j)]   = (bist == 0);
        }
    }

    // Longest circular run of phases where every lane and the BIST pass.
    for (int start = 0; start < S7HR_STEPS; start++) {
        int len = 0;
        while (len < S7HR_STEPS) {
            int i = (start + len) % S7HR_STEPS;
            if (s7hr.lane_pass[i] != S7HR_ALL_LANES || !s7hr.bist_ok[i])
                break;
            len++;
        }
        if (len > best_len) {
            best_len   = len;
            best_start = start;
        }
    }
    s7hr.run = best_len;
    if (best_len == 0) {
        printf("S7HR: no CK phase where every lane passes\n");
        s7hr.ok = 0;
        return 0;
    }
    s7hr.ckphase = (best_start + best_len/2) % S7HR_STEPS - half;

    // Calibrate at the centre of the run.
    s7hr_ck_set(s7hr.ckphase);
    s7hr_init_dram();
    uint32_t lanes = s7hr_calibrate_point();
    s7hr.bist_errors = (lanes == S7HR_ALL_LANES) ? s7hr_bist_hw(S7HR_BIST_FINAL_BYTES) : 0xffffffff;
    s7hr.ok = (lanes == S7HR_ALL_LANES) && (s7hr.bist_errors == 0);
    s7hr_print_point(s7hr.ckphase, lanes, s7hr.bist_errors);
    printf("S7HR: CK phase %+d (run %d steps), write bitslips", s7hr.ckphase, s7hr.run);
    for (int l = 0; l < S7HR_LANES; l++)
        printf(" %d", s7hr.wl[l]);
    printf(", read bitslip/tap/window per bit:\n");
    for (int l = 0; l < S7HR_LANES; l++) {
        printf("  m%d:", l);
        for (int i = 0; i < 8; i++)
            printf(" %d/%02d/%02d", s7hr.bit[8*l + i].bitslip, s7hr.bit[8*l + i].tap,
                s7hr.bit[8*l + i].window);
        printf("\n");
    }
    printf("S7HR: %s (BIST %lu KB, %lu errors)\n", s7hr.ok ? "OK" : "FAILED",
        (unsigned long)(S7HR_BIST_FINAL_BYTES >> 10), (unsigned long)s7hr.bist_errors);
    return s7hr.ok;
}

int sdram_s7hr_init(int controller)
{
    int ok;
#ifdef SDRAM_S7HR_CSR_STRIDE
    s7hr_csr_base = s7hr_csr_base0 + (unsigned long)controller*SDRAM_S7HR_CSR_STRIDE;
#else
    if (controller != 0) {
        printf("S7HR: controller %d: no SDRAM_S7HR_CSR_STRIDE\n", controller);
        return 0;
    }
    s7hr_csr_base = s7hr_csr_base0;
#endif
    ok = s7hr_calibrate();
    // Controller 0 is released by sdram_init(); the others here.
    if (controller != 0)
        sdram_dfii_control_write(ok ? DFII_CONTROL_SEL :
            (DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N));
    s7hr_csr_base = s7hr_csr_base0;
    return ok;
}

#endif /* SDRAM_S7HR_CALIBRATION */
