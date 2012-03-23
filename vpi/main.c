/*
 * Copyright (C) 2012 Vermeer Manufacturing Co.
 * License: GPLv3 with additional permissions (see README).
 */

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <vpi_user.h>

#include "ipc.h"

struct migensim_softc {
	struct ipc_softc *ipc;
	int has_go;
};

static int h_go(void *user)
{
	struct migensim_softc *sc = (struct migensim_softc *)user;
	sc->has_go = 1;
	return 1;
}

static s_vpi_time zero_delay = {
	.type = vpiSimTime,
	.high = 0,
	.low = 0
};

static int h_write(char *name, int index, int nchunks, const unsigned char *chunks, void *user)
{
	vpiHandle item;
	s_vpi_vecval vector[64];
	int i;
	s_vpi_value value;
	
	item = vpi_handle_by_name(name, NULL);
	if(item == NULL) {
		fprintf(stderr, "Attempted to write non-existing signal %s\n", name);
		return 0;
	}
	if(vpi_get(vpiType, item) == vpiMemory)
		item = vpi_handle_by_index(item, index);
	else
		assert(index == 0);
	
	assert(nchunks <= 255);
	for(i=0;i<64;i++) {
		vector[i].aval = 0;
		vector[i].bval = 0;
	}
	for(i=0;i<nchunks;i++)
		vector[i/4].aval |= chunks[i] << 8*(i % 4);
	
	value.format = vpiVectorVal;
	value.value.vector = vector;
	vpi_put_value(item, &value, &zero_delay, vpiInertialDelay);
	
	return 1;
}

static int h_read(char *name, int index, void *user)
{
	struct migensim_softc *sc = (struct migensim_softc *)user;
	vpiHandle item;
	s_vpi_value value;
	int size;
	int i;
	int nvals;
	unsigned int vals[64];
	int nchunks;
	unsigned char chunks[255];
	
	item = vpi_handle_by_name(name, NULL);
	if(item == NULL) {
		fprintf(stderr, "Attempted to read non-existing signal %s\n", name);
		return 0;
	}
	if(vpi_get(vpiType, item) == vpiMemory)
		item = vpi_handle_by_index(item, index);
	else
		assert(index == 0);
	
	value.format = vpiVectorVal;
	vpi_get_value(item, &value);
	size = vpi_get(vpiSize, item);
	nvals = (size + 31)/32;
	assert(nvals <= 64);
	for(i=0;i<nvals;i++)
		vals[i] = value.value.vector[i].aval & ~value.value.vector[i].bval;
	nchunks = (size + 7)/8;
	assert(nchunks <= 255);
	for(i=0;i<nchunks;i++) {
		switch(i % 4) {
			case 0:
				chunks[i] = vals[i/4] & 0xff;
				break;
			case 1:
				chunks[i] = (vals[i/4] & 0xff00) >> 8;
				break;
			case 2:
				chunks[i] = (vals[i/4] & 0xff0000) >> 16;
				break;
			case 3:
				chunks[i] = (vals[i/4] & 0xff000000) >> 24;
				break;
		}
	}
	
	if(!ipc_read_reply(sc->ipc, nchunks, chunks)) {
		perror("ipc_read_reply");
		return 0;
	}
	
	return 1;
}

static int process_until_go(struct migensim_softc *sc)
{
	int r;
	
	sc->has_go = 0;
	while(!sc->has_go) {
		r = ipc_receive(sc->ipc);
		if(r != 1)
			return r;
	}
	return 1;
}

static PLI_INT32 connect_calltf(PLI_BYTE8 *user)
{
	struct migensim_softc *sc = (struct migensim_softc *)user;
	vpiHandle sys;
	vpiHandle argv;
	vpiHandle item;
	s_vpi_value value;
	
	sys = vpi_handle(vpiSysTfCall, 0);
	argv = vpi_iterate(vpiArgument, sys);
	item = vpi_scan(argv);
	value.format = vpiStringVal;
	vpi_get_value(item, &value);
	
	sc->ipc = ipc_connect(value.value.str, h_go, h_write, h_read, sc);
	if(sc->ipc == NULL) {
		perror("ipc_connect");
		vpi_control(vpiFinish, 1);
		return 0;
	}
	
	return 0;
}

static PLI_INT32 tick_calltf(PLI_BYTE8 *user)
{
	struct migensim_softc *sc = (struct migensim_softc *)user;
	int r;
	
	if(!ipc_tick(sc->ipc)) {
		perror("ipc_tick");
		vpi_control(vpiFinish, 1);
		ipc_destroy(sc->ipc);
		sc->ipc = NULL;
		return 0;
	}
	r = process_until_go(sc);
	if(r != 1) {
		vpi_control(vpiFinish, r == 2 ? 0 : 1);
		ipc_destroy(sc->ipc);
		sc->ipc = NULL;
		return 0;
	}
	
	return 0;
}

static struct migensim_softc sc;

static void simple_register(const char *tfname, PLI_INT32 (*calltf)(PLI_BYTE8 *))
{
	s_vpi_systf_data tf_data;

	tf_data.type      = vpiSysTask;
	tf_data.tfname    = tfname;
	tf_data.calltf    = calltf;
	tf_data.compiletf = NULL;
	tf_data.sizetf    = 0;
	tf_data.user_data = (void *)&sc;
	vpi_register_systf(&tf_data);
}

static void migensim_register()
{
	simple_register("$migensim_connect", connect_calltf);
	simple_register("$migensim_tick", tick_calltf);
}

void (*vlog_startup_routines[])() = {
	migensim_register,
	0
};
