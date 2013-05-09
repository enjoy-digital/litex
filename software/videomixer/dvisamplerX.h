#ifndef __DVISAMPLERX_H
#define __DVISAMPLERX_H

void dvisamplerX_isr(void);
void dvisamplerX_init_video(void);
void dvisamplerX_print_status(void);
void dvisamplerX_calibrate_delays(void);
void dvisamplerX_adjust_phase(void);
int dvisamplerX_init_phase(void);
void dvisamplerX_service(void);

#endif
