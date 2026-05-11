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
/* Leveling                                                              */
/*-----------------------------------------------------------------------*/
int sdram_leveling(void);

/*-----------------------------------------------------------------------*/
/* Initialization                                                        */
/*-----------------------------------------------------------------------*/
int sdram_init(void);
int sdram_init_all(void);

#ifdef CSR_SDRAM1_BASE
int sdram1_init(void);
#endif
#ifdef CSR_SDRAM2_BASE
int sdram2_init(void);
#endif
#ifdef CSR_SDRAM3_BASE
int sdram3_init(void);
#endif

/*-----------------------------------------------------------------------*/
/* Debugging                                                             */
/*-----------------------------------------------------------------------*/
void sdram_debug(void);

#ifdef __cplusplus
}
#endif

#endif /* __SDRAM_H */
