#ifndef __LITEDRAM_INSTANCE_H
#define __LITEDRAM_INSTANCE_H

#define LITEDRAM_CONCAT2(a, b) a##b
#define LITEDRAM_CONCAT(a, b)  LITEDRAM_CONCAT2(a, b)

#define LITEDRAM_SYMBOL(name)     LITEDRAM_CONCAT(LITEDRAM_INSTANCE, name)

/* Public SDRAM API. */
#define sdram_get_databits                      LITEDRAM_SYMBOL(_get_databits)
#define sdram_get_freq                          LITEDRAM_SYMBOL(_get_freq)
#define sdram_get_cl                            LITEDRAM_SYMBOL(_get_cl)
#define sdram_get_cwl                           LITEDRAM_SYMBOL(_get_cwl)
#define sdram_software_control_on               LITEDRAM_SYMBOL(_software_control_on)
#define sdram_software_control_off              LITEDRAM_SYMBOL(_software_control_off)
#define sdram_mode_register_write               LITEDRAM_SYMBOL(_mode_register_write)
#define sdram_write_leveling_rst_cmd_delay      LITEDRAM_SYMBOL(_write_leveling_rst_cmd_delay)
#define sdram_write_leveling_force_cmd_delay    LITEDRAM_SYMBOL(_write_leveling_force_cmd_delay)
#define sdram_write_leveling                    LITEDRAM_SYMBOL(_write_leveling)
#define sdram_read_leveling                     LITEDRAM_SYMBOL(_read_leveling)
#define sdram_leveling                          LITEDRAM_SYMBOL(_leveling)
#define sdram_init                              LITEDRAM_SYMBOL(_init)
#define sdram_debug                             LITEDRAM_SYMBOL(_debug)

/* SDRAM calibration globals. */
#define _sdram_tck_taps                         LITEDRAM_SYMBOL(_tck_taps)
#define _sdram_write_leveling_cmd_scan          LITEDRAM_SYMBOL(_write_leveling_cmd_scan)
#define _sdram_write_leveling_cmd_delay         LITEDRAM_SYMBOL(_write_leveling_cmd_delay)
#define _sdram_write_leveling_cdly_range_start  LITEDRAM_SYMBOL(_write_leveling_cdly_range_start)
#define _sdram_write_leveling_cdly_range_end    LITEDRAM_SYMBOL(_write_leveling_cdly_range_end)

/* Accessors API. */
#define read_dq_delay                           LITEDRAM_SYMBOL(_read_dq_delay)
#define read_inc_dq_delay                       LITEDRAM_SYMBOL(_read_inc_dq_delay)
#define read_rst_dq_delay                       LITEDRAM_SYMBOL(_read_rst_dq_delay)
#define sdram_clock_delay                       LITEDRAM_SYMBOL(_clock_delay)
#define sdram_inc_clock_delay                   LITEDRAM_SYMBOL(_inc_clock_delay)
#define sdram_rst_clock_delay                   LITEDRAM_SYMBOL(_rst_clock_delay)
#define write_dq_delay                          LITEDRAM_SYMBOL(_write_dq_delay)
#define write_inc_dq_delay                      LITEDRAM_SYMBOL(_write_inc_dq_delay)
#define write_rst_dq_delay                      LITEDRAM_SYMBOL(_write_rst_dq_delay)
#define write_inc_dqs_delay                     LITEDRAM_SYMBOL(_write_inc_dqs_delay)
#define write_rst_dqs_delay                     LITEDRAM_SYMBOL(_write_rst_dqs_delay)
#define write_inc_delay                         LITEDRAM_SYMBOL(_write_inc_delay)
#define write_rst_delay                         LITEDRAM_SYMBOL(_write_rst_delay)
#define read_dq_bitslip                         LITEDRAM_SYMBOL(_read_dq_bitslip)
#define read_inc_dq_bitslip                     LITEDRAM_SYMBOL(_read_inc_dq_bitslip)
#define read_rst_dq_bitslip                     LITEDRAM_SYMBOL(_read_rst_dq_bitslip)
#define write_dq_bitslip                        LITEDRAM_SYMBOL(_write_dq_bitslip)
#define write_inc_dq_bitslip                    LITEDRAM_SYMBOL(_write_inc_dq_bitslip)
#define write_rst_dq_bitslip                    LITEDRAM_SYMBOL(_write_rst_dq_bitslip)
#define sdram_select                            LITEDRAM_SYMBOL(_select)
#define sdram_deselect                          LITEDRAM_SYMBOL(_deselect)
#define sdram_leveling_action                   LITEDRAM_SYMBOL(_leveling_action)
#define _sdram_write_leveling_dat_delays        LITEDRAM_SYMBOL(_write_leveling_dat_delays)
#define sdram_write_leveling_rst_dat_delay      LITEDRAM_SYMBOL(_write_leveling_rst_dat_delay)
#define sdram_write_leveling_force_dat_delay    LITEDRAM_SYMBOL(_write_leveling_force_dat_delay)
#define _sdram_write_leveling_bitslips          LITEDRAM_SYMBOL(_write_leveling_bitslips)
#define sdram_write_leveling_rst_bitslip        LITEDRAM_SYMBOL(_write_leveling_rst_bitslip)
#define sdram_write_leveling_force_bitslip      LITEDRAM_SYMBOL(_write_leveling_force_bitslip)

#endif /* __LITEDRAM_INSTANCE_H */
