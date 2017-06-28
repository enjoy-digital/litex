/* Copyright (C) 2017 LambdaConcept */

#ifndef __VERIL_H_
#define __VERIL_H_

#ifdef __cplusplus
extern "C" void litex_sim_eval(void *vdut);
extern "C" void litex_sim_init_tracer(void *vdut);
extern "C" void litex_sim_tracer_dump();
#else
void litex_sim_eval(void *vdut);
void litex_sim_init_tracer(void *vdut);
void litex_sim_tracer_dump();
#endif

#endif
