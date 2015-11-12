/*
 * Copyright (C) 2012 Vermeer Manufacturing Co.
 * License: GPLv3 with additional permissions (see README).
 */

#ifndef __IPC_H
#define __IPC_H

struct ipc_softc;

typedef int(*go_handler)(void *);
typedef int(*write_handler)(char *, int, int, const unsigned char *, void *);
typedef int(*read_handler)(char *, int, void *);

struct ipc_softc *ipc_connect(const char *sockaddr, 
	go_handler h_go, write_handler h_write, read_handler h_read, void *user);
void ipc_destroy(struct ipc_softc *sc);

int ipc_receive(struct ipc_softc *sc);

int ipc_tick(struct ipc_softc *sc);
int ipc_read_reply(struct ipc_softc *sc, int nchunks, const unsigned char *value);

#endif /* __IPC_H */
