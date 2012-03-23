/*
 * Copyright (C) 2012 Vermeer Manufacturing Co.
 * License: GPLv3 with additional permissions (see README).
 */

#include <assert.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "ipc.h"

struct ipc_softc {
	int socket;
	go_handler h_go;
	write_handler h_write;
	read_handler h_read;
	void *user;
};

struct ipc_softc *ipc_connect(const char *sockaddr,
	go_handler h_go, write_handler h_write, read_handler h_read, void *user)
{
	struct ipc_softc *sc;
	struct sockaddr_un addr;
	
	sc = malloc(sizeof(struct ipc_softc));
	if(!sc) return NULL;
	
	sc->h_go = h_go;
	sc->h_write = h_write;
	sc->h_read = h_read;
	sc->user = user;
	
	sc->socket = socket(AF_UNIX, SOCK_SEQPACKET, 0);
	if(sc->socket < 0) {
		free(sc);
		return NULL;
	}
	
	addr.sun_family = AF_UNIX;
	strcpy(addr.sun_path, sockaddr);
	if(connect(sc->socket, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
		close(sc->socket);
		free(sc);
		return NULL;
	}
	
	return sc;
}

void ipc_destroy(struct ipc_softc *sc)
{
	close(sc->socket);
	free(sc);
}

enum {
	MESSAGE_TICK = 0,
	MESSAGE_GO,
	MESSAGE_WRITE,
	MESSAGE_READ,
	MESSAGE_READ_REPLY
};

#define MAX_LEN 2048

/*
 * 0 -> error
 * 1 -> success
 * 2 -> graceful shutdown
 */
int ipc_receive(struct ipc_softc *sc)
{
	char buffer[MAX_LEN];
	ssize_t l;
	int i;
	
	l = recv(sc->socket, buffer, MAX_LEN, 0);
	if(l == 0)
		return 2;
	if((l < 0) || (l >= MAX_LEN))
		return 0;
	
	i = 0;
	switch(buffer[i++]) {
		case MESSAGE_GO:
			assert(l == 1);
			return sc->h_go(sc->user);
		case MESSAGE_WRITE: {
			char *name;
			int nchunks;
			unsigned char *chunks;
			unsigned int index;
			
			name = &buffer[i];
			i += strlen(name) + 1;
			assert((i+4) < l);
			index = buffer[i] | buffer[i+1] << 8 | buffer[i+2] << 16 | buffer[i+3] << 24;
			i += 4;
			nchunks = buffer[i++];
			assert(i + nchunks == l);
			chunks = (unsigned char *)&buffer[i];
			
			return sc->h_write(name, index, nchunks, chunks, sc->user);
		}
		case MESSAGE_READ: {
			char *name;
			unsigned int index;
			
			name = &buffer[i];
			i += strlen(name) + 1;
			assert((i+4) == l);
			index = buffer[i] | buffer[i+1] << 8 | buffer[i+2] << 16 | buffer[i+3] << 24;
			
			return sc->h_read(name, index, sc->user);
		}
		default:
			return 0;
	}
}

int ipc_tick(struct ipc_softc *sc)
{
	char c;
	ssize_t l;
	
	c = MESSAGE_TICK;
	l = send(sc->socket, &c, 1, 0);
	if(l != 1)
		return 0;
	return 1;
}

int ipc_read_reply(struct ipc_softc *sc, int nchunks, const unsigned char *chunks)
{
	int len;
	char buffer[MAX_LEN];
	ssize_t l;
	
	len = nchunks + 2;
	assert(len < MAX_LEN);
	assert(nchunks < 256);
	
	buffer[0] = MESSAGE_READ_REPLY;
	buffer[1] = nchunks;
	memcpy(&buffer[2], chunks, nchunks);
	
	l = send(sc->socket, buffer, len, 0);
	if(l != len)
		return 0;
	return 1;
}
