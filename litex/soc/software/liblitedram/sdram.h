#ifndef __SDRAM_H
#define __SDRAM_H

#ifdef __cplusplus
extern "C" {
#endif

#include <generated/csr.h>

/*-----------------------------------------------------------------------*/
/* Constants                                                             */
/*-----------------------------------------------------------------------*/
int sdram_get_databits(void);
int sdram_get_freq(void);
int sdram_get_cl(void);
int sdram_get_cwl(void);

/*-----------------------------------------------------------------------*/
/* Software/Hardware Control                                             */
/*-----------------------------------------------------------------------*/
void sdram_software_control_on(void);
void sdram_software_control_off(void);

/*-----------------------------------------------------------------------*/
/* Mode Register                                                         */
/*-----------------------------------------------------------------------*/
void sdram_mode_register_write(char reg, int value);

/*-----------------------------------------------------------------------*/
/* Write Leveling                                                        */
/*-----------------------------------------------------------------------*/
void sdram_write_leveling_rst_cmd_delay(int show);
void sdram_write_leveling_force_cmd_delay(int taps, int show);
int sdram_write_leveling(void);

/*-----------------------------------------------------------------------*/
/* Read Leveling                                                         */
/*-----------------------------------------------------------------------*/
void sdram_read_leveling(void);

/*-----------------------------------------------------------------------*/
/* CK Phase Leveling (SDRAM_PHY_CKPHASE_STEPS)                           */
/*-----------------------------------------------------------------------*/
int sdram_ckphase_leveling(int controller);
// After a successful leveling: the per-bit read eye re-centred under the application's own
// reads (traffic(arg): once per tap offset, returns the error count, 0 clean, -1 not run; the
// DFI ECC's per-DQ counters attribute errors to bits when present), and the read taps.
int sdram_ckphase_eye_refine(int (*traffic)(void *arg), void *arg, int range, const char *what);
int sdram_ckphase_bit_tap(int bit);
int sdram_ckphase_bit_tap_set(int bit, int tap);

/*-----------------------------------------------------------------------*/
/* Write Training (SDRAM_WRITE_TRAINING)                                 */
/*-----------------------------------------------------------------------*/
/* Round-trip training of the write side of every module (write bitslip, DQS and DQ delays,
 * then the reads), under software control like the other stages: the mask of the modules
 * that did not train (0: all trained). */
int sdram_write_training(void);
/* The error bits of every module on the training pattern (each seed and its complement),
 * under software control; errors_per_module (SDRAM_PHY_MODULES entries) may be NULL. Returns
 * the mask of the modules with errors. */
int sdram_write_training_check(int *errors_per_module);

/*-----------------------------------------------------------------------*/
/* Leveling                                                              */
/*-----------------------------------------------------------------------*/
int sdram_leveling(void);

/*-----------------------------------------------------------------------*/
/* Initialization                                                        */
/*-----------------------------------------------------------------------*/
#ifdef CONFIG_SDRAM_CUSTOM_INIT
/* Implement this when CONFIG_SDRAM_CUSTOM_INIT is defined. Return 1 after
 * successful memory-specific initialization and calibration, or 0 on error.
 * The common sdram_init() path retains controller handoff and memory tests. */
int sdram_custom_init(void);
#endif
int sdram_init(void);

/*-----------------------------------------------------------------------*/
/* Debugging                                                             */
/*-----------------------------------------------------------------------*/
void sdram_debug(void);

#ifdef __cplusplus
}
#endif

#endif /* __SDRAM_H */
