/* Copyright (C) 2017 LambdaConcept */

#ifndef __VERIL_H_
#define __VERIL_H_

#ifdef __cplusplus
extern "C" void lambdasim_eval(void *vdut);
extern "C" void lambdasim_init_tracer(void *vdut);
extern "C" void lambdasim_tracer_dump();
#else
void lambdasim_eval(void *vdut);
void lambdasim_init_tracer(void *vdut);
void lambdasim_tracer_dump();
#endif

#endif
