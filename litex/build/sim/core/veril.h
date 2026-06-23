/* Copyright (C) 2017 LambdaConcept */

#ifndef __VERIL_H_
#define __VERIL_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void litex_sim_init_cmdargs(int argc, char *argv[]);
void litex_sim_eval(void *vsim, uint64_t time_ps);
void litex_sim_init_runtime(long load_start, long save_start);
void litex_sim_init_tracer(void *vsim, long start, long end,
                           const char *timescale, uint64_t timescale_ps);
void litex_sim_tracer_dump(void);
int litex_sim_got_finish(void);
void litex_sim_finalize(void *vsim);
#if VM_COVERAGE
void litex_sim_coverage_dump(void);
#endif

#ifdef __cplusplus
}
#endif

#endif
