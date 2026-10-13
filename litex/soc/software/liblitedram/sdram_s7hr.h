// This file is part of LiteX.
//
// Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
// SPDX-License-Identifier: BSD-2-Clause

#ifndef __SDRAM_S7HR_H
#define __SDRAM_S7HR_H

#ifdef __cplusplus
extern "C" {
#endif

/* Built when the SoC's PHY is an S7DDRPHY with CK phase shift (generated/sdram_phy.h, included
 * before this file, defines SDRAM_PHY_CKPHASE_STEPS). */
#if defined(SDRAM_PHY_CKPHASE_STEPS)
#define SDRAM_S7HR_CALIBRATION
#endif

/* Calibrate controller `controller` of a SoC with LiteDRAM's S7DDRPHY with CK phase shift:
 * CK phase scan, per-lane write latency, per-bit read leveling, BIST. Returns 1 on success.
 * Controller 0 is calibrated by sdram_init(); controller k > 0 needs SDRAM_S7HR_CSR_STRIDE. */
int sdram_s7hr_init(int controller);

#ifdef __cplusplus
}
#endif

#endif /* __SDRAM_S7HR_H */
