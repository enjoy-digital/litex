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
	
	printf("GO\n");
	sc->has_go = 1;
	
	return 1;
}

static int h_write(char *name, int nchunks, const unsigned char *chunks, void *user)
{
	int i;
	
	printf("WRITE: %s / nchunks: %d / ", name, nchunks);
	for(i=0;i<nchunks;i++)
		printf("%02hhx", chunks[i]);
	printf("\n");
	
	return 1;
}

static int h_read(char *name, void *user)
{
	printf("READ: %s\n", name);
	
	return 1;
}

static int process_until_go(struct migensim_softc *sc)
{
	sc->has_go = 0;
	while(!sc->has_go) {
		if(!ipc_receive(sc->ipc))
			return 0;
	}
	return 1;
}

static int connect_calltf(char *user)
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
	
	if(!process_until_go(sc)) {
		vpi_control(vpiFinish, 1);
		return 0;
	}
	
	return 0;
}

static int tick_calltf(char *user)
{
	struct migensim_softc *sc = (struct migensim_softc *)user;
	
	if(!ipc_tick(sc->ipc)) {
		perror("ipc_tick");
		vpi_control(vpiFinish, 1);
		return 0;
	}
	if(!process_until_go(sc)) {
		vpi_control(vpiFinish, 1);
		return 0;
	}
	
	return 0;
}

static struct migensim_softc sc;

static void simple_register(const char *tfname, PLI_INT32 (*calltf)(PLI_BYTE8*))
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
