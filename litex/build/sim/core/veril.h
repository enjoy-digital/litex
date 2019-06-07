/* Copyright (C) 2017 LambdaConcept */

#ifndef __VERIL_H_
#define __VERIL_H_

#ifdef __cplusplus
extern "C" void litex_sim_init_cmdargs(int argc, char *argv[]);
extern "C" void litex_sim_eval(void *vdut);
extern "C" void litex_sim_init_tracer(void *vdut, long start, long end)
extern "C" void litex_sim_tracer_dump();
extern "C" int litex_sim_got_finish();
#if VM_COVERAGE
extern "C" void litex_sim_coverage_dump();
#endif
#else
void litex_sim_eval(void *vdut);
void litex_sim_init_tracer(void *vdut);
void litex_sim_tracer_dump();
int litex_sim_got_finish();
#if VM_COVERAGE
void litex_sim_coverage_dump();
#endif
#endif

#endif
